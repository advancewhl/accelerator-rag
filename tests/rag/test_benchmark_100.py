"""Invariants for the frozen 100-question rc.3 validation benchmark."""

from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "data/evaluation"


def load(name: str):
    with (EVAL / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def test_validity_pilot_v3_keeps_answers_and_amends_eight_stems():
    v2 = load("validity-pilot-v2.json")
    v3 = load("validity-pilot-v3.json")
    assert len(v3["items"]) == 50
    assert len(v3["amended_ids"]) == 8

    v2_by_id = {item["id"]: item for item in v2["items"]}
    for item in v3["items"]:
        original = v2_by_id[item["id"]]
        # Only the stem may change; answers, facts and evidence stay identical.
        assert item["gold_answer"] == original["gold_answer"]
        assert item["must_cover"] == original["must_cover"]
        assert item["forbidden_claims"] == original["forbidden_claims"]
        assert item["evidence_groups"] == original["evidence_groups"]
        if item["id"] in v3["amended_ids"]:
            assert item["query"].startswith(original["query"].rstrip())
            assert item["query"] != original["query"]
        else:
            assert item["query"] == original["query"]


def test_benchmark_has_one_hundred_unique_items():
    data = load("kb2-benchmark-100-v1.json")
    items = data["items"]
    assert len(items) == 100

    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids))

    queries = [item["query"].strip().casefold() for item in items]
    assert len(queries) == len(set(queries))

    counts = collections.Counter(item["source_set"] for item in items)
    assert counts == {
        "validity-pilot-v3": 50,
        "cable-lookup-v1": 20,
        "kb2-question-plan-v1": 30,
    }


def test_every_item_declares_a_valid_status_and_scope():
    data = load("kb2-benchmark-100-v1.json")
    for item in data["items"]:
        assert item["expected_status"] in {"answered", "partial", "insufficient"}
        assert item["query"].strip()
        assert item["verification_level"]
        if item["expected_status"] == "answered":
            assert item["required_facts"], item["id"]


def test_every_kb2_item_has_a_resolvable_version_scope():
    data = load("kb2-benchmark-100-v1.json")
    with (ROOT / "data/documents/v2/registry-v2.json").open(encoding="utf-8") as handle:
        registry = json.load(handle)
    known = {item["revision_id"] for item in registry["revisions"]}
    for item in data["items"]:
        if item["source_set"] != "kb2-question-plan-v1":
            continue
        scope = item.get("scope")
        assert scope, item["id"]
        assert scope["mode"] == "version"
        assert scope["revision_ids"]
        assert set(scope["revision_ids"]) <= known, item["id"]


def test_restricted_dependency_and_unverified_items_are_absent():
    data = load("kb2-benchmark-100-v1.json")
    ids = {item["id"] for item in data["items"]}
    assert "KB2-FMT-015" not in ids
    assert "KB2-BND-001" not in ids

    plan = load("kb2-question-plan-v1.json")
    plan_by_id = {item["id"]: item for item in plan["questions"]}
    for item in data["items"]:
        if item["source_set"] != "kb2-question-plan-v1":
            continue
        source = plan_by_id[item["id"]]
        assert source["provenance_status"] == "verified_from_extracted_text"
