"""Validate/run exactly 50 source-bound dev questions, keeping gold outside HTTP."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from accelerator_rag.evaluation.validity import (  # noqa: E402
    Pilot,
    evidence_coverage,
    load_corpus,
    validate_pilot,
)
from accelerator_rag.retrieval.bm25 import BM25Retriever  # noqa: E402


def run_http(client, pilot, save):
    """Readiness is checked before questions; expected answers never leave client."""
    catalog_response = client.get("/v1/rag/documents")
    catalog_response.raise_for_status()
    catalog = catalog_response.json()
    available = {d["document_id"]: d for d in catalog["documents"]}
    expected = {
        (t.document_id, t.document_version)
        for item in pilot.items
        for group in item.evidence_groups
        for t in group.alternatives
    }
    missing = [
        f"{doc}@{version}"
        for doc, version in sorted(expected)
        if doc not in available
        or version not in available[doc]["versions"]
        or not available[doc]["original_available"]
    ]
    if missing:
        raise ValueError(f"candidate corpus not ready: {missing}")
    rows = []
    for item in pilot.items:
        start = perf_counter()
        response = client.post("/v1/rag/answer", json={"query": item.query})
        response.raise_for_status()
        data = response.json()
        rows.append(
            {
                "id": item.id,
                "response": data,
                "wall_seconds": perf_counter() - start,
                "status_matches": data["status"] == item.expected_status,
                "semantic_grade": None,
            }
        )
        save(rows, catalog)
        print(item.id, data["status"], flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--questions",
        type=Path,
        default=ROOT / "data/evaluation/validity-pilot-v2.json",
    )
    parser.add_argument("--pdf-root", type=Path, default=ROOT)
    parser.add_argument(
        "--mode", choices=["validate", "bm25", "http"], default="validate"
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:18003")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pilot = Pilot.model_validate_json(args.questions.read_text())
    documents, chunks = load_corpus(ROOT, args.pdf_root)
    validate_pilot(pilot, documents, chunks)
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "dataset_revision": pilot.dataset_revision,
        "questions": str(args.questions),
        "question_count": len(pilot.items),
        "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "worktree_status": subprocess.check_output(
            ["git", "status", "--short"], cwd=ROOT, text=True
        ),
        "frozen_code": False,
        "source_validation": "passed",
        "documents": [
            {
                "document_id": d.record.doc_id,
                "version": d.record.version,
                "format": d.record.document_type,
                "sections_or_pages": d.parsed.page_count,
            }
            for d in documents
        ],
        "eligible_chunks": len(chunks),
        "categories": dict(Counter(i.category for i in pilot.items)),
        "expected_statuses": dict(Counter(i.expected_status for i in pilot.items)),
        "human_semantic_review": "pending; no answer accuracy measured",
        "cases": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def write():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    if args.mode == "bm25":
        retriever = BM25Retriever(chunks)
        for item in pilot.items:
            start = perf_counter()
            hits = retriever.search(item.query, top_k=20)
            row = {
                "id": item.id,
                "category": item.category,
                "expected_status": item.expected_status,
                "wall_seconds": perf_counter() - start,
                "hits": [
                    {
                        "rank": h.rank,
                        "score": h.score,
                        "chunk_id": h.chunk.chunk_id,
                        "document_id": h.chunk.document_id,
                        "document_version": h.chunk.document_version,
                        "page_start": h.chunk.page_start,
                    }
                    for h in hits
                ],
            }
            for k in [5, 20]:
                covered = evidence_coverage(item, [h.chunk for h in hits[:k]])
                row[f"groups_at_{k}"] = covered
                row[f"complete_at_{k}"] = all(covered)
            report["cases"].append(row)
        positives = [r for r in report["cases"] if r["expected_status"] == "answered"]
        report["retrieval_summary"] = {
            "note": "BM25 pipeline diagnosis only; source coverage is not answer correctness. Partial/insufficient cases excluded from main denominator.",
            "answerable_denominator": len(positives),
            "complete_at_5": sum(r["complete_at_5"] for r in positives),
            "complete_at_20": sum(r["complete_at_20"] for r in positives),
            "by_category": {
                category: {
                    "n": len(
                        rows := [
                            r for r in report["cases"] if r["category"] == category
                        ]
                    ),
                    "complete_at_5": sum(r["complete_at_5"] for r in rows),
                    "complete_at_20": sum(r["complete_at_20"] for r in rows),
                }
                for category in report["categories"]
            },
        }
    elif args.mode == "http":
        if httpx.URL(args.base_url).host not in {
            "127.0.0.1",
            "localhost",
            "10.101.9.190",
        }:
            raise ValueError("use the existing group service or its local candidate")
        report["base_url"] = args.base_url
        report["model_and_index_identity"] = (
            "unverified; attach candidate config and server traces before comparison"
        )

        def save(rows, catalog):
            report.update(cases=rows, live_catalog=catalog)
            write()

        try:
            with httpx.Client(
                base_url=args.base_url,
                trust_env=False,
                timeout=httpx.Timeout(180, connect=8),
            ) as client:
                run_http(client, pilot, save)
        except (httpx.HTTPError, ValueError) as exc:
            report.update(execution_status="blocked", error=str(exc))
            write()
            print(
                f"HTTP run blocked after {len(report['cases'])} completed questions: {exc}"
            )
            return 1
    report["execution_status"] = "completed"
    write()
    # A blank review sheet is not an automatic semantic score.
    review = [
        {
            "id": i.id,
            "question": i.query,
            "gold_answer": i.gold_answer,
            "must_cover": i.must_cover,
            "forbidden_claims": i.forbidden_claims,
            "evidence_groups": [g.model_dump() for g in i.evidence_groups],
            "reviewer": None,
            "strict_correct": None,
            "condition_complete": None,
            "unsupported_claim": None,
            "citation_supported": None,
            "failure_stage": None,
            "notes": None,
        }
        for i in pilot.items
    ]
    args.output.with_suffix(".review.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k
                in {
                    "question_count",
                    "source_validation",
                    "eligible_chunks",
                    "categories",
                    "retrieval_summary",
                }
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
