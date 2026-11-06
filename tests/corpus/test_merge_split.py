"""The governance merge must reproduce the device/manual split itself."""

import importlib.util
from pathlib import Path
import sys

from accelerator_rag.corpus.schema_v2 import load_registry_v2


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "merge_v2_governance.py"


def load_merge_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "merge_v2_governance", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_merge_applies_reviewed_operation_manual_split():
    merge = load_merge_module()
    registry = load_registry_v2(ROOT / "data/documents/v2/registry-v2.json")
    revisions, families = merge._apply_operation_manual_split(
        list(registry.revisions), list(registry.families), "2026-11-02"
    )

    assert len(revisions) == 225
    assert len(families) == len(registry.families) == 104
    family_ids = {family.family_id for family in families}
    assert "shine-control-operation-manual-series" not in family_ids
    assert "shine-control-operation-manual-timing" in family_ids
    timing = next(
        revision
        for revision in revisions
        if revision.revision_id.endswith("rev-99ecefba")
    )
    assert timing.family_id == "shine-control-operation-manual-timing"
    assert "series:shine-control-operation-manual-series" in timing.tags
    assert "device:timing" in timing.tags
