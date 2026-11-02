"""Analyse the Phase 1 36-question regression and compare with the 2026-10-28 run.

Usage:
    python reports/phase1-m0-20261029/analyze_regression.py \
        --current reports/phase1-m0-20261029/regression-36-http.json \
        --history reports/rag-framework-20261028/http-results.json \
        --out-json reports/phase1-m0-20261029/regression-36-analysis.json \
        --out-md reports/phase1-m0-20261029/regression-36-analysis.md
"""

import argparse
import json
import re
import statistics
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from accelerator_rag.evaluation.retrieval import normalize_evidence  # noqa: E402


def norm(text):
    return normalize_evidence(text or "")


def percentile(values, fraction):
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", required=True)
    parser.add_argument("--history", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    current = json.loads(Path(args.current).read_text())
    history = json.loads(Path(args.history).read_text())
    benchmark = json.loads((ROOT / "data/evaluation/retrieval_baseline.json").read_text())
    registry = json.loads((ROOT / "data/documents/registry.json").read_text())
    doc_pages = {d["doc_id"]: d for d in registry}
    current_bench = {q["id"]: q for q in benchmark["queries"]}
    history_cases = {c["id"]: c for c in history["cases"]}

    rows, violations = [], []
    for case in current["cases"]:
        response = case.get("response", {})
        qid = case["id"]
        citations = response.get("citations", [])
        requirements = response.get("requirements", [])
        supported = sum(1 for r in requirements if r["supported"])
        latency = response.get("latency", {})
        row = {
            "id": qid,
            "http_status": case.get("http_status"),
            "status": response.get("status"),
            "answerable": case.get("answerable"),
            "requirements": len(requirements),
            "requirements_supported": supported,
            "citations": len(citations),
            "documents": sorted({c["document_id"] for c in citations}),
            "wall_seconds": round(case.get("wall_seconds", 0), 2),
            "total_seconds": round(latency.get("total_seconds", 0), 2),
            "history_status": history_cases.get(qid, {}).get("response", {}).get("status"),
            "history_wall_seconds": round(history_cases.get(qid, {}).get("wall_seconds", 0), 2),
        }
        rows.append(row)

        status = row["status"]
        if case.get("http_status") != 200:
            violations.append({"id": qid, "rule": "http_status", "detail": case.get("http_status")})
        if not response.get("answer"):
            violations.append({"id": qid, "rule": "empty_answer", "detail": status})
        if not response.get("request_id"):
            violations.append({"id": qid, "rule": "missing_request_id", "detail": status})
        if status == "answered" and (len(requirements) == 0 or supported != len(requirements)):
            violations.append({"id": qid, "rule": "answered_unsupported_requirement",
                               "detail": f"{supported}/{len(requirements)}"})
        if status in {"answered", "partial"} and not citations:
            violations.append({"id": qid, "rule": "answer_without_citation", "detail": status})
        if status == "insufficient" and citations:
            violations.append({"id": qid, "rule": "insufficient_with_citation",
                               "detail": len(citations)})
        if status not in {"answered", "partial", "insufficient"}:
            violations.append({"id": qid, "rule": "unknown_status", "detail": status})
        for citation in citations:
            doc_id = citation.get("document_id")
            if doc_id not in doc_pages:
                violations.append({"id": qid, "rule": "unknown_document", "detail": doc_id})
            start, end = citation.get("page_start"), citation.get("page_end")
            if not (isinstance(start, int) and isinstance(end, int) and 1 <= start <= end <= 2178):
                violations.append({"id": qid, "rule": "bad_page_range", "detail": f"{start}-{end}"})
            if not citation.get("quote"):
                violations.append({"id": qid, "rule": "empty_quote", "detail": doc_id})
            if not str(citation.get("chunk_id", "")).startswith(str(doc_id) + ":"):
                violations.append({"id": qid, "rule": "chunk_document_mismatch", "detail": doc_id})
        chunk_ids = [c["chunk_id"] for c in citations]
        if len(chunk_ids) != len(set(chunk_ids)):
            violations.append({"id": qid, "rule": "duplicate_citation", "detail": ""})
        if row["answerable"] and status == "insufficient":
            violations.append({"id": qid, "rule": "answerable_but_insufficient", "detail": ""})
        if row["answerable"] is False and status in {"answered", "partial"}:
            violations.append({"id": qid, "rule": "negative_answered", "detail": status})

    # Frozen-evidence containment, same rule as scripts/rag_framework_review.py:
    # document id + physical page range + normalized excerpt containment in quote.
    def freeze_coverage(run):
        coverage = []
        cases = {c["id"]: c for c in run["cases"]}
        for qid, query in current_bench.items():
            if not query["answerable"]:
                continue
            case = cases.get(qid)
            if case is None:
                coverage.append({"id": qid, "groups": len(query["evidence_groups"]),
                                 "covered": 0, "judgment_mode": query["judgment_mode"],
                                 "note": "not run"})
                continue
            citations = case["response"].get("citations", [])
            hit = 0
            for group in query["evidence_groups"]:
                matched = False
                for citation in citations:
                    for target in group["alternatives"]:
                        if (
                            citation.get("document_id") == target["document_id"]
                            and citation.get("page_start", 0)
                            <= target["page"]
                            <= citation.get("page_end", -1)
                            and norm(target["excerpt"]) in norm(citation.get("quote", ""))
                        ):
                            matched = True
                            break
                    if matched:
                        break
                hit += matched
            coverage.append({"id": qid, "groups": len(query["evidence_groups"]),
                             "covered": hit, "judgment_mode": query["judgment_mode"]})
        return coverage

    def complete(row):
        return bool(row["covered"]) if row["judgment_mode"] == "any" else row["covered"] == row["groups"]

    containment = freeze_coverage(current)
    history_containment = freeze_coverage(history)

    latencies = [row["total_seconds"] for row in rows if row["total_seconds"]]
    history_latencies = [row["history_wall_seconds"] for row in rows if row["history_wall_seconds"]]
    summary = {
        "execution": "real production HTTP via 127.0.0.1:18003",
        "current_benchmark_sha256": current.get("benchmark_sha256"),
        "history_benchmark_sha256": history.get("benchmark_sha256"),
        "benchmark_hash_changed": current.get("benchmark_sha256") != history.get("benchmark_sha256"),
        "workers": current.get("workers"),
        "http_errors": sum(1 for row in rows if row["http_status"] != 200),
        "statuses": dict(Counter(row["status"] for row in rows)),
        "history_statuses": dict(Counter(row["history_status"] for row in rows)),
        "citations": sum(row["citations"] for row in rows),
        "documents_cited": len({doc for row in rows for doc in row["documents"]}),
        "latency_seconds": {
            "median": round(statistics.median(latencies), 2),
            "p95": round(percentile(latencies, 0.95), 2),
            "max": round(max(latencies), 2),
            "sum": round(sum(latencies), 2),
        },
        "history_latency_seconds": {
            "median": round(statistics.median(history_latencies), 2),
            "p95": round(percentile(history_latencies, 0.95), 2),
            "max": round(max(history_latencies), 2),
        },
        "status_changes_vs_history": [
            {"id": row["id"], "history": row["history_status"], "current": row["status"]}
            for row in rows if row["history_status"] != row["status"]
        ],
        "frozen_evidence_containment": {
            "definition": "document_id + physical page range + normalize_evidence(excerpt) contained in citation quote; complete = all groups (judgment_mode=all for all 32 items)",
            "groups": sum(item["groups"] for item in containment),
            "covered": sum(item["covered"] for item in containment),
            "questions_fully_covered": sum(complete(item) for item in containment),
            "answerable_questions": len(containment),
            "history_questions_fully_covered": sum(complete(item) for item in history_containment),
            "per_question": containment,
            "history_per_question": history_containment,
        },
        "contract_violations": violations,
        "rows": rows,
        "containment": containment,
    }

    out_json = Path(args.out_json)
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")

    lines = [
        "# 36 题回归结果分析（2026-10-29）",
        "",
        "数据来源：`reports/phase1-m0-20261029/regression-36-http.json`（本次实跑）与 "
        "`reports/rag-framework-20261028/http-results.json`（历史全量）。",
        "",
        "## 汇总",
        "",
        f"- 执行：{summary['execution']}；HTTP 工作线程 {summary['workers']}",
        f"- HTTP 200：{36 - summary['http_errors']}/36；客户端错误 0",
        f"- 状态：{summary['statuses']}",
        f"- 引用：{summary['citations']} 条，涉及 {summary['documents_cited']} 份文档",
        f"- 耗时（本次）：中位 {summary['latency_seconds']['median']} s，P95 {summary['latency_seconds']['p95']} s，"
        f"最大 {summary['latency_seconds']['max']} s",
        f"- 耗时（历史）：中位 {summary['history_latency_seconds']['median']} s，P95 {summary['history_latency_seconds']['p95']} s，"
        f"最大 {summary['history_latency_seconds']['max']} s",
        f"- 冻结证据包含（定义：document_id + 物理页 + 归一化摘录被引用 quote 包含）："
        f"{summary['frozen_evidence_containment']['covered']}/"
        f"{summary['frozen_evidence_containment']['groups']} 个证据组命中；"
        f"完整覆盖 {summary['frozen_evidence_containment']['questions_fully_covered']}/"
        f"{summary['frozen_evidence_containment']['answerable_questions']} 道可答题"
        f"（同一规则回算历史运行：{summary['frozen_evidence_containment']['history_questions_fully_covered']}/"
        f"{summary['frozen_evidence_containment']['answerable_questions']}）",
        f"- 契约违规：{len(summary['contract_violations'])} 项",
        f"- 评测基线文件哈希：本次 `{summary['current_benchmark_sha256'][:16]}…`，"
        f"历史 `{summary['history_benchmark_sha256'][:16]}…`，"
        f"{'**不同**' if summary['benchmark_hash_changed'] else '相同'}",
        "",
        "## 逐题结果",
        "",
        "| # | id | 期望可答 | 状态 | 历史状态 | 需求支持 | 引用 | 耗时 s | 历史耗时 s |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, row in enumerate(rows, 1):
        lines.append(
            f"| {index} | {row['id']} | {'是' if row['answerable'] else '否'} | {row['status']} | "
            f"{row['history_status']} | {row['requirements_supported']}/{row['requirements']} | "
            f"{row['citations']} | {row['total_seconds']} | {row['history_wall_seconds']} |"
        )
    lines += ["", "## 状态相对历史的变化", ""]
    if summary["status_changes_vs_history"]:
        for change in summary["status_changes_vs_history"]:
            lines.append(f"- `{change['id']}`：{change['history']} → {change['current']}")
    else:
        lines.append("- 无：36 题状态与 2026-10-28 全量运行完全一致。")
    lines += ["", "## 契约违规", ""]
    if violations:
        for violation in violations:
            lines.append(f"- `{violation['id']}` / {violation['rule']} / {violation['detail']}")
    else:
        lines.append("- 无（状态一致性、引用存在性、文档登记、页码范围、chunk 前缀、重复引用均通过）")
    lines += ["", "## 冻结证据逐题包含情况", "", "| id | 证据组 | 命中 |", "| --- | --- | --- |"]
    for item in containment:
        lines.append(f"| {item['id']} | {item['groups']} | {item['covered']} |")
    lines += [
        "",
        "## 解释边界",
        "",
        "- 本表只评价接口行为（状态、引用、契约）与冻结证据的逐字包含关系，**不评价答案语义是否正确**。",
        "- `answered` 是模型自报状态，不等于人工判定正确。",
        "- 本次无 trace 访问权限，未复核轮次、子集预算与补检索过程。",
        "- 36 题属于开发回归集，不是独立测试集；不得据此宣称泛化性能。",
    ]
    Path(args.out_md).write_text("\n".join(lines) + "\n")
    print(json.dumps({k: summary[k] for k in (
        "statuses", "history_statuses", "citations", "documents_cited",
        "latency_seconds", "history_latency_seconds", "frozen_evidence_containment")},
        ensure_ascii=False, indent=1))
    print("violations:", len(violations), "status_changes:", summary["status_changes_vs_history"])


if __name__ == "__main__":
    main()
