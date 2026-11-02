"""Validate PRAB seed-question files: schema, ids, category balance, evidence locators.

Usage:
    python scripts/validate_seed_questions.py data/evaluation/seed-questions-v1.json
    python scripts/validate_seed_questions.py data/evaluation/seed-questions-v1*.json --expect-total 50

Exit code 1 on any error. Locators are checked for resolvability only; they do not
prove that an excerpt is semantically sufficient.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WAVEFORM = Path("/home/whloong/waveform-storage/waveform-storage-system")

CATEGORIES = {
    "task1_parameter_condition",
    "task2_alignment_prep",
    "task3_cross_version_comparison",
    "task4_fault_diagnosis",
}
STATUSES = {"answerable", "partial", "insufficient"}
VERIFICATION = {"machine_verified", "pending_human"}
MUST_COVER_TYPES = {"number", "text", "comparator", "list", "version"}
SCORING_KEYS = {"full", "partial", "zero", "hazardous_patterns"}
ITEM_KEYS = {
    "id", "category", "language", "question", "source_case", "applicable",
    "expected_status", "gold_answer", "must_cover", "constraints", "evidence",
    "scoring", "verification", "negative_construction", "provenance",
}
LINE_RANGE = re.compile(r"^(?P<path>[^:]+\.(?:py|md|json)):(?P<start>\d+)(?:-(?P<end>\d+))?$")


def resolve(path_text):
    for base in (ROOT, WAVEFORM):
        candidate = base / path_text
        if candidate.exists():
            return candidate
    return None


def check_locator(locator, errors, item_id):
    path_text = locator.split("#", 1)[0].split(":§", 1)[0]
    match = LINE_RANGE.match(locator)
    if match:
        target = resolve(match["path"])
        if target is None:
            errors.append(f"{item_id}: locator file not found: {locator}")
            return
        lines = sum(1 for _ in target.open("r", encoding="utf-8", errors="replace"))
        end = int(match["end"] or match["start"])
        if not 1 <= int(match["start"]) <= end <= lines:
            errors.append(f"{item_id}: locator line range outside file ({lines} lines): {locator}")
        return
    if resolve(path_text) is None:
        errors.append(f"{item_id}: locator path not found: {locator}")


def validate_item(item, errors, warnings):
    item_id = item.get("id", "<missing-id>")
    missing = ITEM_KEYS - set(item)
    if missing:
        errors.append(f"{item_id}: missing keys {sorted(missing)}")
        return
    extra = set(item) - ITEM_KEYS
    if extra:
        warnings.append(f"{item_id}: unknown keys {sorted(extra)}")
    if item["category"] not in CATEGORIES:
        errors.append(f"{item_id}: bad category {item['category']}")
    if item["expected_status"] not in STATUSES:
        errors.append(f"{item_id}: bad expected_status {item['expected_status']}")
    for field in ("system_version", "conditions"):
        if not item["applicable"].get(field):
            errors.append(f"{item_id}: applicable.{field} empty")

    if not item["must_cover"]:
        errors.append(f"{item_id}: must_cover empty")
    seen = set()
    for fact in item["must_cover"]:
        if fact.get("id") in seen:
            errors.append(f"{item_id}: duplicate must_cover id {fact.get('id')}")
        seen.add(fact.get("id"))
        if fact.get("type") not in MUST_COVER_TYPES:
            errors.append(f"{item_id}/{fact.get('id')}: bad type {fact.get('type')}")
        if not fact.get("match"):
            errors.append(f"{item_id}/{fact.get('id')}: empty match list")
        if fact.get("type") == "number" and fact.get("unit") is None and "unit" not in fact:
            errors.append(f"{item_id}/{fact.get('id')}: number fact needs unit field (null allowed)")

    constraints = item["constraints"]
    for field in ("numbers", "comparators", "preconditions", "version_constraints"):
        if field not in constraints or not isinstance(constraints[field], list):
            errors.append(f"{item_id}: constraints.{field} must be a list")
    for number in constraints.get("numbers", []):
        if "value" not in number or "unit" not in number:
            errors.append(f"{item_id}: constraint number needs value+unit: {number}")

    if not item["evidence"]:
        errors.append(f"{item_id}: evidence empty")
    for evidence in item["evidence"]:
        check_locator(evidence.get("locator", ""), errors, item_id)
        if not evidence.get("excerpt"):
            errors.append(f"{item_id}: evidence {evidence.get('id')} excerpt empty")

    scoring = item["scoring"]
    if set(scoring) != SCORING_KEYS:
        errors.append(f"{item_id}: scoring keys must be {sorted(SCORING_KEYS)}")
    if not isinstance(scoring.get("hazardous_patterns"), list) or not scoring["hazardous_patterns"]:
        errors.append(f"{item_id}: hazardous_patterns must be a non-empty list")

    verification = item["verification"]
    if verification.get("status") not in VERIFICATION:
        errors.append(f"{item_id}: bad verification.status {verification.get('status')}")
    if verification.get("status") == "pending_human" and not verification.get("pending"):
        errors.append(f"{item_id}: pending_human requires non-empty pending list")

    provenance = item["provenance"]
    for field in ("derivation", "independent_test_allowed"):
        if field not in provenance:
            errors.append(f"{item_id}: provenance.{field} missing")
    if provenance.get("independent_test_allowed") is not False:
        errors.append(f"{item_id}: dev seed items must set independent_test_allowed=false")
    if not isinstance(provenance.get("overlaps_36q"), bool):
        errors.append(f"{item_id}: provenance.overlaps_36q must be boolean")

    if item["negative_construction"] is not None:
        for field in ("method", "detail"):
            if not item["negative_construction"].get(field):
                errors.append(f"{item_id}: negative_construction.{field} missing")
    if len(item["question"]) < 10:
        warnings.append(f"{item_id}: question suspiciously short")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--expect-total", type=int)
    args = parser.parse_args()

    errors, warnings, ids, categories, statuses, pending = [], [], Counter(), Counter(), Counter(), 0
    total = 0
    for path_text in args.paths:
        payload = json.loads(Path(path_text).read_text())
        if payload.get("schema_version") != "prab-seed-questions-v1":
            errors.append(f"{path_text}: unexpected schema_version {payload.get('schema_version')}")
        for item in payload.get("items", []):
            total += 1
            ids[item.get("id")] += 1
            categories[item.get("category")] += 1
            statuses[item.get("expected_status")] += 1
            pending += item.get("verification", {}).get("status") == "pending_human"
            validate_item(item, errors, warnings)

    for item_id, count in ids.items():
        if count > 1:
            errors.append(f"duplicate id across files: {item_id} x{count}")
    if args.expect_total is not None and total != args.expect_total:
        errors.append(f"expected {args.expect_total} items, found {total}")
    for name in ("task1_parameter_condition", "task2_alignment_prep",
                 "task3_cross_version_comparison", "task4_fault_diagnosis"):
        if not categories[name]:
            errors.append(f"category {name} has no items")
    if statuses["insufficient"] == 0:
        errors.append("no insufficient items: abstention behaviour is untested")

    print(f"items={total} categories={dict(categories)} statuses={dict(statuses)} pending_human={pending}")
    for warning in warnings:
        print(f"WARN {warning}")
    for error in errors:
        print(f"ERROR {error}")
    print("OK" if not errors else f"FAILED with {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
