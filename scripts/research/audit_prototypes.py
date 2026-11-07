"""Replay every operator recorded in the phase-2 prototype reports.

For each report this audit checks:

* ``operators`` entries have the ``{op, request, response}`` shape and
  ``run_operator(op, request)`` reproduces ``response`` exactly;
* every evidence entry without a ``fact_id`` quotes the cited chunk verbatim;
* ``recompute`` pins the current facts, question file and corpus snapshot.

It is deliberately independent of ``run_prototypes.py --verify``: that command
re-runs the prototype code and compares five fields, but never replays the
recorded operator requests.

Usage:
  python3 scripts/research/audit_prototypes.py \
      --dev reports/phase2/dev.json --val reports/phase2/val.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts" / "research" / "prototypes") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "research" / "prototypes"))

import common  # noqa: E402
from accelerator_rag.facts.corpus import load_scope  # noqa: E402
from accelerator_rag.verify.operators import run_operator  # noqa: E402

DEFAULT_REPORTS = {
    "dev": ROOT / "reports" / "phase2" / "dev.json",
    "val": ROOT / "reports" / "phase2" / "val.json",
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", default=str(DEFAULT_REPORTS["dev"]))
    parser.add_argument("--val", default=str(DEFAULT_REPORTS["val"]))
    parser.add_argument("--facts", default=str(common.DEFAULT_FACTS))
    args = parser.parse_args(argv)

    scope = load_scope(("dev", "val"))
    chunk_text = scope.chunk_text()
    facts_sha = common.facts_digest(args.facts)
    corpus_sha = common.corpus_digest()

    problems: list[str] = []
    checked_ops = 0
    checked_evidence = 0
    for split, path in (("dev", args.dev), ("val", args.val)):
        bundle = json.loads(Path(path).read_text(encoding="utf-8"))
        questions_sha = common.questions_digest(split)
        for report in bundle["reports"]:
            qid = report["question_id"]
            recompute = report.get("recompute", {})
            if recompute.get("facts_sha256") != facts_sha:
                problems.append(f"{qid}: facts_sha256 is stale")
            if recompute.get("questions_sha256") != questions_sha:
                problems.append(f"{qid}: questions_sha256 is stale")
            if recompute.get("corpus_snapshot") != corpus_sha:
                problems.append(f"{qid}: corpus_snapshot is stale")
            for record in report.get("operators", []):
                if set(record) != {"op", "request", "response"}:
                    problems.append(f"{qid}: operator record shape {sorted(record)}")
                    continue
                checked_ops += 1
                replay = run_operator(record["op"], record["request"])
                if replay != record["response"]:
                    problems.append(f"{qid}: {record['op']} does not replay")
            for entry in report.get("evidence", []):
                if entry.get("fact_id"):
                    continue
                checked_evidence += 1
                cid = entry.get("chunk_id", "")
                excerpt = entry.get("excerpt", "")
                if cid not in chunk_text or excerpt not in chunk_text[cid]:
                    problems.append(
                        f"{qid}: evidence not verbatim in {cid[-12:]}"
                    )

    print(
        f"reports=dev+val operators={checked_ops} "
        f"evidence={checked_evidence} problems={len(problems)}"
    )
    for problem in problems[:20]:
        print(f"  {problem}")
    return 1 if problems else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
