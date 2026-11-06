#!/usr/bin/env python3
"""Merge benchmark cases from a targeted rerun into a full report.

The 100-question file contains 70 questions that use the default retrieval
scope and 30 that carry an explicit version scope.  When only the 30 scoped
questions are rerun, this script replaces those cases in the full report and
recomputes the aggregate counters, so the comparison sees one 100-case set.

Usage::

    python scripts/merge_benchmark_runs.py \
        --base reports/.../rc3-candidate.json \
        --override reports/.../rc3-candidate-scoped30.json \
        --output reports/.../rc3-candidate-final.json
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def summarize(cases: list[dict]) -> dict:
    outcomes = collections.Counter(case.get("outcome") for case in cases)
    statuses = collections.Counter(
        case.get("response_status") for case in cases if case.get("response_status")
    )
    return {
        "total": len(cases),
        "success": sum(1 for case in cases if case.get("success")),
        "failures": sum(1 for case in cases if not case.get("success")),
        "http_errors": outcomes.get("http_error", 0),
        "timeouts": outcomes.get("timeout", 0),
        "outcome_distribution": dict(sorted(outcomes.items())),
        "status_distribution": dict(sorted(statuses.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--override", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    base = load(args.base)
    override = load(args.override)
    overrides = {case["id"]: case for case in override.get("cases", [])}
    if not overrides:
        raise SystemExit("override report has no cases")

    merged = []
    replaced = []
    for case in base.get("cases", []):
        replacement = overrides.get(case["id"])
        if replacement is not None:
            merged.append(replacement)
            replaced.append(case["id"])
        else:
            merged.append(case)

    missing = sorted(set(overrides) - {case["id"] for case in base.get("cases", [])})
    payload = {
        "schema_version": base.get("schema_version"),
        "tool": base.get("tool"),
        "generated_at": override.get("generated_at"),
        "base_report": str(args.base),
        "override_report": str(args.override),
        "replaced_case_ids": replaced,
        "override_ids_not_in_base": missing,
        "totals": summarize(merged),
        "cases": merged,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "replaced": len(replaced),
                "missing": missing,
                "totals": payload["totals"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
