"""Offline source validation and rejudgment of frozen Stage 2.7 rankings.

Run: python -m accelerator_rag.evaluation.evidence_audit
No model, encoder, retriever, or vector-store instance is constructed.
"""

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from accelerator_rag.corpus.eligibility import eligibility_audit
from accelerator_rag.evaluation.manual_review import (
    apply_manual_review,
    load_manual_review,
    measurement_rankings,
)
from accelerator_rag.evaluation.model_comparison import (
    complementarity,
    markdown as stage27_markdown,
    pairwise,
)
from accelerator_rag.evaluation.retrieval import (
    EvidenceTarget,
    load_queries,
    target_matches,
    normalize_evidence,
    ranking_sha256,
    rejudge,
)
from accelerator_rag.ingestion import IngestionService
from accelerator_rag.domain.knowledge import KnowledgeChunk
from accelerator_rag.retrieval.index_contract import DenseIndexContract


def file_sha(path):
    with path.open("rb") as stream:
        digest = sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_revision(v1, v2, audit):
    """Alternatives may grow; question semantics and existing targets cannot change."""
    if (
        v1["judgment_revision"] != "evidence-contract-v1"
        or v2["judgment_revision"] != "evidence-contract-v2"
    ):
        raise ValueError("expected evidence-contract-v1 -> evidence-contract-v2")
    if len(v1["queries"]) != len(v2["queries"]):
        raise ValueError("query count changed")
    records = {r["query_id"]: r for r in audit["records"]}
    expected = {q["id"] for q in v1["queries"] if q["answerable"]}
    if set(records) != expected or len(records) != len(audit["records"]):
        raise ValueError("every answerable query needs exactly one audit record")
    added = {}
    for old, new in zip(v1["queries"], v2["queries"], strict=True):
        if {k: v for k, v in old.items() if k != "evidence_groups"} != {
            k: v for k, v in new.items() if k != "evidence_groups"
        } or len(old["evidence_groups"]) != len(new["evidence_groups"]):
            raise ValueError("question metadata or required groups changed")
        declared = []
        for i, (a, b) in enumerate(
            zip(old["evidence_groups"], new["evidence_groups"], strict=True)
        ):
            if b["alternatives"][: len(a["alternatives"])] != a["alternatives"]:
                raise ValueError("original alternatives changed")
            for t in b["alternatives"][len(a["alternatives"]) :]:
                declared.append((i, t))
        if old["answerable"]:
            r = records[old["id"]]
            if r["current_evidence_groups"] != old["evidence_groups"]:
                raise ValueError("audit original groups differ")
            if declared != [
                (x["group_index"], x["target"])
                for x in sorted(
                    r["accepted_new_alternatives"], key=lambda x: x["group_index"]
                )
            ]:
                raise ValueError("accepted audit alternatives differ from v2")
            added[old["id"]] = len(declared)
    return added


