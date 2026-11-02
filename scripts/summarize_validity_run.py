"""Summarize a saved 50-question run and its traces without model calls."""

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from accelerator_rag.evaluation.retrieval import normalize_evidence  # noqa: E402
from accelerator_rag.evaluation.validity import Pilot  # noqa: E402


def group_coverage(item, chunk_ids):
    selected = set(chunk_ids)
    return [
        any(selected.intersection(t.chunk_ids) for t in group.alternatives)
        for group in item.evidence_groups
    ]


def summarize(pilot, run, trace_directory):
    if run["execution_status"] != "completed" or len(run["cases"]) != 50:
        raise ValueError("a completed 50-question run is required")
    items = {i.id: i for i in pilot.items}
    if {c["id"] for c in run["cases"]} != items.keys():
        raise ValueError("run question IDs differ from the pilot")
    cases = []
    for case in run["cases"]:
        item = items[case["id"]]
        response = case["response"]
        trace = json.loads(
            (trace_directory / (response["request_id"] + ".json")).read_text()
        )
        if trace["query"] != item.query or trace["response"] != response:
            raise ValueError(f"{item.id}: trace and HTTP response differ")
        first = trace["rounds"][0]
        final = trace["rounds"][trace["selected_round"] - 1]
        chunks = {r["chunk"]["chunk_id"]: r["chunk"] for r in final["results"]}
        anchors = []
        for citation in response["citations"]:
            chunk = chunks[citation["chunk_id"]]
            kind = "section" if Path(chunk["source_path"]).suffix == ".md" else "page"
            anchors.append(
                all(
                    citation[key] == chunk[key]
                    for key in [
                        "document_id",
                        "document_version",
                        "page_start",
                        "page_end",
                    ]
                )
                and citation["locator_kind"] == kind
                and all(
                    normalize_evidence(quote) in normalize_evidence(chunk["text"])
                    for quote in citation["quote"].split("\n\n")
                )
            )
        row = {
            "id": item.id,
            "category": item.category,
            "expected_status": item.expected_status,
            "actual_status": response["status"],
            "status_matches": case["status_matches"],
            "wall_seconds": case["wall_seconds"],
            "model_calls": len(trace["calls"]),
            "model_call_seconds": sum(c["seconds"] for c in trace["calls"]),
            "rounds": len(trace["rounds"]),
            "selected_round": trace["selected_round"],
            "selected_parents": len(chunks),
            "selected_context_tokens": final["subset"]["context_tokens"],
            "citation_count": len(anchors),
            "all_citation_anchors_valid": all(anchors),
            "final_selected_groups": group_coverage(item, chunks),
            "cited_parent_groups": group_coverage(
                item, [c["chunk_id"] for c in response["citations"]]
            ),
        }
        for k in [5, 20]:
            row[f"first_ranked_groups_at_{k}"] = group_coverage(
                item, [r["chunk_id"] for r in first["retrieval"]["ranked"][:k]]
            )
        cases.append(row)
    positives = [c for c in cases if c["expected_status"] == "answered"]
    latency = sorted(c["wall_seconds"] for c in cases)
    metrics = {
        "dataset_revision": pilot.dataset_revision,
        "note": "Development-only. Parent coverage and quote anchoring are not semantic correctness. Human review remains pending.",
        "completed_questions": len(cases),
        "actual_statuses": dict(Counter(c["actual_status"] for c in cases)),
        "status_matches": sum(c["status_matches"] for c in cases),
        "citation_count": sum(c["citation_count"] for c in cases),
        "questions_with_valid_citation_anchors": sum(
            c["all_citation_anchors_valid"] for c in cases
        ),
        "latency_seconds": {
            "total": sum(latency),
            "median": statistics.median(latency),
            "p95_nearest_rank": latency[47],
            "max": max(latency),
        },
        "model_calls": sum(c["model_calls"] for c in cases),
        "model_token_usage": "not recorded by provider; unavailable",
        "two_round_questions": sum(c["rounds"] == 2 for c in cases),
        "max_selected_parents": max(c["selected_parents"] for c in cases),
        "max_selected_context_tokens": max(c["selected_context_tokens"] for c in cases),
        "answerable_retrieval": {
            "denominator": len(positives),
            "first_ranked_complete_at_5": sum(
                all(c["first_ranked_groups_at_5"]) for c in positives
            ),
            "first_ranked_complete_at_20": sum(
                all(c["first_ranked_groups_at_20"]) for c in positives
            ),
            "final_selected_complete": sum(
                all(c["final_selected_groups"]) for c in positives
            ),
            "cited_parents_complete": sum(
                all(c["cited_parent_groups"]) for c in positives
            ),
        },
        "cases": cases,
    }
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--questions",
        type=Path,
        default=ROOT / "data/evaluation/validity-pilot-v2.json",
    )
    args = parser.parse_args()
    pilot = Pilot.model_validate_json(args.questions.read_text())
    run = json.loads((args.run_dir / "http.json").read_text())
    metrics = summarize(pilot, run, args.run_dir / "traces")
    (args.run_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({k: v for k, v in metrics.items() if k != "cases"}, indent=2))


if __name__ == "__main__":
    main()
