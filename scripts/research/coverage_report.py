"""Gold-evidence coverage of the fact layer (development-facing table).

For every dev/val question, count how many of its ``gold.evidence_minimal``
parent chunks are cited by at least one fact.  The result shows whether the
fact layer can reach a question's source evidence at all; it is **not** a
correctness measure and never substitutes for semantic review.

Usage:
  python3 scripts/research/coverage_report.py \
      --out reports/phase2/evidence-coverage.json
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

DEFAULT_FACTS = Path("data/facts/facts.jsonl")
DEFAULT_BENCHMARK = Path("data/evaluation/research-benchmark-300-v1")
LAYERS = ("connectivity", "process", "parameter")
SPLITS = ("dev", "val")


def load_chunk_layers(path: Path) -> dict[str, set[str]]:
    layers: dict[str, set[str]] = collections.defaultdict(set)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        fact = json.loads(line)
        chunk_id = fact["citation"].get("chunk_id")
        if chunk_id:
            layers[chunk_id].add(fact["layer"])
    return layers


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", default=str(DEFAULT_FACTS))
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    facts_path = Path(args.facts)
    chunk_layers = load_chunk_layers(facts_path)
    facts_sha256 = file_sha256(facts_path)
    coverage: dict[str, dict] = {}
    table: dict[tuple[str, str], list[int]] = collections.defaultdict(
        lambda: [0, 0, 0]
    )
    for split in SPLITS:
        bundle = json.loads(
            (Path(args.benchmark) / split / "questions.json").read_text(
                encoding="utf-8"
            )
        )
        for item in bundle["items"]:
            scenario = item.get("scenario", "")
            evidence = item["gold"].get("evidence_minimal", [])
            covered_chunks = [
                entry.get("chunk_id", "") for entry in evidence
            ]
            covered = [cid for cid in covered_chunks if cid in chunk_layers]
            if len(covered) == len(covered_chunks):
                table[(split, scenario)][0] += 1
            elif covered:
                table[(split, scenario)][1] += 1
            else:
                table[(split, scenario)][2] += 1
            coverage[item["base_id"]] = {
                "split": split,
                "scenario": scenario,
                "verdict": item["gold"].get("verdict_class", ""),
                "evidence": len(covered_chunks),
                "covered_by_layer": {
                    layer: sum(
                        1 for cid in covered_chunks if layer in chunk_layers.get(cid, ()))
                    for layer in LAYERS
                },
                "covered_chunks": [
                    {
                        "chunk_id": cid,
                        "covered": cid in chunk_layers,
                        "layers": sorted(chunk_layers.get(cid, ())),
                    }
                    for cid in covered_chunks
                ],
                "facts_sha256": facts_sha256,
            }

    print(f"{'split':<5} {'scenario':<18} {'full':>5} {'partial':>8} {'none':>5}")
    for (split, scenario), counts in sorted(table.items()):
        print(f"{split:<5} {scenario:<18} {counts[0]:>5} {counts[1]:>8} {counts[2]:>5}")
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(coverage, ensure_ascii=False, indent=1, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {path} ({len(coverage)} questions)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
