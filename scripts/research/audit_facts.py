"""Audit a built phase-2 fact set against the frozen rc.3 snapshot.

Usage:
  python3 scripts/research/audit_facts.py --facts data/facts/facts.jsonl
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.facts.corpus import load_scope  # noqa: E402
from accelerator_rag.facts.schema import (  # noqa: E402
    UNKNOWN,
    FactSet,
    check_citations,
)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", default="data/facts/facts.jsonl")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    facts = FactSet.read_jsonl(args.facts)
    scope = load_scope()
    texts = scope.chunk_text()
    problems = check_citations(facts.sorted(), texts)

    by_layer = collections.Counter()
    by_type = collections.Counter()
    by_source_role = collections.Counter()
    by_locator = collections.Counter()
    unknown_counts = collections.Counter()
    unresolved_scope = collections.Counter()
    conditions = 0
    eq_without_basis = 0
    for fact in facts.sorted():
        by_layer[fact.layer] += 1
        by_type[f"{fact.layer}/{fact.fact_type}"] += 1
        by_source_role[fact.source_role] += 1
        by_locator[fact.citation.locator_kind] += 1
        for name in fact.unknown_fields:
            unknown_counts[name] += 1
        if fact.subject.scope is UNKNOWN:
            unresolved_scope[fact.subject.kind] += 1
        if fact.conditions:
            conditions += 1
        if fact.comparator == "eq" and dict(fact.extra).get(
            "comparator_basis"
        ) != "table_cell_assignment":
            eq_without_basis += 1

    summary = {
        "facts": len(facts.facts),
        "citation_problems": len(problems),
        "first_citation_problems": problems[:10],
        "by_layer": dict(sorted(by_layer.items())),
        "by_type": dict(sorted(by_type.items())),
        "by_source_role": dict(sorted(by_source_role.items())),
        "by_locator_kind": dict(sorted(by_locator.items())),
        "unknown_field_counts": dict(sorted(unknown_counts.items())),
        "facts_with_conditions": conditions,
        "eq_without_table_basis": eq_without_basis,
        "subjects_with_unknown_scope": dict(sorted(unresolved_scope.items())),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
