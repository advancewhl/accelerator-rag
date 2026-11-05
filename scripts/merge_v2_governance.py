#!/usr/bin/env python3
"""Merge legacy migrations, batch dispositions, family candidates and conflicts.

The output is reviewable metadata only.  It does not parse documents, assign
approval, or mark any batch document ``current``: unapproved P0/operational
material becomes ``pending_review``; archived material becomes ``historical``;
other design/standards/test evidence becomes ``reference``.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.corpus.schema_v2 import (  # noqa: E402
    AccessScope,
    ApprovalStatus,
    ConflictLedger,
    ConflictRecord,
    Disposition,
    DispositionRecord,
    DocumentFamily,
    DocumentKind,
    EvidenceRole,
    PlannedAction,
    RegistryV2,
    RevisionRecord,
    UsageStatus,
    load_registry_v2,
    write_conflict_ledger,
    write_registry_v2,
)


BATCH_ID = "2026-11-02-shine-control"
BATCH_ROOT = "data/l0_raw/incoming/2026-11-02-shine-control/资料/"
DEFAULT_REGISTRY = ROOT / "data/documents/v2/registry-v2.json"
DEFAULT_DISPOSITIONS = ROOT / "data/documents/v2/dispositions.draft.json"
DEFAULT_FAMILIES = ROOT / "data/documents/v2/family-candidates.draft.json"
DEFAULT_CONFLICTS = ROOT / "data/documents/v2/conflict-candidates.draft.json"
DEFAULT_OUTPUT = ROOT / "data/documents/v2/registry-v2.json"
DEFAULT_CONFLICT_OUTPUT = ROOT / "data/documents/v2/conflicts.json"
DEFAULT_REPORT = ROOT / "data/documents/v2/governance-merge-report.json"

_USAGE_BY_KIND = {
    DocumentKind.OPERATION_MANUAL.value: UsageStatus.PENDING_REVIEW,
    DocumentKind.INSTALLATION_MAINTENANCE.value: UsageStatus.PENDING_REVIEW,
    DocumentKind.UNKNOWN.value: UsageStatus.PENDING_REVIEW,
}

_ROLE_BY_KIND = {
    DocumentKind.OVERALL_DESIGN.value: EvidenceRole.DESIGN_TARGET,
    DocumentKind.SUBSYSTEM_DESIGN.value: EvidenceRole.DESIGN_TARGET,
    DocumentKind.STANDARD_SPECIFICATION.value: EvidenceRole.SPECIFICATION_REQUIREMENT,
    DocumentKind.INTERFACE_SPECIFICATION.value: EvidenceRole.SPECIFICATION_REQUIREMENT,
    DocumentKind.OPERATION_MANUAL.value: EvidenceRole.OPERATING_STEP,
    DocumentKind.INSTALLATION_MAINTENANCE.value: EvidenceRole.OPERATING_STEP,
    DocumentKind.TEST_PLAN.value: EvidenceRole.TEST_RESULT,
    DocumentKind.TEST_REPORT.value: EvidenceRole.TEST_RESULT,
    DocumentKind.ACCEPTANCE_REPORT.value: EvidenceRole.ACCEPTANCE_CONCLUSION,
    DocumentKind.DEVELOPMENT_SUMMARY.value: EvidenceRole.HISTORICAL_RECORD,
    DocumentKind.REVIEW_OPINION.value: EvidenceRole.HISTORICAL_RECORD,
    DocumentKind.MEETING_RECORD.value: EvidenceRole.HISTORICAL_RECORD,
    DocumentKind.PAPER.value: EvidenceRole.BACKGROUND_REFERENCE,
    DocumentKind.CONFIGURATION_SNAPSHOT.value: EvidenceRole.BACKGROUND_REFERENCE,
    DocumentKind.STRUCTURED_LIST.value: EvidenceRole.BACKGROUND_REFERENCE,
    DocumentKind.DRAWING.value: EvidenceRole.BACKGROUND_REFERENCE,
    DocumentKind.UNKNOWN.value: EvidenceRole.UNKNOWN,
}

_TOPIC_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("网络安全", "信息安全"), "cybersecurity"),
    (("联锁",), "interlock"),
    (("定时", "白兔", "时序"), "timing"),
    (("真空",), "vacuum"),
    (("低温", "恒温"), "cryogenics"),
    (("激光",), "laser"),
    (("运动", "电机", "四自由度", "调谐器", "准直器", "切换平台"), "motion_control"),
    (("pdu", "电源分配"), "pdu"),
    (("电源", "功率源", "热备"), "power_supply"),
    (("存档", "archiver"), "archiver"),
    (("数据存储", "数据库", "mysql"), "data_storage"),
    (("网络", "交换机", "snmp", "nagios"), "network"),
    (("报警", "告警"), "alarm"),
    (("epics",), "epics"),
    (("ioc", "opi", "pv"), "ioc"),
    (("界面", "操作手册", "操作说明"), "gui"),
    (("命名", "规范", "标准", "代号"), "standards"),
    (("验收",), "acceptance"),
    (("评审",), "review"),
    (("图像", "采集", "波形"), "data_acquisition"),
    (("安装", "维护"), "installation"),
    (("设计", "报告"), "design"),
)

_DATE_DAY_SEPARATED = re.compile(
    r"(?<!\d)(20\d{2})[-_.](0?[1-9]|1[0-2])[-_.](0?[1-9]|[12]\d|3[01])(?!\d)"
)
_DATE_DAY_COMPACT = re.compile(
    r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)"
)
_DATE_MONTH_SEPARATED = re.compile(
    r"(?<!\d)(20\d{2})[-_.](0?[1-9]|1[0-2])(?![\d])"
)
_DATE_MONTH_COMPACT = re.compile(
    r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(?!\d)"
)
_DATE_YEAR = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--dispositions", type=Path, default=DEFAULT_DISPOSITIONS)
    parser.add_argument("--families", type=Path, default=DEFAULT_FAMILIES)
    parser.add_argument("--conflicts", type=Path, default=DEFAULT_CONFLICTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--conflict-output", type=Path, default=DEFAULT_CONFLICT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--generated-on", default="2026-11-02")
    return parser.parse_args()


def _sha8(value: str) -> str:
    return sha256(value.encode()).hexdigest()[:8]


def _slug(value: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _derive_family_id(path: str, title: str, document_kind: str) -> str:
    topic = _classify(path, title).replace("_", "-")
    kind = document_kind.replace("_", "-")
    return f"{topic}-{kind}-{_sha8(path)}"


def _title(path: str) -> str:
    stem = PurePosixPath(path).stem.strip()
    if not stem:
        raise ValueError(f"cannot derive title from {path}")
    return stem


def _revision_label(path: str) -> str:
    relative = path[len(BATCH_ROOT) :] if path.startswith(BATCH_ROOT) else path
    pure = PurePosixPath(relative)
    stem = pure.stem
    parent = pure.parent.as_posix()
    if parent in {"", "."}:
        return f"batch-2026-11-02 | {stem}"
    return f"{parent} | {stem}"


def _language(title: str) -> str:
    if re.search(r"[一-鿿]", title):
        return "zh"
    if re.search(r"[A-Za-z]", title):
        return "en"
    return "unknown"


def _classify(path: str, title: str) -> str:
    text = f"{path} {title}".casefold()
    for keywords, topic in _TOPIC_RULES:
        if any(keyword.casefold() in text for keyword in keywords):
            return topic
    return "control_architecture"


def _usage_status(priority: str, kind: str, path: str) -> str:
    if priority == "P0":
        return UsageStatus.PENDING_REVIEW.value
    if "归档" in path:
        return UsageStatus.HISTORICAL.value
    if kind in _USAGE_BY_KIND:
        return _USAGE_BY_KIND[kind].value
    return UsageStatus.REFERENCE.value


def _access_scope(path: str, title: str) -> str:
    text = f"{path} {title}"
    if any(
        keyword in text
        for keyword in ("网络安全", "安全管理", "IP地址", "地址分配", "账号", "密码")
    ):
        return AccessScope.RESTRICTED.value
    return AccessScope.INTERNAL.value


def _parser_profile(action: str, source_format: str) -> tuple[str, str, str]:
    if action == PlannedAction.OCR.value:
        return "pending-ocr", "", "tesseract-pending"
    if action == PlannedAction.CONVERT.value:
        return (
            f"pending-{source_format}-conversion",
            "libreoffice-pending" if source_format == "doc" else "",
            "",
        )
    if action == PlannedAction.STRUCTURED.value:
        return "pending-structured-parse", "", ""
    return "pending-kb2-parse", "", ""


def _date_from_filename(path: str) -> tuple[str, str]:
    stem = PurePosixPath(path).stem
    candidates = (
        (_DATE_DAY_SEPARATED, "day"),
        (_DATE_DAY_COMPACT, "day"),
        (_DATE_MONTH_COMPACT, "month"),
        (_DATE_MONTH_SEPARATED, "month"),
        (_DATE_YEAR, "year"),
    )
    formats = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}
    for pattern, precision in candidates:
        match = pattern.search(stem)
        if match is None:
            continue
        groups = match.groups()
        if precision == "day":
            value = f"{groups[0]}-{int(groups[1]):02d}-{int(groups[2]):02d}"
        elif precision == "month":
            value = f"{groups[0]}-{int(groups[1]):02d}"
        else:
            value = groups[0]
        try:
            datetime.strptime(value, formats[precision])
        except ValueError:
            continue
        return value, precision
    return "", "unknown"


def _revision_from_disposition(item: DispositionRecord) -> RevisionRecord:
    if item.disposition not in {
        Disposition.TEXT_INDEX.value,
        Disposition.STRUCTURED_INDEX.value,
    }:
        raise ValueError("only text/structured dispositions create revisions")
    if item.batch_id != BATCH_ID:
        raise ValueError(f"unexpected batch_id: {item.batch_id}")
    title = _title(item.source_path)
    family_id = item.target_family_id or _derive_family_id(
        item.source_path, title, item.document_kind
    )
    date, precision = _date_from_filename(item.source_path)
    parser_profile, conversion_profile, ocr_profile = _parser_profile(
        item.planned_action, item.source_format
    )
    revision_suffix = (
        f"-rev-{_sha8(item.source_path)}" if item.target_family_id else "-rev"
    )
    revision_id = f"{family_id}{revision_suffix}"
    return RevisionRecord(
        family_id=family_id,
        revision_id=revision_id,
        title=title,
        revision_label=_revision_label(item.source_path),
        batch_id=item.batch_id,
        original_asset_id=f"asset-{revision_id}",
        source_path=item.source_path,
        source_format=item.source_format,
        language=_language(title),
        document_kind=item.document_kind,
        category="control_system",
        topic=_classify(item.source_path, title),
        evidence_role=_ROLE_BY_KIND[item.document_kind].value,
        usage_status=_usage_status(item.priority, item.document_kind, item.source_path),
        approval_status=ApprovalStatus.UNKNOWN.value,
        disposition=item.disposition,
        reason=(
            item.reason
            + " 批次治理候选；批准状态、现行适用性与现场部署均未确认。"
        ),
        received_at="2026-11-02",
        document_date=date,
        date_precision=precision,
        owner="unknown",
        source_authority="batch-analysis-2026-11-02",
        access_scope=_access_scope(item.source_path, title),
        parser_profile=parser_profile,
        conversion_profile=conversion_profile,
        ocr_profile=ocr_profile,
        review_record=(
            "generated from document-decisions.csv/ANALYSIS; no document-level "
            "review; document_date (if any) is extracted from the filename"
        ),
        tags=("batch-2026-11-02",),
    )


def _load_family_candidates(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 2:
        raise ValueError("family candidates schema_version must be 2")
    families = payload.get("families")
    if not isinstance(families, list):
        raise ValueError("family candidates must contain a families list")
    return families


def _resolve_families(
    revisions: list[RevisionRecord], candidates: list[dict], generated_on: str
) -> tuple[list[RevisionRecord], list[DocumentFamily], list[dict]]:
    by_id = {revision.revision_id: revision for revision in revisions}
    by_path = {revision.source_path: revision for revision in revisions}
    assigned: dict[str, str] = {}
    overrides: dict[str, dict] = {}
    unresolved: list[dict] = []
    updated = {revision.revision_id: revision for revision in revisions}
    for candidate in candidates:
        family_id = candidate["family_id"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", family_id):
            raise ValueError(f"invalid family_id: {family_id}")
        resolved: list[str] = []
        missing: list[dict] = []
        for member in candidate["members"]:
            if member["kind"] == "legacy_doc_id":
                revision_id = member["value"]
                if revision_id in by_id:
                    resolved.append(revision_id)
                else:
                    missing.append(member)
            elif member["kind"] == "batch_path":
                revision = by_path.get(BATCH_ROOT + member["value"])
                if revision is None:
                    missing.append(member)
                else:
                    resolved.append(revision.revision_id)
            else:
                missing.append(member)
        for revision_id in resolved:
            previous = assigned.get(revision_id)
            if previous is not None and previous != family_id:
                raise ValueError(
                    f"revision {revision_id} belongs to two families: "
                    f"{previous} and {family_id}"
                )
            assigned[revision_id] = family_id
        if not resolved:
            unresolved.append(
                {
                    "family_id": family_id,
                    "title": candidate.get("title", ""),
                    "missing": missing,
                }
            )
            continue
        note = (
            f"confidence={candidate.get('confidence', 'unknown')}; "
            f"needs_confirmation={candidate.get('needs_confirmation', True)}; "
            f"evidence={candidate.get('evidence', '')}"
        )
        description = candidate.get("description", "")
        if missing:
            description += (
                " 未纳入修订的成员（无文本索引或未解析）: "
                + "; ".join(
                    m["value"] for m in missing if isinstance(m.get("value"), str)
                )
            )
        overrides[family_id] = {
            "title": candidate.get("title") or _title(
                updated[resolved[0]].source_path
            ),
            "description": description,
            "notes": note,
        }
        for revision_id in resolved:
            updated[revision_id] = replace(updated[revision_id], family_id=family_id)
    # A revision whose target_family_id is not a candidate keeps that family ID;
    # it will become a batch-derived family below.
    grouped: dict[str, list[str]] = defaultdict(list)
    for revision in updated.values():
        grouped[revision.family_id].append(revision.revision_id)
    families: list[DocumentFamily] = []
    for family_id in sorted(grouped):
        revision_ids = tuple(sorted(grouped[family_id]))
        override = overrides.get(family_id)
        if override:
            title = override["title"]
            description = override["description"]
            notes = override["notes"]
        else:
            first = updated[revision_ids[0]]
            title = first.title
            description = "Batch or legacy-derived family with no confirmed relationship."
            notes = "single-revision placeholder; merge only with evidence"
        families.append(
            DocumentFamily(
                family_id=family_id,
                title=title,
                description=description,
                revision_ids=revision_ids,
                notes=notes,
                created_at=generated_on,
            )
        )
    return list(updated.values()), families, unresolved


def _apply_operation_manual_split(
    revisions: list[RevisionRecord],
    families: list[DocumentFamily],
    generated_on: str,
) -> tuple[list[RevisionRecord], list[DocumentFamily]]:
    """Apply the reviewed device/manual split as part of the merge, not as a
    manual post-processing step."""

    from split_operation_manual_families import (  # noqa: PLC0415
        DEVICE_FAMILIES,
        FAMILY_BY_ID,
        REVISION_DEVICE_SLUG,
        REVISION_FAMILY_ID,
        SERIES_FAMILY_ID,
        SERIES_TAG,
    )

    updated = []
    counts: dict[str, int] = {}
    for revision in revisions:
        family_id = REVISION_FAMILY_ID.get(revision.revision_id)
        if family_id is None:
            updated.append(revision)
            continue
        counts[family_id] = counts.get(family_id, 0) + 1
        device_slug = REVISION_DEVICE_SLUG[revision.revision_id]
        tags = [
            tag
            for tag in revision.tags
            if tag != SERIES_TAG and not tag.startswith("device:")
        ]
        tags.extend([SERIES_TAG, f"device:{device_slug}"])
        updated.append(
            replace(
                revision,
                family_id=family_id,
                tags=tuple(dict.fromkeys(tags)),
            )
        )
    if not counts:
        return updated, families
    missing = {
        family.family_id: len(family.revision_ids) - counts.get(family.family_id, 0)
        for family in DEVICE_FAMILIES
        if counts.get(family.family_id, 0) != len(family.revision_ids)
    }
    if missing:
        raise SystemExit(
            "operation-manual split cannot be applied; revision membership "
            f"does not match the reviewed mapping: {missing}"
        )
    kept = [
        family
        for family in families
        if family.family_id != SERIES_FAMILY_ID
        and family.family_id not in FAMILY_BY_ID
    ]
    created = [
        DocumentFamily(
            family_id=family.family_id,
            title=family.title,
            description=family.description,
            revision_ids=family.revision_ids,
            notes="device/manual split from shine-control-operation-manual-series",
            created_at=generated_on,
        )
        for family in DEVICE_FAMILIES
    ]
    return updated, kept + created


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    args = parse_args()
    legacy = load_registry_v2(args.registry)
    if any(revision.batch_id != "legacy-baseline" for revision in legacy.revisions):
        raise SystemExit(
            "input registry already contains batch revisions; pass "
            "--registry data/documents/v2/registry-v2.legacy-baseline.json "
            "(never merge the merged output again)"
        )
    dispositions_payload = json.loads(
        args.dispositions.read_text(encoding="utf-8")
    )
    if dispositions_payload.get("batch_id") != BATCH_ID:
        raise SystemExit(f"unexpected disposition batch: {dispositions_payload.get('batch_id')}")
    batch_dispositions = tuple(
        DispositionRecord.from_dict(item)
        for item in dispositions_payload["dispositions"]
    )
    if len(batch_dispositions) != 218:
        raise SystemExit(
            f"expected 218 batch dispositions, got {len(batch_dispositions)}"
        )
    if len({item.source_path for item in batch_dispositions}) != 218:
        raise SystemExit("duplicate source_path in batch dispositions")
    missing_files = [
        item.source_path
        for item in batch_dispositions
        if not (ROOT / item.source_path).is_file()
    ]
    if missing_files:
        raise SystemExit(
            "batch dispositions reference missing files: "
            + "; ".join(missing_files[:10])
        )

    new_revisions = [
        _revision_from_disposition(item)
        for item in batch_dispositions
        if item.disposition
        in {Disposition.TEXT_INDEX.value, Disposition.STRUCTURED_INDEX.value}
    ]
    family_candidates = _load_family_candidates(args.families)
    revisions, families, unresolved = _resolve_families(
        list(legacy.revisions) + new_revisions,
        family_candidates,
        args.generated_on,
    )
    revisions, families = _apply_operation_manual_split(
        revisions, families, args.generated_on
    )
    final_family_by_path = {
        revision.source_path: revision.family_id for revision in revisions
    }
    all_dispositions = tuple(
        replace(
            item,
            target_family_id=final_family_by_path.get(
                item.source_path, item.target_family_id
            ),
        )
        for item in tuple(legacy.dispositions) + batch_dispositions
    )
    registry = RegistryV2(
        schema_version=2,
        release_target=legacy.release_target,
        generated_on=args.generated_on,
        revisions=tuple(revisions),
        families=tuple(families),
        dispositions=all_dispositions,
    )
    backup = args.output.with_name("registry-v2.legacy-baseline.json")
    if not backup.exists():
        backup.write_text(
            json.dumps(legacy.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    write_registry_v2(registry, args.output)

    conflicts_payload = json.loads(args.conflicts.read_text(encoding="utf-8"))
    revision_ids = {revision.revision_id for revision in revisions}
    by_path = {revision.source_path: revision.revision_id for revision in revisions}
    by_path.update(
        {
            revision.source_path[len(BATCH_ROOT) :]: revision.revision_id
            for revision in revisions
            if revision.source_path.startswith(BATCH_ROOT)
        }
    )

    def resolve_conflict_target(value: str) -> str:
        if value in by_path:
            return by_path[value]
        if value in revision_ids:
            return value
        if "#" in value:
            candidate = value.rsplit("#", 1)[-1]
            if candidate in revision_ids:
                return candidate
        return ""

    conflicts = []
    for item in conflicts_payload["conflicts"]:
        data = dict(item)
        a_id = resolve_conflict_target(data["revision_a"])
        b_id = resolve_conflict_target(data["revision_b"])
        external = [
            value
            for value, resolved in (
                (data["revision_a"], a_id),
                (data["revision_b"], b_id),
            )
            if not resolved
        ]
        data.update(
            revision_a_id=a_id,
            revision_b_id=b_id,
            external_reference=" | ".join(external),
        )
        conflicts.append(ConflictRecord.from_dict(data))
    ledger = ConflictLedger(
        schema_version=2,
        release_target=legacy.release_target,
        generated_on=args.generated_on,
        conflicts=tuple(conflicts),
    )
    write_conflict_ledger(ledger, args.conflict_output)

    report = {
        "generated_on": args.generated_on,
        "batch_id": BATCH_ID,
        "legacy_revisions": len(legacy.revisions),
        "new_revisions": len(new_revisions),
        "total_revisions": len(revisions),
        "dispositions": len(all_dispositions),
        "families": len(families),
        "family_candidates": len(family_candidates),
        "family_candidates_used": sorted(
            {
                revision.family_id
                for revision in revisions
                if revision.family_id
                in {item["family_id"] for item in family_candidates}
            }
        ),
        "unresolved_family_candidates": unresolved,
        "by_usage_status": dict(
            Counter(revision.usage_status for revision in revisions)
        ),
        "by_approval_status": dict(
            Counter(revision.approval_status for revision in revisions)
        ),
        "by_access_scope": dict(
            Counter(revision.access_scope for revision in revisions)
        ),
        "by_source_format": dict(
            Counter(revision.source_format for revision in revisions)
        ),
        "by_disposition": dict(
            Counter(revision.disposition for revision in revisions)
        ),
        "conflicts": len(ledger.conflicts),
        "output": _display_path(args.output),
        "conflict_output": _display_path(args.conflict_output),
    }
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
