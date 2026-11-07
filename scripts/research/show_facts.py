"""Inspect built phase-2 facts.

Usage:
  python3 scripts/research/show_facts.py --layer parameter --limit 5
  python3 scripts/research/show_facts.py --fact-id F0123456789abcdef
  python3 scripts/research/show_facts.py --revision <rev> --fact-type attribute
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.facts.schema import FactSet  # noqa: E402


def compact(fact) -> dict:
    payload = fact.to_dict()
    payload.pop("schema_version", None)
    for name in ("number", "low", "high", "unit", "attribute", "raw_value"):
        value = payload.get(name)
        if value is None:
            payload[name] = "UNKNOWN"
    return payload


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", default="data/facts/facts.jsonl")
    parser.add_argument("--layer", default=None)
    parser.add_argument("--fact-type", default=None)
    parser.add_argument("--revision", default=None)
    parser.add_argument("--fact-id", default=None)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)

    facts = FactSet.read_jsonl(args.facts)
    rows = []
    for fact in facts.sorted():
        if args.fact_id and fact.fact_id != args.fact_id:
            continue
        if args.layer and fact.layer != args.layer:
            continue
        if args.fact_type and fact.fact_type != args.fact_type:
            continue
        if args.revision and fact.revision_id != args.revision:
            continue
        rows.append(compact(fact))
        if not args.fact_id and len(rows) >= args.limit:
            break
    print(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f"[{len(rows)} shown of {len(facts.facts)}]")


if __name__ == "__main__":  # pragma: no cover
    main()
