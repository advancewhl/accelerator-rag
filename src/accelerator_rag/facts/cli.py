"""Build the phase-2 fact layers over the dev/val family scope.

Usage:
  python -m accelerator_rag.facts.cli --splits dev,val --out data/facts
  python -m accelerator_rag.facts.cli --revision <revision_id> --out /tmp/facts
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .corpus import load_scope, split_family_ids
from .schema import FactSet, check_citations, SCHEMA_VERSION


def _load_layers(layers=None):
    """Import only the requested layers so one workflow can build alone."""

    wanted = set(layers) if layers else {"parameter", "connectivity", "process"}
    loaded = []
    if "parameter" in wanted:
        from . import params

        loaded.append(("parameter", params))
    if "connectivity" in wanted:
        from . import connectivity

        loaded.append(("connectivity", connectivity))
    if "process" in wanted:
        from . import process

        loaded.append(("process", process))
    return tuple(loaded)


def build(splits: tuple[str, ...], out: Path, revisions=None, layers=None) -> dict:
    scope = load_scope(splits, revision_ids=revisions)
    wanted = set(layers) if layers else None
    fact_set = FactSet()
    counts: dict[str, int] = {}
    for name, module in _load_layers(layers):
        if wanted is not None and name not in wanted:
            continue
        facts = list(module.extract(scope))
        for fact in facts:
            if fact.layer != name:
                raise ValueError(
                    f"{module.__name__} emitted layer={fact.layer}, expected {name}"
                )
            fact_set.add(fact)
        counts[name] = len(facts)

    out.mkdir(parents=True, exist_ok=True)
    total = fact_set.write_jsonl(out / "facts.jsonl")
    for name in counts:
        layer_path = out / f"{name}.jsonl"
        layer_facts = fact_set.by_layer(name)
        FactSet({fact.fact_id: fact for fact in layer_facts}).write_jsonl(layer_path)

    problems = check_citations(fact_set.sorted(), scope.chunk_text())
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "splits": list(splits),
        "family_ids": list(split_family_ids(splits)),
        "revision_count": len(scope.revisions),
        "revision_ids": list(scope.revision_ids()),
        "fact_counts": counts,
        "fact_total": total,
        "citation_problems": problems,
        "facts_sha256": hashlib.sha256(
            (out / "facts.jsonl").read_bytes()
        ).hexdigest(),
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    if problems:
        raise SystemExit(
            f"{len(problems)} citation problems; first: {problems[0]}"
        )
    return manifest


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits", default="dev,val")
    parser.add_argument("--out", default="data/facts")
    parser.add_argument(
        "--revision",
        action="append",
        default=None,
        help="restrict to one revision id (repeatable)",
    )
    parser.add_argument(
        "--layer",
        action="append",
        choices=["parameter", "connectivity", "process"],
        default=None,
    )
    args = parser.parse_args(argv)
    manifest = build(
        tuple(args.splits.split(",")),
        Path(args.out),
        revisions=args.revision,
        layers=args.layer,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=1))


if __name__ == "__main__":  # pragma: no cover
    main()
