"""The migrated Schema v2 artifact must stay consistent with the v1 baseline."""

from pathlib import Path

from accelerator_rag.corpus.registry import load_registry
from accelerator_rag.corpus.schema_v2 import load_registry_v2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = PROJECT_ROOT / "data/documents/v2/registry-v2.legacy-baseline.json"


def test_migrated_registry_covers_every_legacy_document():
    legacy = load_registry(PROJECT_ROOT / "data/documents/registry.json")
    legacy += load_registry(PROJECT_ROOT / "data/documents/registry-md.json")
    registry = load_registry_v2(ARTIFACT)

    assert len(registry.revisions) == len(legacy) == 17
    assert {
        revision.revision_id for revision in registry.revisions
    } == {record.doc_id for record in legacy}
    assert {
        revision.source_path for revision in registry.revisions
    } == {record.source_path for record in legacy}
    assert len(registry.families) == len(legacy)
    assert len(registry.dispositions) == len(legacy)
    assert {revision.batch_id for revision in registry.revisions} == {
        "legacy-baseline"
    }


def test_migrated_registry_does_not_overclaim_current_status():
    registry = load_registry_v2(ARTIFACT)
    current = {
        revision.revision_id
        for revision in registry.revisions
        if revision.usage_status == "current"
    }

    assert current == {
        "waveform-storage-dataflow",
        "waveform-alignment-semantics",
        "waveform-fault-history",
        "rag-ingestion-verification-rollback",
    }
    assert all(
        revision.approval_status == "unknown" for revision in registry.revisions
    )
    assert all(
        revision.scope for revision in registry.revisions
        if revision.usage_status == "current"
    )
