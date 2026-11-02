"""Merged Schema v2 artifact: every batch input has a disposition, no overclaim."""

from pathlib import Path

from accelerator_rag.corpus.schema_v2 import (
    load_conflict_ledger,
    load_registry_v2,
    source_format_for_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = PROJECT_ROOT / "data/documents/v2/registry-v2.json"
LEGACY = PROJECT_ROOT / "data/documents/v2/registry-v2.legacy-baseline.json"
CONFLICTS = PROJECT_ROOT / "data/documents/v2/conflicts.json"
BATCH_ID = "2026-11-02-shine-control"
BATCH_ROOT = "data/l0_raw/incoming/2026-11-02-shine-control/资料/"


def test_batch_artifact_covers_all_inputs_and_revisions():
    registry = load_registry_v2(REGISTRY)

    assert len(registry.revisions) == 210
    assert len(registry.families) == 74
    assert len(registry.dispositions) == 235
    batch = [
        item for item in registry.dispositions if item.batch_id == BATCH_ID
    ]
    assert len(batch) == 218
    assert len({item.source_path for item in batch}) == 218
    revision_paths = {
        revision.source_path
        for revision in registry.revisions
        if revision.batch_id == BATCH_ID
    }
    assert len(revision_paths) == 193
    for item in batch:
        if item.disposition in {"text_index", "structured_index"}:
            assert item.source_path in revision_paths
        else:
            assert item.source_path not in revision_paths
    registry.validate_batch_coverage(
        BATCH_ID, (item.source_path for item in batch)
    )


def test_batch_revisions_never_claim_approval_or_current_status():
    registry = load_registry_v2(REGISTRY)
    batch_revisions = [
        revision
        for revision in registry.revisions
        if revision.batch_id == BATCH_ID
    ]

    assert len(batch_revisions) == 193
    assert all(
        revision.approval_status == "unknown" for revision in batch_revisions
    )
    assert all(
        revision.usage_status != "current" for revision in batch_revisions
    )
    assert all(
        revision.revision_id.startswith(revision.family_id)
        for revision in batch_revisions
    )
    assert all(
        not revision.revision_label.startswith("data/")
        for revision in batch_revisions
    )


def test_restricted_and_pending_material_is_explicit():
    registry = load_registry_v2(REGISTRY)
    restricted = [
        revision
        for revision in registry.revisions
        if revision.access_scope == "restricted"
    ]

    assert len(restricted) == 3
    assert all(revision.batch_id == BATCH_ID for revision in restricted)
    assert any("网络安全" in revision.title for revision in restricted)
    assert any(
        "地址分配" in revision.title for revision in restricted
    )
    assert all(
        revision.usage_status in {"pending_review", "reference"}
        for revision in restricted
    )


def test_source_format_matches_every_batch_path():
    registry = load_registry_v2(REGISTRY)
    for item in registry.dispositions:
        if item.batch_id != BATCH_ID:
            continue
        assert item.source_path.startswith(BATCH_ROOT)
        expected = source_format_for_path(item.source_path)
        if expected.value != "other":
            assert item.source_format == expected.value


def test_conflicts_are_validated_and_kept_open():
    ledger = load_conflict_ledger(CONFLICTS)

    assert len(ledger.conflicts) == 6
    assert {item.status for item in ledger.conflicts} == {
        "open",
        "needs_source_check",
    }
    assert all(not item.resolution for item in ledger.conflicts)
    assert any("8 GeV" in item.topic for item in ledger.conflicts)
    assert any("7.2 GeV" in item.evidence_location or "7.2 GeV" in item.topic
               for item in ledger.conflicts)


def test_conflicts_link_to_registry_revisions_where_possible():
    ledger = load_conflict_ledger(CONFLICTS)
    registry = load_registry_v2(REGISTRY)
    revision_ids = {revision.revision_id for revision in registry.revisions}
    linked = [
        value
        for item in ledger.conflicts
        for value in (item.revision_a_id, item.revision_b_id)
        if value
    ]

    assert len(linked) >= 10
    assert set(linked) <= revision_ids
    assert all(
        item.external_reference
        for item in ledger.conflicts
        if not item.revision_a_id or not item.revision_b_id
    )


def test_legacy_baseline_snapshot_stays_separate():
    legacy = load_registry_v2(LEGACY)

    assert len(legacy.revisions) == 17
    assert {revision.batch_id for revision in legacy.revisions} == {
        "legacy-baseline"
    }
    assert len(legacy.dispositions) == 17
