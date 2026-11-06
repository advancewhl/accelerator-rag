#!/usr/bin/env python3
"""Compare two 100-question benchmark reports.

Both inputs are the JSON written by ``scripts/kb2_run_regression.py``.  The
comparison is deliberately mechanical: HTTP success, expected-status match,
citation overlap and latency.  It never scores answer semantics.  Per-subset
breakdowns use the ID prefix (P50 / CAB / KB2), because the runner treats the
whole 100-question file as one dataset.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

SUBSETS = {"P50": "old-50", "CAB": "cable-20", "KB2": "kb2-30"}


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def subset_of(case_id: str) -> str:
    return SUBSETS.get(case_id.split("-", 1)[0], "other")


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(fraction * len(ordered))) - 1))
    return ordered[index]


def summarize(report: dict) -> dict:
    cases = report.get("cases", [])
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for case in cases:
        groups[subset_of(case["id"])].append(case)
    groups["all"] = cases

    result = {}
    for name, items in groups.items():
        success = sum(1 for case in items if case.get("success"))
        expected = sum(
            1
            for case in items
            if case.get("response_status")
            == (case.get("expected") or {}).get("status_normalized")
        )
        citing_doc = sum(
            1
            for case in items
            if (case.get("reference_overlap") or {}).get("any_cited_expected_document")
        )
        citing_chunk = sum(
            1
            for case in items
            if (case.get("reference_overlap") or {}).get("any_cited_expected_chunk")
        )
        with_expected = sum(
            1
            for case in items
            if ((case.get("reference_overlap") or {}).get("expected_chunk_count") or 0) > 0
        )
        latencies = [
            case["elapsed_seconds"]
            for case in items
            if isinstance(case.get("elapsed_seconds"), (int, float))
        ]
        result[name] = {
            "total": len(items),
            "http_success": success,
            "http_success_rate": round(success / len(items), 4) if items else None,
            "expected_status_match": expected,
            "expected_status_match_rate": (
                round(expected / len(items), 4) if items else None
            ),
            "with_expected_evidence": with_expected,
            "cites_expected_document": citing_doc,
            "cites_expected_chunk": citing_chunk,
            "p50_seconds": percentile(latencies, 0.50),
            "p95_seconds": percentile(latencies, 0.95),
        }
    return result


def changed_cases(baseline: dict, candidate: dict) -> list[dict]:
    base_by_id = {case["id"]: case for case in baseline.get("cases", [])}
    changes = []
    for case in candidate.get("cases", []):
        before = base_by_id.get(case["id"])
        if before is None:
            continue
        before_state = (
            before.get("outcome"),
            before.get("response_status"),
            (before.get("reference_overlap") or {}).get("any_cited_expected_chunk"),
        )
        after_state = (
            case.get("outcome"),
            case.get("response_status"),
            (case.get("reference_overlap") or {}).get("any_cited_expected_chunk"),
        )
        if before_state != after_state:
            changes.append(
                {
                    "id": case["id"],
                    "subset": subset_of(case["id"]),
                    "category": case.get("category"),
                    "before": {
                        "outcome": before_state[0],
                        "status": before_state[1],
                        "cites_expected_chunk": before_state[2],
                    },
                    "after": {
                        "outcome": after_state[0],
                        "status": after_state[1],
                        "cites_expected_chunk": after_state[2],
                    },
                }
            )
    return changes


def render_markdown(payload: dict) -> str:
    lines = [
        "# 100 题对照：rc.3 候选 vs rc.2 生产",
        "",
        f"生成时间：{payload['generated_at']}",
        "",
        "> 工程指标，不是语义准确率。`expected_status_match` 只比较接口状态与预期标签。",
        "",
        "| 子集 | 题数 | HTTP 成功 | 状态匹配 | 引用命中父块 | P50 (s) | P95 (s) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in ("all", "old-50", "cable-20", "kb2-30"):
        for side in ("baseline", "candidate"):
            row = payload[side]["summary"].get(name)
            if row is None:
                continue
            lines.append(
                f"| {name} · {side} | {row['total']} | "
                f"{row['http_success']}/{row['total']} | "
                f"{row['expected_status_match']}/{row['total']} | "
                f"{row['cites_expected_chunk']}/{row['with_expected_evidence']} | "
                f"{row['p50_seconds']} | {row['p95_seconds']} |"
            )
    lines.extend(["", "## 结果变化", ""])
    changes = payload["changed_cases"]
    if not changes:
        lines.append("没有用例的结果、状态或引用命中发生变化。")
    else:
        lines.append("| 题号 | 子集 | 之前 | 之后 |")
        lines.append("| --- | --- | --- | --- |")
        for change in changes:
            before = change["before"]
            after = change["after"]
            lines.append(
                f"| {change['id']} | {change['subset']} | "
                f"{before['outcome']}/{before['status']}/chunk={before['cites_expected_chunk']} | "
                f"{after['outcome']}/{after['status']}/chunk={after['cites_expected_chunk']} |"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, default=None)
    args = parser.parse_args()

    baseline = load(args.baseline)
    candidate = load(args.candidate)
    payload = {
        "generated_at": candidate.get("generated_at"),
        "baseline": {
            "path": str(args.baseline),
            "summary": summarize(baseline),
        },
        "candidate": {
            "path": str(args.candidate),
            "summary": summarize(candidate),
        },
        "changed_cases": changed_cases(baseline, candidate),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path = args.markdown or args.output.with_suffix(".md")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
