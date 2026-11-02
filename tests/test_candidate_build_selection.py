"""Candidate selection must exclude restricted material by default."""

import importlib.util
from pathlib import Path

from accelerator_rag.corpus.schema_v2 import load_registry_v2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "kb2_candidate_build.py"


def load_build_module():
    spec = importlib.util.spec_from_file_location("kb2_candidate_build", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_restricted_revisions_are_excluded_from_public_candidate():
    module = load_build_module()
    registry = load_registry_v2(
        PROJECT_ROOT / "data/documents/v2/registry-v2.json"
    )
    public = module.selected_revisions(
        registry, 0, batch_id="2026-11-02-shine-control"
    )
    all_revisions = module.selected_revisions(
        registry,
        0,
        batch_id="2026-11-02-shine-control",
        include_restricted=True,
    )

    assert all(
        revision.access_scope != "restricted" for revision in public
    )
    assert any(
        revision.access_scope == "restricted" for revision in all_revisions
    )
    assert len(all_revisions) == len(public) + 3
