"""Resolve the 10 .doc revision evidence IDs against the local rc.3 snapshot.

The expert review reported that 41 production-build evidence IDs for ten
``.doc`` operation-manual revisions were not found in the older
``kb2-batch-full-20261102-r3`` build.  The phase-3 loader uses the v2 snapshot
``tmp/research-rc3`` instead.  This read-only audit builds the
``revision_id -> chunk_id`` map, checks every review/gold evidence ID, and
replays the affected dev/val questions against the recorded reports.

The output is local-only under ``reports/phase3/``.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.evidence_pack.index import load_index  # noqa: E402
from accelerator_rag.evidence_pack.pipeline import run_question  # noqa: E402

REVISIONS = (
    "shine-control-operation-manual-series-rev-0e94a5e4",
    "shine-control-operation-manual-series-rev-300f0580",
    "shine-control-operation-manual-series-rev-715c251d",
    "shine-control-operation-manual-series-rev-73552d9f",
    "shine-control-operation-manual-series-rev-7da26046",
    "shine-control-operation-manual-series-rev-96ebdc19",
    "shine-control-operation-manual-series-rev-99ecefba",
    "shine-control-operation-manual-series-rev-b9bfd428",
    "shine-control-operation-manual-series-rev-ec081ce3",
    "shine-control-operation-manual-series-rev-f12c9ad8",
)
QUESTIONS = ROOT / "data" / "evaluation" / "research-benchmark-300-v1"
REVIEW = ROOT / "reports" / "expert-review-20261108" / "items.jsonl"
FACTS = ROOT / "data" / "facts" / "facts.jsonl"


def _questions(split: str) -> list[dict]:
    return json.loads(
        (QUESTIONS / split / "questions.json").read_text(encoding="utf-8")
    )["items"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "reports" / "phase3" / "revision-chunk-map.json"))
    args = parser.parse_args(argv)
    indexes = {
        split: load_index(splits=(split,), facts_path=str(FACTS))
        for split in ("dev", "val")
    }
    known_chunks = set()
    by_revision: dict[str, list[str]] = collections.defaultdict(list)
    for index in indexes.values():
        known_chunks.update(index.chunks)
        for chunk_id, chunk in index.chunks.items():
            by_revision[index.revision_of(chunk_id)].append(chunk_id)
    for revision in by_revision:
        by_revision[revision] = sorted(set(by_revision[revision]))

    review_rows = [
        json.loads(line)
        for line in REVIEW.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    review_evidence = collections.defaultdict(list)
    for row in review_rows:
        if row.get("split") not in {"dev", "val"}:
            continue
        for chunk_id in row.get("independent_evidence", ()):
            revision = chunk_id.split(":", 1)[0]
            if revision in REVISIONS:
                review_evidence[revision].append(chunk_id)

    gold_evidence = collections.defaultdict(set)
    affected_questions: list[str] = []
    for split in ("dev", "val"):
        for question in _questions(split):
            revision_ids = {
                item.get("revision_id")
                for item in question["gold"].get("evidence_minimal", ())
            }
            if revision_ids & set(REVISIONS):
                affected_questions.append(question["base_id"])
            for item in question["gold"].get("evidence_minimal", ()):
                if item.get("revision_id") in REVISIONS:
                    gold_evidence[item["revision_id"]].add(item["chunk_id"])

    report = {"revisions": {}, "summary": {}}
    total_review = total_review_missing = 0
    total_gold = total_gold_missing = 0
    for revision in REVISIONS:
        chunks = by_revision.get(revision, [])
        review_ids = review_evidence.get(revision, [])
        review_missing = [chunk_id for chunk_id in review_ids if chunk_id not in known_chunks]
        gold_ids = sorted(gold_evidence.get(revision, ()))
        gold_missing = [chunk_id for chunk_id in gold_ids if chunk_id not in known_chunks]
        total_review += len(review_ids)
        total_review_missing += len(review_missing)
        total_gold += len(gold_ids)
        total_gold_missing += len(gold_missing)
        report["revisions"][revision] = {
            "chunk_count": len(chunks),
            "chunk_ids": chunks,
            "review_evidence": len(review_ids),
            "review_evidence_unique": len(set(review_ids)),
            "review_missing": review_missing,
            "gold_evidence": len(gold_ids),
            "gold_missing": gold_missing,
        }

    recorded = {}
    for split in ("dev", "val"):
        bundle = json.loads(
            (ROOT / "reports" / "phase3" / f"{split}.json").read_text(encoding="utf-8")
        )
        recorded.update({row["question_id"]: row for row in bundle["reports"]})
    replay = {}
    for split in ("dev", "val"):
        index = indexes[split]
        for question in _questions(split):
            if question["base_id"] not in affected_questions:
                continue
            old = recorded.get(question["base_id"])
            if old is None:
                continue
            recompute = {
                key: value
                for key, value in old.get("recompute", {}).items()
                if key != "report_sha256"
            }
            fresh = run_question(
                index,
                question,
                reranker=old.get("reranker", {}).get("name", "none"),
                command=old.get("recompute", {}).get("command", ""),
                recompute=recompute,
                include_baseline=bool(old.get("baseline")),
            )
            replay[question["base_id"]] = {
                "route": fresh["route"],
                "status": fresh["verification"]["status"],
                "pack_tokens": fresh["pack"]["tokens"],
                "report_sha256_match": bool(
                    old and old.get("recompute", {}).get("report_sha256")
                    == fresh["recompute"]["report_sha256"]
                ),
            }
    report["summary"] = {
        "revisions": len(REVISIONS),
        "chunk_ids_total": sum(len(by_revision.get(rev, ())) for rev in REVISIONS),
        "review_evidence": total_review,
        "review_evidence_missing": total_review_missing,
        "gold_evidence": total_gold,
        "gold_evidence_missing": total_gold_missing,
        "affected_questions": len(affected_questions),
        "replayed_questions": len(replay),
        "report_sha256_mismatch": sum(
            not row["report_sha256_match"] for row in replay.values()
        ),
        "status_counts": dict(
            sorted(collections.Counter(row["status"] for row in replay.values()).items())
        ),
        "gold_evidence_missing_list": [
            chunk_id
            for revision in REVISIONS
            for chunk_id in report["revisions"][revision]["gold_missing"]
        ],
        "review_evidence_missing_list": [
            chunk_id
            for revision in REVISIONS
            for chunk_id in report["revisions"][revision]["review_missing"]
        ],
    }
    report["replay"] = replay
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
