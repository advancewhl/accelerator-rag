"""Assemble the 50-item PRAB seed set from the three authoring files.

The canonical file keeps the metadata block from seed-questions-v1.json (the 8 full
samples live there too) and appends the corpus/Waveform parts, deduplicating by id.

Usage:
    python scripts/build_seed_questions.py            # write data/evaluation/seed-questions-v1.json
    python scripts/build_seed_questions.py --check    # validate only, do not write
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "data/evaluation"
CANONICAL = EVAL / "seed-questions-v1.json"
PARTS = [EVAL / "seed-questions-v1-corpus.json", EVAL / "seed-questions-v1-waveform.json"]
ORDER = {
    "task1_parameter_condition": 0,
    "task2_alignment_prep": 1,
    "task3_cross_version_comparison": 2,
    "task4_fault_diagnosis": 3,
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    base = load(CANONICAL)
    if base.get("schema_version") != "prab-seed-questions-v1":
        raise SystemExit(f"unexpected schema_version in {CANONICAL}")

    items, sources, seen = [], {}, set()
    for path in [CANONICAL, *PARTS]:
        if not path.exists():
            print(f"skip missing part: {path.name}")
            continue
        payload = load(path)
        sources[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        for item in payload.get("items", []):
            if item["id"] in seen:
                print(f"duplicate id ignored: {item['id']} ({path.name})")
                continue
            seen.add(item["id"])
            items.append(item)

    items.sort(key=lambda item: (ORDER[item["category"]], item["id"]))
    base["items"] = items
    base["sources"] = sources
    base["assembled_at"] = "2026-10-29"

    categories = Counter(item["category"] for item in items)
    statuses = Counter(item["expected_status"] for item in items)
    overlap = sum(1 for item in items if item["provenance"].get("overlaps_36q"))
    pending = sum(1 for item in items if item["verification"]["status"] == "pending_human")
    negatives = sum(1 for item in items if item["negative_construction"])
    print(f"items={len(items)} categories={dict(categories)}")
    print(f"statuses={dict(statuses)} overlaps_36q={overlap} pending_human={pending} negatives={negatives}")

    if args.check:
        return
    CANONICAL.write_text(json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {CANONICAL.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
