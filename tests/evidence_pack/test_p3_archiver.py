from accelerator_rag.evidence_pack.archiver import (
    StaticArchiver,
    atoms_for_needs,
    load_export,
    normalize_export,
)
from accelerator_rag.evidence_pack.schema import EntityNeed, Needs, RelationNeed


def _result(pv="TEST:FAKE:PV", **overrides):
    payload = {
        "pv": pv,
        "start": "2026-01-01T00:00:00Z",
        "end": "2026-01-01T00:10:00Z",
        "strategy": "lastSample",
        "points": [
            {"timestamp": "2025-12-31T23:59:00Z", "value": 10},
            {"timestamp": "2026-01-01T00:01:00Z", "value": 20},
            {"timestamp": "2026-01-01T00:02:00Z", "value": 20},
        ],
        "point_count": 3,
        "in_range_point_count": 2,
        "context_point_count": 1,
        "data_state": "available",
        "segments": [
            {
                "source_id": "SRC",
                "start": "2026-01-01T00:00:00Z",
                "end": "2026-01-01T00:10:00Z",
                "bin_seconds": 1,
                "point_count": 3,
                "ok": True,
                "error": None,
                "warnings": [],
            }
        ],
        "source_ids": ["SRC"],
        "bin_seconds": 1,
        "downsampled": False,
        "truncated": False,
        "complete": True,
        "warnings": [],
        "error": None,
    }
    payload.update(overrides)
    return payload


def _export(result=None, pv="TEST:FAKE:PV"):
    return {
        "captured_on": "2026-01-01",
        "timezone": "UTC",
        "archiver": {
            "capabilities": {"read_only": True},
            "health": {"status": "ok"},
            "sources": {"sources": []},
        },
        "probes": {
            "probe": {
                "request": {"pvs": [pv], "start": "2026-01-01T00:00:00Z"},
                "response": {"results": [result or _result(pv)]},
            }
        },
    }


def test_normalization_keeps_window_strategy_and_limits():
    payload = _export(
        _result(
            downsampled=True,
            truncated=True,
            warnings=["coarse query"],
            segments=[
                {
                    "warnings": ["segment truncated"],
                    "error": None,
                }
            ],
        )
    )
    export = normalize_export(payload)
    observation = export.observations[0]
    assert observation.point_count == 3
    assert observation.context_point_count == 1
    limitations = " ".join(observation.limitations())
    assert "downsampled" in limitations
    assert "truncated" in limitations
    assert "segment_warning=segment truncated" in limitations
    assert "context_points=1" in limitations
    assert "unit_unknown" in limitations
    assert observation.values() == ("10", "20")


def test_complete_true_with_truncated_stays_limited():
    export = normalize_export(_export(_result(complete=True, truncated=True)))
    observation = export.observations[0]
    assert observation.complete is True
    assert "truncated" in " ".join(observation.limitations())


def test_atoms_only_for_named_pv():
    export = normalize_export(_export())
    needs = Needs(
        question_id="Q",
        route="exact_record",
        entities=(EntityNeed("TEST:FAKE:PV", "test:fake:pv", "pv"),),
        relations=(RelationNeed("external_observation", False, "观测"),),
        revision_ids=(),
    )
    atoms = atoms_for_needs(export, needs)
    assert len(atoms) == 1
    assert atoms[0].locator_kind == "external_observation"
    assert atoms[0].external["downsampled"] is False
    assert "TEST:FAKE:PV" in atoms[0].excerpt
    other = Needs(
        question_id="Q2",
        route="exact_record",
        entities=(EntityNeed("OTHER:PV", "other:pv", "pv"),),
        relations=(RelationNeed("external_observation", False, "观测"),),
        revision_ids=(),
    )
    assert atoms_for_needs(export, other) == ()


def test_static_archiver_and_load(tmp_path):
    path = tmp_path / "export.json"
    import json

    path.write_text(json.dumps(_export()), encoding="utf-8")
    export = load_export(path)
    source = StaticArchiver(export)
    needs = Needs(
        question_id="Q",
        route="exact_record",
        entities=(EntityNeed("TEST:FAKE:PV", "test:fake:pv", "pv"),),
        relations=(RelationNeed("external_observation", False, "观测"),),
        revision_ids=(),
    )
    assert len(source.atoms_for(needs)) == 1
