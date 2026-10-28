import gzip
import hashlib
import json
from pathlib import Path
import statistics

from accelerator_rag.evaluation.retrieval import normalize_evidence

root = Path("reports/rag-framework-20261028")
benchmark = Path("data/evaluation/retrieval_baseline.json")
questions = {q["id"]: q for q in json.loads(benchmark.read_text())["queries"]}
registry = json.loads(Path("data/documents/registry.json").read_text())
by_title = {d["title"]: d for d in registry}
assert len(by_title) == len(registry)
http = json.loads((root / "http-results.json").read_text())
traces = {
    t["request_id"]: t
    for t in json.load(gzip.open(root / "request-traces.json.gz", "rt"))
}


def covered(records, question):
    satisfied = set()
    for i, group in enumerate(question["evidence_groups"]):
        for target in group["alternatives"]:
            for record in records:
                docid = record.get("document_id")
                if docid is None:
                    docid = by_title[record["document_title"]]["doc_id"]
                if (
                    docid == target["document_id"]
                    and record["page_start"] <= target["page"] <= record["page_end"]
                    and normalize_evidence(target["excerpt"])
                    in normalize_evidence(record["text"])
                ):
                    satisfied.add(i)
    return sorted(satisfied)


rows = []
for case in http["cases"]:
    q = questions.get(case["id"])
    if not q or not q["answerable"]:
        continue
    assert q["query"] == case["query"] and q["judgment_mode"] == "all"
    trace = traces[case["response"]["request_id"]]
    first = trace["rounds"][0]["candidates"]
    chosen = trace["rounds"][trace["selected_round"] - 1]
    selected = [h["chunk"] for h in chosen["results"]]
    all_candidates = [
        r for round_row in trace["rounds"] for r in round_row["candidates"]
    ]
    n = len(q["evidence_groups"])
    complete_rank = next(
        (k for k in range(1, len(first) + 1) if len(covered(first[:k], q)) == n), None
    )
    first_relevant_rank = next(
        (k for k in range(1, len(first) + 1) if covered(first[:k], q)), None
    )
    rows.append(
        {
            "id": q["id"],
            "groups": n,
            "first_round": {str(k): covered(first[:k], q) for k in (1, 3, 5, 10, 20)},
            "first_complete_rank": complete_rank,
            "first_relevant_rank": first_relevant_rank,
            "all_round_candidates": covered(all_candidates, q),
            "selected_subset": covered(selected, q),
            "quoted": covered(
                [dict(c, text=c["quote"]) for c in case["response"]["citations"]], q
            ),
        }
    )


def aggregate(stage):
    counts = [len(stage(r)) for r in rows]
    return {
        "evidence_groups_recovered": sum(counts),
        "evidence_groups_total": sum(r["groups"] for r in rows),
        "micro_group_recall": sum(counts) / sum(r["groups"] for r in rows),
        "macro_group_recall": statistics.mean(
            len(stage(r)) / r["groups"] for r in rows
        ),
        "complete_questions": sum(c == r["groups"] for c, r in zip(counts, rows)),
        "questions": len(rows),
    }


result = {
    "dataset": {
        "questions": len(rows),
        "evidence_groups": sum(r["groups"] for r in rows),
        "source_benchmark_sha256": hashlib.sha256(benchmark.read_bytes()).hexdigest(),
        "trace_archive_sha256": hashlib.sha256(
            (root / "request-traces.json.gz").read_bytes()
        ).hexdigest(),
        "code_scope": "36-case HTTP run before the final version-scope and numeric-normalization fixes; not a full run of the final code",
    },
    "first_round": {
        str(k): aggregate(lambda r: r["first_round"][str(k)]) for k in (1, 3, 5, 10, 20)
    },
    "mrr_first_relevant_at_5": statistics.mean(
        1 / r["first_relevant_rank"]
        if r["first_relevant_rank"] is not None and r["first_relevant_rank"] <= 5
        else 0
        for r in rows
    ),
    "mrr_complete_at_5": statistics.mean(
        1 / r["first_complete_rank"]
        if r["first_complete_rank"] is not None and r["first_complete_rank"] <= 5
        else 0
        for r in rows
    ),
    "all_round_candidates": aggregate(lambda r: r["all_round_candidates"]),
    "selected_subset": aggregate(lambda r: r["selected_subset"]),
    "quoted": aggregate(lambda r: r["quoted"]),
    "cases": rows,
    "limitations": [
        "Recall refers to frozen evidence groups with literal excerpt matching, not exhaustive relevant corpus chunks.",
        "The benchmark is small and has been used for development; it is not an unseen holdout.",
        "Selected subset and quotation coverage do not prove answer entailment or completeness.",
    ],
}
legacy_path = Path("reports/rag-stage-two-eight-two-reranking.json")
legacy = json.loads(legacy_path.read_text())
assert (
    legacy["frozen_sha256"][str(benchmark)]
    == result["dataset"]["source_benchmark_sha256"]
)
result["historical_reference"] = {
    "path": str(legacy_path),
    "same_benchmark_verified": True,
    "metrics": legacy["evaluations"]["E5 + Qwen3 + Reranker"]["overall"],
    "comparison_limit": "Historical CPU offline run versus production GPU workflow with changed candidate generation and full-parent reranking; not a paired rerun in one environment.",
}
assert len(rows) == 21 and result["dataset"]["evidence_groups"] == 35
review = json.loads((root / "independent-review.json").read_text())
assert (
    result["selected_subset"]["complete_questions"]
    == review["selected_parent_frozen_target_complete"]
)
assert result["quoted"]["complete_questions"] == review["quoted_frozen_target_complete"]
(root / "retrieval-metrics.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n"
)
print(
    json.dumps(
        {k: v for k, v in result.items() if k != "cases"}, ensure_ascii=False, indent=2
    )
)