def markdown(report):
    lines = [
        "# RAG Stage 2.7.1：索引契约与证据审核",
        "",
        "本轮只验证源证据并重判已保存的 Top-5。所有小样本指标仅用于诊断。",
        "",
        "## Dense index contract",
        "",
        "每个 point 保存完整 contract 与 dense_index_contract_id。初始化绑定模型指纹和 passage policy；非空 collection 在读取、写入、删除前完整扫描，search 在 query encoding 前验证。不匹配或缺少签名均拒绝，要求新 collection 或完整重建。模型指纹按加载实例缓存。",
        "",
        "contract 包含：requested model、weights manifest、model config、encoding config、tokenizer、query template、document prefix/template、dimension、max sequence length、normalization、distance、passage contract ID/algorithm。路径、batch、线程和耗时不参与身份。",
        "",
        "持久化测试覆盖同 contract 更新 A 时 B 的 vector/payload 不变、不同 passage policy 零写入拒绝、768 维不同模型在 query encode 前拒绝，以及 reopen 后继续拒绝。历史 Stage 2.7 索引未加签、未打开，保留只读 measurement；正式 runtime 拒绝无签名的历史 payload。",
        "",
    ]
    for name, row in report["dense_index_contracts"].items():
        lines += [f"- `{name}`：`{row['dense_index_contract_id']}`。"]
    a = report["audit_summary"]
    lines += [
        "",
        "## Evidence contract v1 → v2",
        "",
        f"审核 {a['audited_queries']}/21 条可回答问题，每条搜索全部 13 份 PDF。原有 {a['old_alternatives']} 个 alternatives，新增 {a['added_alternatives']} 个，修订后共 {a['new_alternatives']} 个。{a['changed_queries']} 条问题新增证据。查询文本、数量、类别、语言与 group 的 AND/OR 语义保持不变。",
        "",
        report["audit"]["method"],
        "",
        "问题 | 新增 alternatives | 审核说明",
        "--- | ---: | ---",
    ]
    for r in report["audit"]["records"]:
        lines += [
            f"{r['query_id']} | {len(r['accepted_new_alternatives'])} | {r['audit_note']}"
        ]
    lines += [
        "",
        "逐条原始 groups、术语搜索、宽 BM25 候选、物理页、接受/拒绝原因及合法 canonical chunk ID 见同名 JSON。审核依据源文本，未以模型命中作为接受条件。候选召回不构成全语料不存在其他改写的数学证明。",
        "",
        "## 重判指标",
        "",
        "Retriever | v1 Hit@1/3/5 | v2 Hit@1/3/5 | v1 MRR@5 | v2 MRR@5",
        "--- | --- | --- | ---: | ---:",
    ]
    for name, row in report["metrics_comparison"].items():
        a, b = row["v1"], row["v2"]
        h1 = "/".join(f"{a[k]:.4f}" for k in ("Hit@1", "Hit@3", "Hit@5"))
        h2 = "/".join(f"{b[k]:.4f}" for k in ("Hit@1", "Hit@3", "Hit@5"))
        lines += [f"{name} | {h1} | {h2} | {a['MRR@5']:.4f} | {b['MRR@5']:.4f}"]
    lines += ["", "### 判断变化", ""]
    for name, changes in report["changed_judgments"].items():
        lines += [
            f"- {name}："
            + (
                "；".join(
                    f"`{c['query_id']}` 完整首次排名 {c['v1_first_complete_rank']} → {c['v2_first_complete_rank']}，Top-5 groups {c['v1_groups']} → {c['v2_groups']}"
                    for c in changes
                )
                or "无变化"
            )
            + "。"
        ]
    lines += ["", "## E5 与 BM25 互补性", ""]
    comp = report["complementarity"]["intfloat/multilingual-e5-base"]
    for key, ids in comp["query_ids"].items():
        lines += [
            f"- {key}（{len(ids)}）："
            + ("、".join(f"`{x}`" for x in ids) or "无")
            + "。"
        ]
    lines += [
        "",
        "## 跨语言证据覆盖",
        "",
        "Retriever | 问题 | Top-5 满足 group | 完整覆盖",
        "--- | --- | --- | ---",
    ]
    for name, cases in report["cross_language"].items():
        for c in cases:
            lines += [
                f"{name} | {c['query_id']} | {c['satisfied_groups']}/{c['required_groups']}（{c['group_indices']}） | {c['complete']}"
            ]
    lines += [
        "",
        "## 排名完整性与可复现性",
        "",
        "0 embeddings recomputed；0 document vectors changed；全部 Stage 2.7 Top-5 排名、父 Chunk payload、score 和完整 passage_trace 的 canonical SHA-256 前后一致。JSON 包含每个 retriever 的摘要、历史 SQLite 文件摘要及完整重判 cases。",
        "",
        "passage_trace 中的 matched_evidence / matched_evidence_groups 保留 v1 历史注释，不代表 v2 判断；v2 first_complete_passage_rank 单独重算。",
        "",
        "measurement + v1/v2 ground truth + 人工 review artifact 可离线重建报告。Stage 2.7 Markdown 已在临时目录逐字重建并比对摘要，历史文件不修改。",
        "",
        "## 最终判断",
        "",
        report["recommendation"],
        "",
        "## 验证",
        "",
        *[f"- {x}" for x in report.get("validation", [])],
        "",
    ]
    return "\n".join(lines)


