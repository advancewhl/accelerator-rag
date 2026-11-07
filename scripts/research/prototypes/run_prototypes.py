"""Run the three phase-2 prototypes over one dev/val split, or replay a report.

Usage:
  python3 scripts/research/prototypes/run_prototypes.py --split dev --out reports/phase2/dev.json
  python3 scripts/research/prototypes/run_prototypes.py --split val --verify reports/phase2/val.json
"""

from __future__ import annotations

import argparse
import collections
import importlib
import json
from pathlib import Path

import common

PROTOTYPE_MODULES = {
    "s1_connectivity": "p1_cable_cross_table",
    "s2_revision": "p2_manual_revision_align",
    "s3_verification": "p3_requirement_test_claim",
}


def _module_for(scenario: str):
    name = PROTOTYPE_MODULES.get(scenario)
    if name is None:
        raise SystemExit(f"no prototype for scenario: {scenario}")
    return importlib.import_module(name)


def run_split(split: str, facts_path: Path | str = common.DEFAULT_FACTS) -> dict:
    facts = common.load_facts(facts_path)
    questions = [
        item
        for _, item in sorted(common.question_index((split,)).items())
    ]
    reports = []
    for question in questions:
        reason = common.guard_verdict_class(question)
        if reason is not None:
            reports.append(
                common.not_evaluated_report(
                    question,
                    reason,
                    facts_path=facts_path,
                    command=(
                        "python3 scripts/research/prototypes/"
                        f"run_prototypes.py --split {split}"
                    ),
                )
            )
            continue
        module = _module_for(question["scenario"])
        reports.append(module.evaluate(question, facts, facts_path))

    status_counts = collections.Counter(report["status"] for report in reports)
    task_counts: dict[str, collections.Counter] = {}
    for report in reports:
        task_counts.setdefault(report["task_type"], collections.Counter())[
            report["status"]
        ] += 1
    present = sum(
        len(report["gold_alignment"]["present_in_gold"]) for report in reports
    )
    absent = sum(
        len(report["gold_alignment"]["absent_from_gold"]) for report in reports
    )
    return {
        "schema_version": "phase2-prototype-run-v1",
        "split": split,
        "facts_sha256": common.facts_digest(facts_path),
        "question_count": len(reports),
        "status_counts": dict(sorted(status_counts.items())),
        "task_status_counts": {
            task: dict(sorted(counts.items()))
            for task, counts in sorted(task_counts.items())
        },
        "claim_values_in_gold": present,
        "claim_values_absent_from_gold": absent,
        "unsupported": [
            {
                "question_id": report["question_id"],
                "reason": report["unresolved_conditions"],
            }
            for report in reports
            if report["status"] in {"unsupported", "not_evaluated"}
        ],
        "reports": reports,
    }


def _comparable(report: dict) -> dict:
    return {
        "question_id": report["question_id"],
        "status": report["status"],
        "answer": report["answer"],
        "claims": report["claims"],
        "operators": report["operators"],
        "evidence": report["evidence"],
    }


def verify(report_path: Path, facts_path: Path) -> int:
    recorded = json.loads(Path(report_path).read_text(encoding="utf-8"))
    fresh = run_split(recorded["split"], facts_path)
    if recorded.get("facts_sha256") != fresh["facts_sha256"]:
        print("facts digest changed since the recorded run")
        return 1
    old = {item["question_id"]: item for item in recorded["reports"]}
    new = {item["question_id"]: item for item in fresh["reports"]}
    if set(old) != set(new):
        print("question set differs")
        return 1
    for question_id in sorted(old):
        if _comparable(old[question_id]) != _comparable(new[question_id]):
            print(f"report differs: {question_id}")
            return 1
    print(f"replay ok: {len(old)} reports")
    return 0


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=["dev", "val"])
    parser.add_argument("--facts", default=str(common.DEFAULT_FACTS))
    parser.add_argument("--out", default="")
    parser.add_argument("--verify", default="", help="replay a recorded report")
    args = parser.parse_args(argv)
    if args.verify:
        raise SystemExit(verify(Path(args.verify), Path(args.facts)))
    result = run_split(args.split, args.facts)
    if args.out:
        common.write_report(args.out, result)
    print(json.dumps({k: v for k, v in result.items() if k != "reports"}, indent=1))


if __name__ == "__main__":  # pragma: no cover
    main()
