#!/usr/bin/env python3
"""Split the over-broad SHINE operation-manual series family (F11).

The registry currently assigns 31 operation-manual revisions to one family,
``shine-control-operation-manual-series``.  Those revisions cover different
devices (timing, interlock, power source, power supply, PDU, collimator,
four-DOF platform, switch platform, laser heater, tuner, vacuum, temperature/
humidity, constant-temperature cabinet, laser and the data-archive clients) and
several revisions are editions or archive copies of the same manual.

This script rewrites exactly those 31 revisions, using an explicit
revision_id -> device/manual family mapping derived from the revision title and
revision_label.  It does not infer ``supersedes``, effective dates or approval
state.  The original series identity is retained as the tag
``series:shine-control-operation-manual-series``; every split revision also
gets a ``device:<slug>`` tag.

Only these fields are touched:

* ``family_id`` of the 31 mapped revisions;
* their ``tags`` (series tag + device tag are added, other tags preserved);
* ``target_family_id`` of the matching 31 dispositions;
* the ``families`` entry: the series family is replaced by one explicit family
  per device/manual.

Default mode is ``--dry-run``; pass ``--write`` to update the registry.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.corpus.schema_v2 import load_registry_v2  # noqa: E402

DEFAULT_REGISTRY = ROOT / "data/documents/v2/registry-v2.json"

SERIES_FAMILY_ID = "shine-control-operation-manual-series"
SERIES_TAG = f"series:{SERIES_FAMILY_ID}"
FAMILY_PREFIX = "shine-control-operation-manual-"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

EXPECTED_SPLIT_REVISIONS = 31


@dataclass(frozen=True)
class DeviceFamily:
    """One device/manual family and the revisions that belong to it."""

    device_slug: str
    title: str
    description: str
    revision_ids: tuple[str, ...]

    @property
    def family_id(self) -> str:
        return f"{FAMILY_PREFIX}{self.device_slug}"


# Explicit grouping evidence: revision titles/revision_labels identify the same
# device and manual.  First/second/third editions and archive copies stay with
# their device; no other relationship is asserted.
DEVICE_FAMILIES: tuple[DeviceFamily, ...] = (
    DeviceFamily(
        device_slug="timing",
        title="SHINE 定时系统界面操作手册（第一版 / 第二版 / 2023 归档副本）",
        description=(
            "SHINE 定时界面操作手册第一版、第二版（2023-12-06）与 2023 年"
            "归档副本（硬X射线自由电子激光装置项目定时系统控制界面操作说明）。"
        ),
        revision_ids=(
            "shine-control-operation-manual-series-rev-99ecefba",
            "shine-control-operation-manual-series-rev-73552d9f",
            "shine-control-operation-manual-series-rev-715c251d",
        ),
    ),
    DeviceFamily(
        device_slug="interlock",
        title="SHINE 联锁系统界面操作手册（第一版 / 第二版 / 2023、2024 归档副本）",
        description=(
            "SHINE 联锁界面操作手册第一版、第二版（2023-12-06）、2023 年"
            "联锁系统控制界面操作说明归档副本与 2024 年注入器联锁系统"
            "操作说明归档副本。"
        ),
        revision_ids=(
            "shine-control-operation-manual-series-rev-41ba2750",
            "shine-control-operation-manual-series-rev-2a16a52e",
            "shine-control-operation-manual-series-rev-a00f759c",
            "shine-control-operation-manual-series-rev-fba058ab",
        ),
    ),
    DeviceFamily(
        device_slug="power-source",
        title="SHINE 功率源控制界面操作说明（第一版 / 2023 归档副本）",
        description=(
            "SHINE 功率源控制界面操作说明第一版与 2023 年 1 号井功率源"
            "控制界面操作说明归档副本。功率源与电源按标题区分为不同设备。"
        ),
        revision_ids=(
            "shine-control-operation-manual-series-rev-ebbcf97e",
            "shine-control-operation-manual-series-rev-6aab6b8c",
        ),
    ),
    DeviceFamily(
        device_slug="power-supply",
        title="SHINE 电源控制界面操作说明（第一版 / 第二版 / 2023 归档副本）",
        description=(
            "SHINE 电源控制界面操作说明第一版、1 号井电源控制界面操作说明"
            "第二版（2023-12-07）与 2023 年 1 号井电源控制界面操作说明"
            "归档副本。"
        ),
        revision_ids=(
            "shine-control-operation-manual-series-rev-e6551458",
            "shine-control-operation-manual-series-rev-9aa08d8a",
            "shine-control-operation-manual-series-rev-fe5144f3",
        ),
    ),
    DeviceFamily(
        device_slug="pdu",
        title="SHINE 电源分配器 PDU 界面操作手册（第一版）",
        description="SHINE 电源分配器 PDU 界面操作手册第一版。",
        revision_ids=(
            "shine-control-operation-manual-series-rev-24e94d16",
        ),
    ),
    DeviceFamily(
        device_slug="collimator",
        title="SHINE 准直器界面操作手册（第一版 / 第三版）",
        description=(
            "SHINE 准直器界面操作手册第一版与 2024-11 第三版"
            "（SHINE 注入器段准直器控制界面操作手册）。"
        ),
        revision_ids=(
            "shine-control-operation-manual-series-rev-c05637cf",
            "shine-control-operation-manual-series-rev-afa68262",
        ),
    ),
    DeviceFamily(
        device_slug="four-dof-platform",
        title="SHINE 四自由度平台界面操作手册（第一版 / 第三版）",
        description=(
            "SHINE 四自由度平台界面操作手册第一版与 2024-11 第三版"
            "（SHINE 注入器段四自由度平台控制界面操作手册）。"
        ),
        revision_ids=(
            "shine-control-operation-manual-series-rev-2536c98d",
            "shine-control-operation-manual-series-rev-fd3c0264",
        ),
    ),
    DeviceFamily(
        device_slug="switch-platform",
        title="SHINE 注入器段切换平台控制界面操作手册（第三版）",
        description="SHINE 注入器段切换平台控制界面操作手册 2024-11 第三版。",
        revision_ids=(
            "shine-control-operation-manual-series-rev-b6698e8a",
        ),
    ),
    DeviceFamily(
        device_slug="laser-heater",
        title="SHINE 注入器段 Laser Heater 控制界面操作手册（第三版）",
        description="SHINE 注入器段 Laser Heater 控制界面操作手册 2024-11 第三版。",
        revision_ids=(
            "shine-control-operation-manual-series-rev-fd679514",
        ),
    ),
    DeviceFamily(
        device_slug="tuner",
        title="SHINE 注入器段调谐器控制界面操作手册（第三版）",
        description="SHINE 注入器段调谐器控制界面操作手册 2024-11 第三版。",
        revision_ids=(
            "shine-control-operation-manual-series-rev-eb5d6e0e",
        ),
    ),
    DeviceFamily(
        device_slug="vacuum",
        title="SHINE 注入段真空控制操作手册（第三版 / 2024 归档副本）",
        description=(
            "SHINE 注入段段真空控制界面操作手册 2024-11 第三版与 2024 年"
            "注入段真空控制操作手册归档副本。"
        ),
        revision_ids=(
            "shine-control-operation-manual-series-rev-96ebdc19",
            "shine-control-operation-manual-series-rev-b9bfd428",
        ),
    ),
    DeviceFamily(
        device_slug="temperature-humidity",
        title="SHINE 温湿度控制界面操作说明（第一版 / 2023 归档副本）",
        description=(
            "SHINE 温湿度控制界面操作说明第一版与 2023 年 1 号井温湿度"
            "控制界面操作说明归档副本。"
        ),
        revision_ids=(
            "shine-control-operation-manual-series-rev-f11c069c",
            "shine-control-operation-manual-series-rev-c6fe79d8",
        ),
    ),
    DeviceFamily(
        device_slug="constant-temperature-cabinet",
        title="SHINE 恒温机柜界面操作手册（第一版 / 2023 归档副本）",
        description=(
            "SHINE 恒温机柜界面操作手册第一版与 2023 年恒温机柜控制界面"
            "操作说明归档副本。"
        ),
        revision_ids=(
            "shine-control-operation-manual-series-rev-0e94a5e4",
            "shine-control-operation-manual-series-rev-300f0580",
        ),
    ),
    DeviceFamily(
        device_slug="laser",
        title="SHINE 激光界面操作手册（第一版）",
        description="SHINE 激光界面操作手册第一版。",
        revision_ids=(
            "shine-control-operation-manual-series-rev-b672c917",
        ),
    ),
    DeviceFamily(
        device_slug="archive-desktop",
        title="SHINE 数据存档系统 archiverDesktop 操作手册（第一版）",
        description="SHINE 数据存档系统 archiverDesktop 操作手册第一版。",
        revision_ids=(
            "shine-control-operation-manual-series-rev-fba2ad49",
        ),
    ),
    DeviceFamily(
        device_slug="archive-query",
        title="SHINE 数据存档系统查询软件操作手册（第一版 / 第二版 / 2024 归档副本）",
        description=(
            "SHINE 数据存档系统 web 查询软件操作手册第一版、archiver appliance "
            "数据存档系统 web 查询软件操作手册第二版（2023-12-06）与 2024 年 "
            "SHINE 存档数据查询软件操作手册归档副本。"
        ),
        revision_ids=(
            "shine-control-operation-manual-series-rev-f12c9ad8",
            "shine-control-operation-manual-series-rev-ec081ce3",
            "shine-control-operation-manual-series-rev-7da26046",
        ),
    ),
)

FAMILY_BY_ID = {family.family_id: family for family in DEVICE_FAMILIES}
REVISION_FAMILY_ID = {
    revision_id: family.family_id
    for family in DEVICE_FAMILIES
    for revision_id in family.revision_ids
}
REVISION_DEVICE_SLUG = {
    revision_id: family.device_slug
    for family in DEVICE_FAMILIES
    for revision_id in family.revision_ids
}


def _require_slug(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not SLUG_RE.fullmatch(value):
        raise SystemExit(
            f"{field_name} 必须是只含小写字母、数字和单个连字符的 slug: {value!r}"
        )


def _validate_mapping() -> None:
    """Reject duplicate or malformed entries before touching the registry."""

    if len(DEVICE_FAMILIES) < 2:
        raise SystemExit("拆分后至少需要两个设备族")
    family_ids: set[str] = set()
    device_slugs: set[str] = set()
    revision_ids: set[str] = set()
    for family in DEVICE_FAMILIES:
        _require_slug(family.device_slug, "device_slug")
        _require_slug(family.family_id, "family_id")
        if family.family_id != f"{FAMILY_PREFIX}{family.device_slug}":
            raise SystemExit(
                f"family_id 与 device_slug 不一致: {family.family_id} / "
                f"{family.device_slug}"
            )
        if family.family_id == SERIES_FAMILY_ID:
            raise SystemExit("新族不能复用原系列 family_id")
        if family.family_id in family_ids:
            raise SystemExit(f"重复 family_id: {family.family_id}")
        if family.device_slug in device_slugs:
            raise SystemExit(f"重复 device_slug: {family.device_slug}")
        if not family.title or not family.description:
            raise SystemExit(f"family 必须说明 title/description: {family.family_id}")
        if not family.revision_ids:
            raise SystemExit(f"family 必须包含 revision_id: {family.family_id}")
        for revision_id in family.revision_ids:
            _require_slug(revision_id, "revision_id")
            if revision_id in revision_ids:
                raise SystemExit(f"revision_id 出现在多个族: {revision_id}")
            revision_ids.add(revision_id)
        family_ids.add(family.family_id)
        device_slugs.add(family.device_slug)
    if len(revision_ids) != EXPECTED_SPLIT_REVISIONS:
        raise SystemExit(
            f"映射必须覆盖 {EXPECTED_SPLIT_REVISIONS} 个修订，"
            f"实际 {len(revision_ids)} 个"
        )
    if len(family_ids) != len(DEVICE_FAMILIES):
        raise SystemExit("family_id 统计不一致")


def _managed_tags(existing: object, device_slug: str) -> list[str]:
    if existing is None:
        tags: list[str] = []
    elif isinstance(existing, list) and all(isinstance(tag, str) for tag in existing):
        tags = list(existing)
    else:
        raise SystemExit("tags 必须是字符串数组")
    # Drop only tags this migration owns; preserve unrelated classifications.
    managed_slugs = {family.device_slug for family in DEVICE_FAMILIES}
    preserved = [
        tag
        for tag in tags
        if tag != SERIES_TAG
        and not (
            tag.startswith("device:") and tag[len("device:") :] in managed_slugs
        )
    ]
    return preserved + [SERIES_TAG, f"device:{device_slug}"]


def _family_entry(family: DeviceFamily, generated_on: str) -> dict[str, object]:
    return {
        "family_id": family.family_id,
        "title": family.title,
        "description": family.description,
        "revision_ids": sorted(family.revision_ids),
        "notes": (
            "F11 从 shine-control-operation-manual-series 拆出；按 title 与 "
            "revision_label 识别设备/手册后归族；未确认 supersedes、生效日期或"
            "批准状态。"
        ),
        "created_at": generated_on,
    }


def _split_registry(data: dict[str, object]) -> tuple[dict[str, object], dict[str, int]]:
    """Return the rewritten registry and a small change summary."""

    _validate_mapping()
    if data.get("schema_version") != 2:
        raise SystemExit("只支持 schema_version=2 的登记表")
    revisions = data.get("revisions")
    families = data.get("families")
    dispositions = data.get("dispositions")
    if not isinstance(revisions, list):
        raise SystemExit("revisions 必须是数组")
    if not isinstance(families, list):
        raise SystemExit("families 必须是数组")
    if not isinstance(dispositions, list):
        raise SystemExit("dispositions 必须是数组")
    original = copy.deepcopy(data)
    updated = copy.deepcopy(data)

    revisions_by_id: dict[str, dict[str, object]] = {}
    for revision in updated["revisions"]:
        revision_id = revision.get("revision_id")
        if not isinstance(revision_id, str):
            raise SystemExit("revision 缺少 revision_id")
        if revision_id in revisions_by_id:
            raise SystemExit(f"重复 revision_id: {revision_id}")
        revisions_by_id[revision_id] = revision

    # Every mapped revision must either still be in the series family or already
    # be in its target family; anything else means the registry drifted.
    for revision_id, family_id in REVISION_FAMILY_ID.items():
        revision = revisions_by_id.get(revision_id)
        if revision is None:
            raise SystemExit(f"映射中的修订不存在: {revision_id}")
        current = revision.get("family_id")
        if current not in {SERIES_FAMILY_ID, family_id}:
            raise SystemExit(
                f"修订 {revision_id} 当前属于 {current!r}，"
                f"既不是原系列也不是目标族 {family_id}"
            )

    # The old series family must contain exactly the mapped revisions; no
    # unmapped revision may be silently absorbed into the split.
    series_revisions = {
        revision_id
        for revision_id, revision in revisions_by_id.items()
        if revision.get("family_id") == SERIES_FAMILY_ID
    }
    unmapped_series = series_revisions - set(REVISION_FAMILY_ID)
    if unmapped_series:
        raise SystemExit(
            "原系列中存在未映射的修订，拒绝改变: "
            + ", ".join(sorted(unmapped_series))
        )

    for revision_id, family_id in REVISION_FAMILY_ID.items():
        revision = revisions_by_id[revision_id]
        revision["family_id"] = family_id
        revision["tags"] = _managed_tags(
            revision.get("tags"), REVISION_DEVICE_SLUG[revision_id]
        )

    # Dispositions carry target_family_id and must stay consistent with the
    # revision family (RegistryV2 validates this).
    mapped_paths: set[tuple[str, str]] = set()
    disposition_by_path: dict[tuple[str, str], dict[str, object]] = {}
    for disposition in updated["dispositions"]:
        key = (disposition.get("batch_id"), disposition.get("source_path"))
        if not all(isinstance(part, str) for part in key):
            raise SystemExit("disposition 缺少 batch_id/source_path")
        if key in disposition_by_path:
            raise SystemExit(f"重复 disposition: {key}")
        disposition_by_path[key] = disposition

    for revision_id, family_id in REVISION_FAMILY_ID.items():
        revision = revisions_by_id[revision_id]
        key = (revision.get("batch_id"), revision.get("source_path"))
        mapped_paths.add(key)
        disposition = disposition_by_path.get(key)
        if disposition is None:
            raise SystemExit(f"修订缺少对应 disposition: {revision_id}")
        current = disposition.get("target_family_id", "")
        if current not in {"", SERIES_FAMILY_ID, family_id}:
            raise SystemExit(
                f"disposition {key} 的 target_family_id={current!r} "
                f"与目标族 {family_id} 不一致"
            )
        disposition["target_family_id"] = family_id

    for key, disposition in disposition_by_path.items():
        if key in mapped_paths:
            continue
        if disposition.get("target_family_id") == SERIES_FAMILY_ID:
            raise SystemExit(
                f"未映射 disposition 仍指向原系列: {key}"
            )

    # Replace the old series family (wherever it sits) with the explicit
    # device families, sorted for deterministic output.
    generated_on = data.get("generated_on")
    if not isinstance(generated_on, str) or not generated_on:
        raise SystemExit("登记表缺少 generated_on")
    desired = [
        _family_entry(family, generated_on)
        for family in sorted(DEVICE_FAMILIES, key=lambda item: item.family_id)
    ]
    removed_indices = [
        index
        for index, family in enumerate(updated["families"])
        if family.get("family_id") == SERIES_FAMILY_ID
        or family.get("family_id") in FAMILY_BY_ID
    ]
    if not removed_indices:
        raise SystemExit("既没有原系列族，也没有已拆分的目标族；登记表状态异常")
    insert_at = min(removed_indices)
    existing_target_ids = {
        family.get("family_id")
        for family in updated["families"]
        if family.get("family_id") in FAMILY_BY_ID
    }
    expected_target_ids = set(FAMILY_BY_ID)
    if existing_target_ids and not series_revisions:
        if existing_target_ids != expected_target_ids:
            raise SystemExit(
                "目标族不完整: "
                + ", ".join(sorted(expected_target_ids - existing_target_ids))
            )
    for family in updated["families"]:
        family_id = family.get("family_id")
        if family_id in FAMILY_BY_ID:
            unknown = set(family.get("revision_ids", [])) - set(REVISION_FAMILY_ID)
            if unknown:
                raise SystemExit(
                    f"目标族 {family_id} 含有映射外修订: {sorted(unknown)}"
                )
    remaining = [
        family
        for index, family in enumerate(updated["families"])
        if index not in set(removed_indices)
    ]
    updated["families"] = remaining[:insert_at] + desired + remaining[insert_at:]

    _assert_change_scope(original, updated, mapped_paths)

    summary = {
        "revisions": len(updated["revisions"]),
        "split_revisions": len(REVISION_FAMILY_ID),
        "device_families": len(DEVICE_FAMILIES),
        "untouched_revisions": len(updated["revisions"]) - len(REVISION_FAMILY_ID),
        "changed_dispositions": len(mapped_paths),
        "family_count_before": len(original["families"]),
        "family_count_after": len(updated["families"]),
    }
    return updated, summary


def _assert_change_scope(
    original: dict[str, object],
    updated: dict[str, object],
    mapped_paths: set[tuple[str, str]],
) -> None:
    """Prove that only the mapped revisions/families/dispositions changed."""

    before_revisions = {
        revision["revision_id"]: revision for revision in original["revisions"]
    }
    after_revisions = {
        revision["revision_id"]: revision for revision in updated["revisions"]
    }
    if list(before_revisions) != list(after_revisions):
        raise SystemExit("revision 顺序或集合发生了变化")
    for revision_id, before in before_revisions.items():
        after = after_revisions[revision_id]
        if revision_id not in REVISION_FAMILY_ID:
            if before != after:
                raise SystemExit(f"非映射修订被修改: {revision_id}")
            continue
        before_payload = {
            key: value
            for key, value in before.items()
            if key not in {"family_id", "tags"}
        }
        after_payload = {
            key: value
            for key, value in after.items()
            if key not in {"family_id", "tags"}
        }
        if before_payload != after_payload:
            raise SystemExit(f"映射修订的 family/tags 之外的字段被修改: {revision_id}")

    before_dispositions = {
        (item["batch_id"], item["source_path"]): item
        for item in original["dispositions"]
    }
    after_dispositions = {
        (item["batch_id"], item["source_path"]): item
        for item in updated["dispositions"]
    }
    if list(before_dispositions) != list(after_dispositions):
        raise SystemExit("disposition 顺序或集合发生了变化")
    for key, before in before_dispositions.items():
        after = after_dispositions[key]
        if key not in mapped_paths:
            if before != after:
                raise SystemExit(f"非映射 disposition 被修改: {key}")
            continue
        before_payload = {
            name: value
            for name, value in before.items()
            if name != "target_family_id"
        }
        after_payload = {
            name: value
            for name, value in after.items()
            if name != "target_family_id"
        }
        if before_payload != after_payload:
            raise SystemExit(f"映射 disposition 的 target_family_id 之外字段被修改: {key}")

    # Target families are owned by this migration and may be re-rendered on a
    # re-run (for example after a metadata fix); every other family must stay
    # byte-for-byte identical.
    before_families = {
        family["family_id"]: family
        for family in original["families"]
        if family["family_id"] != SERIES_FAMILY_ID
        and family["family_id"] not in FAMILY_BY_ID
    }
    after_families = {
        family["family_id"]: family
        for family in updated["families"]
        if family["family_id"] not in FAMILY_BY_ID
    }
    if set(after_families) != set(before_families):
        raise SystemExit("family 集合不只是原系列被替换")
    for family_id, before in before_families.items():
        if after_families[family_id] != before:
            raise SystemExit(f"非拆分 family 被修改: {family_id}")
    if not set(FAMILY_BY_ID) <= {
        family["family_id"] for family in updated["families"]
    }:
        raise SystemExit("拆分后的设备族不完整")


def _print_summary(
    path: Path,
    summary: dict[str, int],
    write: bool,
) -> None:
    print(f"registry: {path}")
    print(f"series family: {SERIES_FAMILY_ID} (family removed, tag kept)")
    print(
        f"split revisions: {summary['split_revisions']} -> "
        f"{summary['device_families']} device/manual families"
    )
    print()
    print(f"{'family_id':<58} {'n':>2}  revision_ids")
    for family in sorted(DEVICE_FAMILIES, key=lambda item: item.family_id):
        revision_ids = ", ".join(sorted(family.revision_ids))
        print(f"{family.family_id:<58} {len(family.revision_ids):>2}  {revision_ids}")
    print()
    print(
        f"revisions: {summary['revisions']} total; "
        f"{summary['split_revisions']} split; "
        f"{summary['untouched_revisions']} untouched"
    )
    print(
        f"families: {summary['family_count_before']} -> "
        f"{summary['family_count_after']}"
    )
    print(f"dispositions retargeted: {summary['changed_dispositions']}")
    if write:
        print(f"wrote: {path}")
    else:
        print(f"dry-run: no file written; pass --write to update {path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Split the SHINE operation-manual series family into explicit "
            "device/manual families (F11)."
        )
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help=f"registry-v2.json path (default: {DEFAULT_REGISTRY})",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="print the mapping and change summary without writing (default)",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="write the updated registry back to --registry",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    registry_path = args.registry.resolve()
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"registry v2 不是合法 JSON: line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(data, dict):
        raise SystemExit("registry 根节点必须是 JSON 对象")

    updated, summary = _split_registry(data)
    _print_summary(registry_path, summary, write=args.write)

    if not args.write:
        return 0
    if updated == data:
        print("already applied: registry unchanged")
        return 0
    descriptor, temporary = tempfile.mkstemp(
        dir=registry_path.parent,
        prefix=".registry-v2-split-",
        suffix=".json",
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(updated, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        load_registry_v2(temporary_path)
        os.replace(temporary_path, registry_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
