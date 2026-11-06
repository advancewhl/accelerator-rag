"""Register the 2026-11-05 SHINE network cable/switch tables in registry v2.

Usage::

    python scripts/register_cable_tables.py <extracted SHINE线缆表 dir>

The originals are copied (never moved or modified) into
``data/l0_raw/incoming/2026-11-05-shine-cables/SHINE线缆表/``.  Byte-identical
files are registered once; the extra copy gets an ``excluded`` disposition so
the batch still accounts for every input file.  The script is idempotent: an
existing revision with the same ``revision_id`` is replaced, not duplicated.

Governance facts recorded here are only what the files show: file name, sheet
coverage and the "已核对/已发" markers in the file name.  Approval, field
deployment state and supersession between the 2023 table and the later
per-section tables are not known and stay ``unknown`` / unlinked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.corpus.schema_v2 import RegistryV2  # noqa: E402

BATCH_ID = "2026-11-05-shine-cables"
RAW_DIR = ROOT / "data/l0_raw/incoming" / BATCH_ID / "SHINE线缆表"
REGISTRY = ROOT / "data/documents/v2/registry-v2.json"
RECEIVED = "2026-11-05"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(name: str) -> str:
    """Stable ASCII slug from the section part of a file name."""

    stem = Path(name).stem
    stem = re.sub(r"^(已核对-)?(已发-)?", "", stem)
    ascii_part = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    digest = hashlib.sha1(stem.encode("utf-8")).hexdigest()[:6]
    return f"{ascii_part or 'table'}-{digest}"


def describe(name: str) -> dict:
    stem = Path(name).stem
    tags = ["batch-2026-11-05", "network-cabling"]
    if "已核对" in stem:
        tags.append("marked-checked")
    if "已发" in stem:
        tags.append("marked-issued")
    switch_config = "交换机配置表" in stem
    kind = "configuration_snapshot" if switch_config else "structured_list"
    family_prefix = "network-switch-config" if switch_config else "network-cable-table"
    date = ""
    precision = "unknown"
    match = re.search(r"(20\d{2})(\d{2})(\d{2})", stem)
    if match:
        date = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        precision = "day"
    if switch_config:
        reason = (
            "交换机网口配置表：按设备/端口段登记所属系统与 VLAN；"
            "行列级结构化索引，端口号可按区间查询。"
        )
    else:
        reason = (
            "网络系统线缆表：按机柜/交换机分组登记电缆编号、始端/终端机柜、"
            "设备用途与网络类别；行列级结构化索引。"
        )
    reason += (
        " 文件名中的“已核对/已发”仅作标签；批准状态、现场敷设状态"
        "及与其他分段表的替代关系均未确认。"
    )
    return {
        "family_prefix": family_prefix,
        "document_kind": kind,
        "tags": tags,
        "document_date": date,
        "date_precision": precision,
        "reason": reason,
        "title": re.sub(r"^(已核对-)?(已发-)?", "", stem),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source_dir", type=Path)
    args = parser.parse_args()
    # A "副本"/"copy" name sorts after its original so the original is the
    # registered revision and the copy is the excluded duplicate.
    sources = sorted(
        (
            path
            for path in args.source_dir.iterdir()
            if path.suffix.lower() in {".xlsx", ".xls"}
            and not path.name.startswith("~$")
        ),
        key=lambda path: (
            "副本" in path.stem or "copy" in path.stem.lower(),
            path.name,
        ),
    )
    if not sources:
        print("no .xlsx/.xls files found", file=sys.stderr)
        return 1
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    revisions = [r for r in registry["revisions"] if r["batch_id"] != BATCH_ID]
    families = [
        f
        for f in registry["families"]
        if not f["family_id"].startswith(("network-cable-table-", "network-switch-config-"))
    ]
    dispositions = [d for d in registry["dispositions"] if d["batch_id"] != BATCH_ID]

    seen: dict[str, str] = {}
    added = 0
    for source in sources:
        target = RAW_DIR / source.name
        if not target.exists() or sha256(target) != sha256(source):
            shutil.copy2(source, target)
        digest = sha256(target)
        relative = target.relative_to(ROOT).as_posix()
        batch_relative = f"SHINE线缆表/{source.name}"
        source_format = target.suffix.lower().lstrip(".")
        info = describe(source.name)
        if digest in seen:
            dispositions.append(
                {
                    "batch_id": BATCH_ID,
                    "batch_relative_path": batch_relative,
                    "source_path": relative,
                    "source_format": source_format,
                    "document_kind": info["document_kind"],
                    "priority": "P3",
                    "disposition": "excluded",
                    "planned_action": "exclude",
                    "reason": f"与 {seen[digest]} 字节完全相同（sha256 {digest[:12]}），不重复入库。",
                    "target_family_id": "",
                    "notes": "duplicate copy",
                }
            )
            continue
        seen[digest] = source.name
        family_id = f"{info['family_prefix']}-{slug(source.name)}"
        revision_id = f"{family_id}-rev"
        revisions.append(
            {
                "family_id": family_id,
                "revision_id": revision_id,
                "title": info["title"],
                "revision_label": f"SHINE线缆表 | {source.name}",
                "batch_id": BATCH_ID,
                "original_asset_id": f"asset-{revision_id}",
                "source_path": relative,
                "source_format": source_format,
                "language": "zh",
                "document_kind": info["document_kind"],
                "category": "control_system",
                "topic": "network",
                "evidence_role": "background_reference",
                "usage_status": "reference",
                "approval_status": "unknown",
                "disposition": "structured_index",
                "reason": info["reason"],
                "received_at": RECEIVED,
                "document_date": info["document_date"],
                "effective_from": "",
                "effective_to": "",
                "date_precision": info["date_precision"],
                "owner": "unknown",
                "source_authority": "user-upload-2026-11-05",
                "access_scope": "internal",
                "parser_profile": (
                    "xls-converted-xlsx-v1" if source_format == "xls" else "openpyxl-cells-v1"
                ),
                "conversion_profile": "",
                "ocr_profile": "",
                "review_record": (
                    f"registered by scripts/register_cable_tables.py; sha256={digest}; "
                    "no document-level review"
                ),
                "reviewed_by": "",
                "reviewed_at": "",
                "tags": info["tags"],
                "scope": [],
                "applicable_versions": [],
                "supersedes": [],
                "equivalent_to": [],
                "contains": [],
                "supplements": [],
                "derived_from": [],
            }
        )
        families.append(
            {
                "family_id": family_id,
                "title": info["title"],
                "description": "SHINE 网络系统线缆/交换机配置分段表（单修订）。",
                "revision_ids": [revision_id],
                "notes": "confidence=high; single revision received 2026-11-05",
                "created_at": RECEIVED,
            }
        )
        dispositions.append(
            {
                "batch_id": BATCH_ID,
                "batch_relative_path": batch_relative,
                "source_path": relative,
                "source_format": source_format,
                "document_kind": info["document_kind"],
                "priority": "P1",
                "disposition": "structured_index",
                "planned_action": "structured",
                "reason": info["reason"],
                "target_family_id": family_id,
                "notes": f"sha256={digest}",
            }
        )
        added += 1

    registry["revisions"] = revisions
    registry["families"] = families
    registry["dispositions"] = dispositions
    RegistryV2.from_dict(registry)  # schema validation before writing
    REGISTRY.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"registered {added} revisions; {len(sources) - added} duplicate(s) excluded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