def run(root: Path):
    data = root / "data/evaluation"
    source = root / "reports/rag-stage-two-seven-embedding-comparison.json"
    old = json.loads(source.read_text())
    audit = json.loads((data / "stage271-evidence-audit.json").read_text())
    review = load_manual_review(data / "stage27-manual-review.json")
    decision = json.loads((data / "stage271-manual-review.json").read_text())
    v1path, v2path = (
        data / "retrieval-baseline-v1.json",
        data / "retrieval_baseline.json",
    )
    v1, v2 = [json.loads(p.read_text()) for p in (v1path, v2path)]
    added = validate_revision(v1, v2, audit)
    protected = decision["protected_historical_files"]
    for name, digest in protected.items():
        if file_sha(root / name) != digest:
            raise ValueError(f"historical file changed: {name}")
    for source_path, digest in old["metadata"]["source_sha256"].items():
        if file_sha(root / source_path) != digest:
            raise ValueError(f"frozen raw PDF changed: {source_path}")
    docs = IngestionService(root).ingest_all_registered_pdfs()
    chunks, _ = eligibility_audit([c for d in docs for c in d.chunks])
    if len(docs) != 13:
        raise ValueError("frozen audit requires 13 PDFs")
    all_docs = {d.record.doc_id for d in docs}
    for r in audit["records"]:
        if set(r["searched_documents"]) != all_docs:
            raise ValueError("audit must search every document per query")
        for accepted in r["accepted_new_alternatives"]:
            t = accepted["target"]
            ids = [
                c.chunk_id
                for c in chunks
                if c.document_id == t["document_id"]
                and c.page_start <= t["page"] <= c.page_end
                and normalize_evidence(t["excerpt"]) in normalize_evidence(c.text)
            ]
            if sorted(ids) != sorted(accepted["eligible_chunk_ids"]):
                raise ValueError("accepted canonical chunk provenance changed")
    queries1 = load_queries(v1path, docs, eligible_chunks=chunks)
    queries2 = load_queries(v2path, docs, eligible_chunks=chunks)
    measurements = {
        "BM25": old["bm25"],
        **{name: row["evaluation"] for name, row in old["models"].items()},
    }
    judged, integrity, changed = {}, {}, {}
    for name, ev in measurements.items():
        check1 = rejudge(ev["cases"], queries1)
        if check1["metrics"] != ev["metrics"]:
            raise ValueError("v1 stored measurement does not reproduce")
        new = rejudge(ev["cases"], queries2)
        judged[name] = new
        integrity[name] = {
            "before": ranking_sha256(ev["cases"]),
            "after": ranking_sha256(new["cases"]),
            "equal": ranking_sha256(ev["cases"]) == ranking_sha256(new["cases"]),
        }
        changed[name] = [
            {
                "query_id": a["id"],
                "v1_first_complete_rank": a["first_complete_rank"],
                "v2_first_complete_rank": b["first_complete_rank"],
                "v1_groups": a["groups_satisfied_at_k"]["5"],
                "v2_groups": b["groups_satisfied_at_k"]["5"],
            }
            for a, b in zip(ev["cases"], new["cases"], strict=True)
            if a["first_complete_rank"] != b["first_complete_rank"]
            or a["groups_satisfied_at_k"] != b["groups_satisfied_at_k"]
            or [x["judged_relevant"] for x in a["results"]]
            != [x["judged_relevant"] for x in b["results"]]
        ]
    rebuilt = stage27_markdown(apply_manual_review(old, review))
    historical_md = source.with_suffix(".md")
    if rebuilt != historical_md.read_text():
        raise ValueError("manual review does not reproduce Stage 2.7 Markdown")
    tmp = root / "tmp/stage-two-seven-one"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "regenerated-stage27.md").write_text(rebuilt)
    contracts = {}
    for name, row in old["models"].items():
        contract = DenseIndexContract.from_fingerprint(
            row["fingerprint"], row["passage_statistics"]["contract"]
        )
        contracts[name] = {
            "dense_index_contract_id": contract.contract_id,
            "fields": asdict(contract),
            "historical_collection": row["collection"],
            "policy": "historical read-only; unsigned payloads rejected by formal runtime",
        }
    cross = {}
    for name, ev in judged.items():
        cross[name] = [
            {
                "query_id": c["id"],
                "required_groups": len(c["evidence_groups"]),
                "satisfied_groups": c["groups_satisfied_at_k"]["5"],
                "group_indices": [
                    i
                    for i, g in enumerate(c["evidence_groups"])
                    if any(
                        target_matches(
                            KnowledgeChunk(**r["chunk"]), EvidenceTarget(**t)
                        )
                        for r in c["results"]
                        for t in g["alternatives"]
                    )
                ],
                "complete": c["first_complete_rank"] is not None,
            }
            for c in ev["cases"]
            if c["answerable"] and c["language_relation"] == "cross_language"
        ]

    def count(value):
        return sum(
            len(g["alternatives"])
            for q in value["queries"]
            for g in q["evidence_groups"]
        )

    report = {
        "stage": "2.7.1",
        "judgment_revision": "evidence-contract-v2",
        "dense_index_contracts": contracts,
        "dense_contract_verification": decision["dense_contract_verification"],
        "audit_summary": {
            "audited_queries": len(added),
            "documents_per_query": len(docs),
            "changed_queries": sum(n > 0 for n in added.values()),
            "old_alternatives": count(v1),
            "added_alternatives": sum(added.values()),
            "new_alternatives": count(v2),
            "added_per_query": added,
        },
        "audit": audit,
        "metrics_comparison": {
            name: {"v1": measurements[name]["metrics"], "v2": ev["metrics"]}
            for name, ev in judged.items()
        },
        "changed_judgments": changed,
        "complementarity": {
            name: complementarity(judged["BM25"], ev)
            for name, ev in judged.items()
            if name != "BM25"
        },
        "pairwise": pairwise(judged),
        "cross_language": cross,
        "ranking_integrity": integrity,
        "embeddings_recomputed": 0,
        "document_vectors_changed": 0,
        "historical_files_sha256": protected,
        "stage27_markdown_reproduced": file_sha(historical_md),
        "measurement_rankings_sha256": measurement_rankings(old),
        "source_files_sha256": {
            str(p.relative_to(root)): file_sha(p)
            for p in (
                source,
                v1path,
                v2path,
                data / "stage271-evidence-audit.json",
                data / "stage27-manual-review.json",
                data / "stage271-manual-review.json",
            )
        },
        "code_sha256": {
            str(p.relative_to(root)): file_sha(p)
            for p in sorted((root / "src/accelerator_rag").rglob("*.py"))
            if p.parts[-2] in {"evaluation", "retrieval", "storage"}
        },
        "raw_pdf_sha256": {
            d.record.doc_id: file_sha(root / d.record.source_path) for d in docs
        },
        "recommendation": decision["recommendation"],
        "validation": decision["validation"],
        "passage_trace_note": "Entire passage_trace is frozen v1 provenance; only case-level first_complete_passage_rank is rejudged.",
        "rejudged": judged,
    }
    for name, digest in protected.items():
        if file_sha(root / name) != digest:
            raise RuntimeError(f"offline audit modified historical file: {name}")
    destination = root / "reports/rag-stage-two-seven-one-evidence-audit"
    destination.with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    destination.with_suffix(".md").write_text(markdown(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = run(args.project_root.resolve())
    print(
        json.dumps(
            {
                "audit_summary": report["audit_summary"],
                "metrics": report["metrics_comparison"],
                "cross_language": report["cross_language"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
