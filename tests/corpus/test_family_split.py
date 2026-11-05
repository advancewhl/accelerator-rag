"""F11: the operation-manual series is split into explicit device/manual families.

The mapping below is intentionally literal and duplicated from
``scripts/split_operation_manual_families.py`` so this test fails if either the
registry or the audit mapping drifts.  Grouping evidence is the revision title
and revision_label only; no supersedes/effective-date relation is asserted.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

from accelerator_rag.corpus.schema_v2 import load_registry_v2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = PROJECT_ROOT / "data/documents/v2/registry-v2.json"
SCRIPT = PROJECT_ROOT / "scripts" / "split_operation_manual_families.py"

SERIES_FAMILY_ID = "shine-control-operation-manual-series"
SERIES_TAG = f"series:{SERIES_FAMILY_ID}"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# revision_id -> (device_slug, new family_id).  Explicit, not inferred.
EXPECTED_SPLIT: dict[str, tuple[str, str]] = {
    # timing: first edition / second edition (2023-12-06) / 2023 archive
    "shine-control-operation-manual-series-rev-99ecefba": (
        "timing",
        "shine-control-operation-manual-timing",
    ),
    "shine-control-operation-manual-series-rev-73552d9f": (
        "timing",
        "shine-control-operation-manual-timing",
    ),
    "shine-control-operation-manual-series-rev-715c251d": (
        "timing",
        "shine-control-operation-manual-timing",
    ),
    # interlock: first / second (2023-12-06) / 2023 archive / 2024 archive
    "shine-control-operation-manual-series-rev-41ba2750": (
        "interlock",
        "shine-control-operation-manual-interlock",
    ),
    "shine-control-operation-manual-series-rev-2a16a52e": (
        "interlock",
        "shine-control-operation-manual-interlock",
    ),
    "shine-control-operation-manual-series-rev-a00f759c": (
        "interlock",
        "shine-control-operation-manual-interlock",
    ),
    "shine-control-operation-manual-series-rev-fba058ab": (
        "interlock",
        "shine-control-operation-manual-interlock",
    ),
    # RF power source: first edition / 2023 archive
    "shine-control-operation-manual-series-rev-ebbcf97e": (
        "power-source",
        "shine-control-operation-manual-power-source",
    ),
    "shine-control-operation-manual-series-rev-6aab6b8c": (
        "power-source",
        "shine-control-operation-manual-power-source",
    ),
    # power supply: first / second (2023-12-07) / 2023 archive
    "shine-control-operation-manual-series-rev-e6551458": (
        "power-supply",
        "shine-control-operation-manual-power-supply",
    ),
    "shine-control-operation-manual-series-rev-9aa08d8a": (
        "power-supply",
        "shine-control-operation-manual-power-supply",
    ),
    "shine-control-operation-manual-series-rev-fe5144f3": (
        "power-supply",
        "shine-control-operation-manual-power-supply",
    ),
    # PDU: one first-edition manual
    "shine-control-operation-manual-series-rev-24e94d16": (
        "pdu",
        "shine-control-operation-manual-pdu",
    ),
    # collimator: first / third edition (2024-11)
    "shine-control-operation-manual-series-rev-c05637cf": (
        "collimator",
        "shine-control-operation-manual-collimator",
    ),
    "shine-control-operation-manual-series-rev-afa68262": (
        "collimator",
        "shine-control-operation-manual-collimator",
    ),
    # four-DOF platform: first / third edition (2024-11)
    "shine-control-operation-manual-series-rev-2536c98d": (
        "four-dof-platform",
        "shine-control-operation-manual-four-dof-platform",
    ),
    "shine-control-operation-manual-series-rev-fd3c0264": (
        "four-dof-platform",
        "shine-control-operation-manual-four-dof-platform",
    ),
    # switch platform: one third-edition manual
    "shine-control-operation-manual-series-rev-b6698e8a": (
        "switch-platform",
        "shine-control-operation-manual-switch-platform",
    ),
    # laser heater: one third-edition manual
    "shine-control-operation-manual-series-rev-fd679514": (
        "laser-heater",
        "shine-control-operation-manual-laser-heater",
    ),
    # tuner: one third-edition manual
    "shine-control-operation-manual-series-rev-eb5d6e0e": (
        "tuner",
        "shine-control-operation-manual-tuner",
    ),
    # vacuum: third edition (2024-11) / 2024 archive
    "shine-control-operation-manual-series-rev-96ebdc19": (
        "vacuum",
        "shine-control-operation-manual-vacuum",
    ),
    "shine-control-operation-manual-series-rev-b9bfd428": (
        "vacuum",
        "shine-control-operation-manual-vacuum",
    ),
    # temperature/humidity: first edition / 2023 archive
    "shine-control-operation-manual-series-rev-f11c069c": (
        "temperature-humidity",
        "shine-control-operation-manual-temperature-humidity",
    ),
    "shine-control-operation-manual-series-rev-c6fe79d8": (
        "temperature-humidity",
        "shine-control-operation-manual-temperature-humidity",
    ),
    # constant-temperature cabinet: first edition / 2023 archive
    "shine-control-operation-manual-series-rev-0e94a5e4": (
        "constant-temperature-cabinet",
        "shine-control-operation-manual-constant-temperature-cabinet",
    ),
    "shine-control-operation-manual-series-rev-300f0580": (
        "constant-temperature-cabinet",
        "shine-control-operation-manual-constant-temperature-cabinet",
    ),
    # laser: one first-edition manual
    "shine-control-operation-manual-series-rev-b672c917": (
        "laser",
        "shine-control-operation-manual-laser",
    ),
    # archive desktop client: one first-edition manual
    "shine-control-operation-manual-series-rev-fba2ad49": (
        "archive-desktop",
        "shine-control-operation-manual-archive-desktop",
    ),
    # archive query software: first / second (2023-12-06) / 2024 archive
    "shine-control-operation-manual-series-rev-f12c9ad8": (
        "archive-query",
        "shine-control-operation-manual-archive-query",
    ),
    "shine-control-operation-manual-series-rev-ec081ce3": (
        "archive-query",
        "shine-control-operation-manual-archive-query",
    ),
    "shine-control-operation-manual-series-rev-7da26046": (
        "archive-query",
        "shine-control-operation-manual-archive-query",
    ),
}

EXPECTED_FAMILY_IDS = {family_id for _, family_id in EXPECTED_SPLIT.values()}
EXPECTED_DEVICE_SLUGS = {device_slug for device_slug, _ in EXPECTED_SPLIT.values()}

# SHA-256 of sorted "<revision_id>\t<family_id>" lines for the 179 revisions
# outside the split.  Pins that no non-series revision was reassigned.
EXPECTED_NON_SERIES_FAMILY_DIGEST = (
    "880f0c5f2986be9ec41ad73803a7ab3f7feae84c346c132855d501f19b14967a"
)
# SHA-256 of canonical JSON for the 31 split revisions with family_id and tags
# removed.  Pins that the split preserved every other revision field.
EXPECTED_SPLIT_PAYLOAD_DIGEST = (
    "8376d9dd846b257d764f07073d516ccdc540bf65d5de5e577012578eb9d4241f"
)


def _registry():
    return load_registry_v2(REGISTRY)


def _revision_map():
    registry = _registry()
    return registry, {revision.revision_id: revision for revision in registry.revisions}


def test_registry_keeps_210_revisions_and_the_31_series_members():
    registry = _registry()

    assert len(registry.revisions) == 210
    assert len(EXPECTED_SPLIT) == 31
    assert set(EXPECTED_SPLIT) <= set(_revision_map()[1])
    assert len(EXPECTED_FAMILY_IDS) == 16


def test_each_split_revision_has_its_explicit_device_family():
    _, revisions = _revision_map()

    for revision_id, (device_slug, family_id) in EXPECTED_SPLIT.items():
        revision = revisions[revision_id]
        assert revision.family_id == family_id
        assert f"device:{device_slug}" in revision.tags


def test_no_family_contains_two_different_device_slugs():
    registry, revisions = _revision_map()

    family_members: dict[str, set[str]] = defaultdict(set)
    family_slugs: dict[str, set[str]] = defaultdict(set)
    for revision_id, (device_slug, family_id) in EXPECTED_SPLIT.items():
        revision = revisions[revision_id]
        assert revision.family_id == family_id
        family_members[family_id].add(revision_id)
        family_slugs[family_id].add(device_slug)

    assert set(family_slugs) == EXPECTED_FAMILY_IDS
    assert all(len(slugs) == 1 for slugs in family_slugs.values())

    expected_members: dict[str, set[str]] = defaultdict(set)
    for revision_id, (_, family_id) in EXPECTED_SPLIT.items():
        expected_members[family_id].add(revision_id)
    for family_id, expected in expected_members.items():
        assert family_members[family_id] == expected
        # The registry family must contain exactly the split members, with no
        # different-device revision folded into the same family.
        assert set(registry.family(family_id).revision_ids) == expected

    # Same-device editions and archive copies are grouped into one family.
    slug_families: dict[str, set[str]] = defaultdict(set)
    for device_slug, family_id in EXPECTED_SPLIT.values():
        slug_families[device_slug].add(family_id)
    assert set(slug_families) == EXPECTED_DEVICE_SLUGS
    assert all(len(family_ids) == 1 for family_ids in slug_families.values())


def test_every_split_revision_keeps_the_series_tag():
    registry, revisions = _revision_map()

    for revision_id in EXPECTED_SPLIT:
        assert SERIES_TAG in revisions[revision_id].tags

    # The series survives only as a tag, never as a family or a family_id.
    assert all(
        SERIES_TAG not in revision.tags
        for revision in registry.revisions
        if revision.revision_id not in EXPECTED_SPLIT
    )
    assert all(
        revision.family_id != SERIES_FAMILY_ID
        for revision in registry.revisions
    )
    assert SERIES_FAMILY_ID not in {
        family.family_id for family in registry.families
    }


def test_family_ids_are_lowercase_slugs():
    registry = _registry()

    for family in registry.families:
        assert SLUG_RE.fullmatch(family.family_id), family.family_id
    for device_slug, family_id in EXPECTED_SPLIT.values():
        assert SLUG_RE.fullmatch(device_slug), device_slug
        assert SLUG_RE.fullmatch(family_id), family_id


def test_no_non_series_revision_family_id_changed():
    registry = _registry()

    untouched = sorted(
        (revision.revision_id, revision.family_id)
        for revision in registry.revisions
        if revision.revision_id not in EXPECTED_SPLIT
    )
    assert len(untouched) == 179
    payload = "\n".join(
        f"{revision_id}\t{family_id}"
        for revision_id, family_id in untouched
    )
    assert hashlib.sha256(payload.encode("utf-8")).hexdigest() == (
        EXPECTED_NON_SERIES_FAMILY_DIGEST
    )


def test_split_revisions_preserve_all_fields_except_family_and_tags():
    _, revisions = _revision_map()

    rows = []
    for revision_id in sorted(EXPECTED_SPLIT):
        row = revisions[revision_id].to_dict()
        row.pop("family_id")
        row.pop("tags")
        rows.append(row)
    payload = json.dumps(
        rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    assert hashlib.sha256(payload.encode("utf-8")).hexdigest() == (
        EXPECTED_SPLIT_PAYLOAD_DIGEST
    )


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "split_operation_manual_families", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    # dataclass resolves string annotations via sys.modules[cls.__module__].
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_script_mapping_matches_the_audit_mapping():
    module = _load_script_module()

    assert module.REVISION_FAMILY_ID == {
        revision_id: family_id
        for revision_id, (_, family_id) in EXPECTED_SPLIT.items()
    }
    assert module.REVISION_DEVICE_SLUG == {
        revision_id: device_slug
        for revision_id, (device_slug, _) in EXPECTED_SPLIT.items()
    }


def test_script_is_deterministic_and_registry_is_its_fixed_point():
    module = _load_script_module()
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))

    updated, summary = module._split_registry(data)
    again, again_summary = module._split_registry(updated)

    assert updated == data
    assert again == updated
    assert summary == again_summary
    assert summary["revisions"] == 210
    assert summary["split_revisions"] == 31
    assert summary["device_families"] == 16
    assert summary["untouched_revisions"] == 179


def test_script_defaults_to_dry_run_and_write_is_idempotent(tmp_path):
    copy = tmp_path / "registry-v2.json"
    copy.write_bytes(REGISTRY.read_bytes())
    original = copy.read_bytes()

    dry_run = subprocess.run(
        [sys.executable, str(SCRIPT), "--registry", str(copy)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert dry_run.returncode == 0, dry_run.stderr
    assert "dry-run" in dry_run.stdout
    assert copy.read_bytes() == original

    write = subprocess.run(
        [sys.executable, str(SCRIPT), "--registry", str(copy), "--write"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0, write.stderr
    assert "already applied" in write.stdout
    assert copy.read_bytes() == original


def test_first_split_from_a_pre_split_registry_matches_current_state():
    module = _load_script_module()
    current = json.loads(REGISTRY.read_text(encoding="utf-8"))
    pre = json.loads(REGISTRY.read_text(encoding="utf-8"))
    mapped = set(EXPECTED_SPLIT)
    mapped_paths = set()
    for revision in pre["revisions"]:
        if revision["revision_id"] not in mapped:
            continue
        mapped_paths.add(revision["source_path"])
        revision["family_id"] = SERIES_FAMILY_ID
        revision["tags"] = [
            tag
            for tag in revision["tags"]
            if tag != SERIES_TAG and not tag.startswith("device:")
        ]
    pre["families"] = [
        family
        for family in pre["families"]
        if family["family_id"] not in EXPECTED_FAMILY_IDS
    ]
    pre["families"].append(
        {
            "family_id": SERIES_FAMILY_ID,
            "title": "SHINE 控制界面操作手册系列",
            "description": "拆分前的过宽操作手册族。",
            "revision_ids": sorted(mapped),
            "notes": "",
            "created_at": "2026-11-02",
        }
    )
    for disposition in pre["dispositions"]:
        if disposition["source_path"] in mapped_paths:
            disposition["target_family_id"] = SERIES_FAMILY_ID

    updated, _summary = module._split_registry(pre)
    current_revisions = {
        revision["revision_id"]: revision for revision in current["revisions"]
    }
    updated_revisions = {
        revision["revision_id"]: revision for revision in updated["revisions"]
    }
    current_dispositions = {
        (item["batch_id"], item["source_path"]): item
        for item in current["dispositions"]
    }
    updated_dispositions = {
        (item["batch_id"], item["source_path"]): item
        for item in updated["dispositions"]
    }

    for revision_id in mapped:
        assert updated_revisions[revision_id]["family_id"] == current_revisions[
            revision_id
        ]["family_id"]
        assert updated_revisions[revision_id]["tags"] == current_revisions[
            revision_id
        ]["tags"]
        key = (
            updated_revisions[revision_id]["batch_id"],
            updated_revisions[revision_id]["source_path"],
        )
        assert updated_dispositions[key]["target_family_id"] == (
            current_dispositions[key]["target_family_id"]
        )
