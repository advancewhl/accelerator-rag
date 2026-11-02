"""Knowledge-base Schema v2: revisions, families, dispositions and releases.

Five identities stay distinct (plan §5.1):

``family_id``    logical document family (manual editions, design generations)
``revision_id``  one immutable source revision and the retrieval document ID
``asset_id``     original, converted, OCR or reading-copy asset of a revision
``build_id``     one candidate build under a fixed processing contract
``release_id``   one accepted knowledge-base release users actually query

The v1 ``DocumentRecord`` remains the ingestion adapter for the frozen legacy
pipeline.  Schema v2 records are an additional governance layer and never
silently rewrite the v1 registry.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import MISSING, asdict, dataclass, fields
from datetime import datetime
from enum import Enum
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Iterable

from accelerator_rag.corpus.taxonomy_v2 import (
    TOPICS_BY_CATEGORY as V2_TOPICS_BY_CATEGORY,
    VALID_CATEGORIES as V2_VALID_CATEGORIES,
)


SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SOURCE_ROOT_PARTS = ("data", "l0_raw")
_LEGACY_BATCH_ID = "legacy-baseline"
_LEGACY_RECEIVED_AT = "unknown"


class SourceFormat(str, Enum):
    PDF = "pdf"
    MD = "md"
    DOCX = "docx"
    DOC = "doc"
    PPTX = "pptx"
    XLSX = "xlsx"
    CSV = "csv"
    ODS = "ods"
    TXT = "txt"
    IMAGE = "image"
    ARCHIVE = "archive"
    CODE = "code"
    OTHER = "other"


class DocumentKind(str, Enum):
    OVERALL_DESIGN = "overall_design"
    SUBSYSTEM_DESIGN = "subsystem_design"
    STANDARD_SPECIFICATION = "standard_specification"
    INTERFACE_SPECIFICATION = "interface_specification"
    OPERATION_MANUAL = "operation_manual"
    INSTALLATION_MAINTENANCE = "installation_maintenance"
    TEST_PLAN = "test_plan"
    TEST_REPORT = "test_report"
    ACCEPTANCE_REPORT = "acceptance_report"
    DEVELOPMENT_SUMMARY = "development_summary"
    REVIEW_OPINION = "review_opinion"
    MEETING_RECORD = "meeting_record"
    PAPER = "paper"
    CONFIGURATION_SNAPSHOT = "configuration_snapshot"
    STRUCTURED_LIST = "structured_list"
    DRAWING = "drawing"
    UNKNOWN = "unknown"


class EvidenceRole(str, Enum):
    DESIGN_TARGET = "design_target"
    SPECIFICATION_REQUIREMENT = "specification_requirement"
    TEST_RESULT = "test_result"
    ACCEPTANCE_CONCLUSION = "acceptance_conclusion"
    OPERATING_STEP = "operating_step"
    HISTORICAL_RECORD = "historical_record"
    BACKGROUND_REFERENCE = "background_reference"
    UNKNOWN = "unknown"


class ApprovalStatus(str, Enum):
    APPROVED = "approved"
    DRAFT = "draft"
    UNKNOWN = "unknown"
    WITHDRAWN = "withdrawn"


class UsageStatus(str, Enum):
    CURRENT = "current"
    HISTORICAL = "historical"
    REFERENCE = "reference"
    PENDING_REVIEW = "pending_review"
    EXCLUDED = "excluded"


class BuildStatus(str, Enum):
    RECEIVED = "received"
    PARSED = "parsed"
    REVIEWED = "reviewed"
    INDEXED = "indexed"
    VERIFIED = "verified"
    FAILED = "failed"


class ReleaseStatus(str, Enum):
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    LIVE = "live"
    ROLLED_BACK = "rolled_back"
    RETIRED = "retired"


class DatePrecision(str, Enum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    UNKNOWN = "unknown"


class Disposition(str, Enum):
    TEXT_INDEX = "text_index"
    STRUCTURED_INDEX = "structured_index"
    ATTACHMENT_ONLY = "attachment_only"
    CATALOG_ONLY = "catalog_only"
    DEFERRED = "deferred"
    EXCLUDED = "excluded"


class PlannedAction(str, Enum):
    INGEST = "ingest"
    CONVERT = "convert"
    OCR = "ocr"
    STRUCTURED = "structured"
    ATTACHMENT = "attachment"
    CATALOG = "catalog"
    EXCLUDE = "exclude"
    DEFER = "defer"


class AccessScope(str, Enum):
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class ConflictStatus(str, Enum):
    OPEN = "open"
    NEEDS_SOURCE_CHECK = "needs_source_check"
    RESOLVED = "resolved"


SOURCE_FORMAT_BY_SUFFIX: dict[str, SourceFormat] = {
    ".pdf": SourceFormat.PDF,
    ".md": SourceFormat.MD,
    ".markdown": SourceFormat.MD,
    ".docx": SourceFormat.DOCX,
    ".doc": SourceFormat.DOC,
    ".pptx": SourceFormat.PPTX,
    ".xlsx": SourceFormat.XLSX,
    ".csv": SourceFormat.CSV,
    ".ods": SourceFormat.ODS,
    ".txt": SourceFormat.TXT,
    ".jpg": SourceFormat.IMAGE,
    ".jpeg": SourceFormat.IMAGE,
    ".png": SourceFormat.IMAGE,
    ".tif": SourceFormat.IMAGE,
    ".tiff": SourceFormat.IMAGE,
    ".bmp": SourceFormat.IMAGE,
    ".zip": SourceFormat.ARCHIVE,
    ".rar": SourceFormat.ARCHIVE,
    ".7z": SourceFormat.ARCHIVE,
    ".tar": SourceFormat.ARCHIVE,
    ".gz": SourceFormat.ARCHIVE,
    ".py": SourceFormat.CODE,
    ".sh": SourceFormat.CODE,
    ".log": SourceFormat.CODE,
    ".acf": SourceFormat.CODE,
    ".conf": SourceFormat.CODE,
    ".cfg": SourceFormat.CODE,
    ".json": SourceFormat.CODE,
    ".yaml": SourceFormat.CODE,
    ".yml": SourceFormat.CODE,
    ".xml": SourceFormat.CODE,
    ".sql": SourceFormat.CODE,
}

_LANGUAGES = frozenset({"en", "unknown", "zh", "zh-en"})
_TEXT_INDEX_FORMATS = frozenset(
    {
        SourceFormat.PDF,
        SourceFormat.MD,
        SourceFormat.DOCX,
        SourceFormat.DOC,
        SourceFormat.PPTX,
        SourceFormat.TXT,
    }
)
_STRUCTURED_FORMATS = frozenset(
    {SourceFormat.XLSX, SourceFormat.CSV, SourceFormat.ODS}
)
_DATE_PATTERNS = {
    DatePrecision.DAY: re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    DatePrecision.MONTH: re.compile(r"^\d{4}-\d{2}$"),
    DatePrecision.YEAR: re.compile(r"^\d{4}$"),
}
_DATE_STRPTIME = {
    DatePrecision.DAY: "%Y-%m-%d",
    DatePrecision.MONTH: "%Y-%m",
    DatePrecision.YEAR: "%Y",
}

_TUPLE_FIELDS = frozenset(
    {
        "tags",
        "scope",
        "applicable_versions",
        "supersedes",
        "equivalent_to",
        "contains",
        "supplements",
        "derived_from",
    }
)

_DISPOSITION_ACTIONS = {
    Disposition.TEXT_INDEX: frozenset(
        {PlannedAction.INGEST, PlannedAction.CONVERT, PlannedAction.OCR}
    ),
    Disposition.STRUCTURED_INDEX: frozenset({PlannedAction.STRUCTURED}),
    Disposition.ATTACHMENT_ONLY: frozenset({PlannedAction.ATTACHMENT}),
    Disposition.CATALOG_ONLY: frozenset({PlannedAction.CATALOG}),
    Disposition.DEFERRED: frozenset({PlannedAction.DEFER}),
    Disposition.EXCLUDED: frozenset({PlannedAction.EXCLUDE}),
}


def source_format_for_path(path: str | PurePosixPath) -> SourceFormat:
    """Map a suffix to the format axis; unknown suffixes never guess."""

    return SOURCE_FORMAT_BY_SUFFIX.get(PurePosixPath(path).suffix.lower(), SourceFormat.OTHER)


def _require_text(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 不能为空")
    if value != value.strip():
        raise ValueError(f"{field_name} 不能包含首尾空白")


def _require_slug(value: Any, field_name: str) -> None:
    _require_text(value, field_name)
    if not SLUG_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} 只能使用小写字母、数字和单个连字符分隔的 slug")


def _require_enum(value: Any, enum_type: type[Enum], field_name: str) -> None:
    if value not in {item.value for item in enum_type}:
        raise ValueError(
            f"不支持的 {field_name}: {value}; 允许值: "
            + ", ".join(sorted(item.value for item in enum_type))
        )


def _require_source_path(value: Any) -> None:
    _require_text(value, "source_path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != value
        or "\\" in value
    ):
        raise ValueError("source_path 必须是 data/l0_raw 下的安全相对路径")
    if path.parts[:2] != _SOURCE_ROOT_PARTS:
        raise ValueError("source_path 必须位于 data/l0_raw 下")


def _require_format_matches(path: str, source_format: str) -> None:
    expected = source_format_for_path(path)
    if expected is SourceFormat.OTHER:
        if source_format != SourceFormat.OTHER.value:
            raise ValueError("未知扩展名只能使用 source_format=other")
        return
    if source_format != expected.value:
        raise ValueError(
            f"source_path 扩展名要求 source_format={expected.value}，"
            f"实际为 {source_format}"
        )


def _validate_date(value: str, precision: str, field_name: str) -> None:
    if value in {"", "unknown"}:
        return
    if precision == DatePrecision.UNKNOWN.value:
        candidates = list(_DATE_PATTERNS.values())
        if not any(pattern.fullmatch(value) for pattern in candidates):
            raise ValueError(f"{field_name} 必须是 YYYY、YYYY-MM 或 YYYY-MM-DD")
        return
    _require_enum(precision, DatePrecision, "date_precision")
    pattern = _DATE_PATTERNS[DatePrecision(precision)]
    if not pattern.fullmatch(value):
        raise ValueError(f"{field_name} 不符合 date_precision={precision}")
    try:
        datetime.strptime(value, _DATE_STRPTIME[DatePrecision(precision)])
    except ValueError as exc:
        raise ValueError(f"{field_name} 不是有效日期: {value}") from exc


def _as_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, Mapping)) or not isinstance(value, Iterable):
        raise ValueError(f"{field_name} 必须是字符串数组")
    items = tuple(value)
    for item in items:
        if not isinstance(item, str) or not item.strip() or item != item.strip():
            raise ValueError(f"{field_name} 数组元素必须是非空无首尾空白字符串")
    return items


def _from_dict(cls, data: Any):
    if not isinstance(data, dict):
        raise ValueError(f"{cls.__name__} 必须是 JSON 对象")
    allowed = {field.name for field in fields(cls)}
    extra = set(data) - allowed
    if extra:
        raise ValueError(f"{cls.__name__} 存在未知字段: {', '.join(sorted(extra))}")
    values: dict[str, Any] = {}
    for field in fields(cls):
        if field.name in data:
            value = data[field.name]
            if field.name in _TUPLE_FIELDS:
                value = _as_tuple(value, field.name)
            values[field.name] = value
        elif field.default is MISSING and field.default_factory is MISSING:
            raise ValueError(f"{cls.__name__} 缺少必填字段: {field.name}")
    return cls(**values)


@dataclass(frozen=True)
class RevisionRecord:
    """One immutable source revision with governance and applicability metadata."""

    family_id: str
    revision_id: str
    title: str
    revision_label: str
    batch_id: str
    original_asset_id: str
    source_path: str
    source_format: str
    language: str
    document_kind: str
    category: str
    topic: str
    evidence_role: str
    usage_status: str
    approval_status: str
    disposition: str
    reason: str
    received_at: str
    document_date: str = ""
    effective_from: str = ""
    effective_to: str = ""
    date_precision: str = DatePrecision.UNKNOWN.value
    owner: str = "unknown"
    source_authority: str = "unknown"
    access_scope: str = AccessScope.INTERNAL.value
    parser_profile: str = ""
    conversion_profile: str = ""
    ocr_profile: str = ""
    review_record: str = ""
    reviewed_by: str = ""
    reviewed_at: str = ""
    tags: tuple[str, ...] = ()
    scope: tuple[str, ...] = ()
    applicable_versions: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    equivalent_to: tuple[str, ...] = ()
    contains: tuple[str, ...] = ()
    supplements: tuple[str, ...] = ()
    derived_from: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "family_id",
            "revision_id",
            "batch_id",
            "original_asset_id",
        ):
            _require_slug(getattr(self, name), name)
        for name in (
            "title",
            "revision_label",
            "reason",
            "received_at",
            "owner",
            "source_authority",
        ):
            _require_text(getattr(self, name), name)
        _require_source_path(self.source_path)
        _require_enum(self.source_format, SourceFormat, "source_format")
        _require_format_matches(self.source_path, self.source_format)
        _require_enum(self.document_kind, DocumentKind, "document_kind")
        _require_enum(self.evidence_role, EvidenceRole, "evidence_role")
        _require_enum(self.usage_status, UsageStatus, "usage_status")
        _require_enum(self.approval_status, ApprovalStatus, "approval_status")
        _require_enum(self.disposition, Disposition, "disposition")
        _require_enum(self.date_precision, DatePrecision, "date_precision")
        _require_enum(self.access_scope, AccessScope, "access_scope")
        if self.review_record and not isinstance(self.review_record, str):
            raise ValueError("review_record 必须是字符串")
        for name in ("parser_profile", "conversion_profile", "ocr_profile"):
            value = getattr(self, name)
            if not isinstance(value, str) or value != value.strip():
                raise ValueError(f"{name} 必须是无首尾空白的字符串")
        if self.language not in _LANGUAGES:
            raise ValueError(f"不支持的 language: {self.language}")
        if self.category not in V2_VALID_CATEGORIES:
            raise ValueError(f"不支持的 category: {self.category}")
        if self.topic not in V2_TOPICS_BY_CATEGORY[self.category]:
            raise ValueError(
                f"category={self.category} 不支持 topic: {self.topic}"
            )
        for name in (
            "document_date",
            "effective_from",
            "effective_to",
        ):
            _validate_date(getattr(self, name), self.date_precision, name)
        if self.reviewed_at:
            _validate_date(self.reviewed_at, DatePrecision.DAY.value, "reviewed_at")
        if (
            self.effective_from
            and self.effective_to
            and self.effective_from != "unknown"
            and self.effective_to != "unknown"
            and self.effective_to < self.effective_from
        ):
            raise ValueError("effective_to 不能早于 effective_from")
        if self.usage_status == UsageStatus.CURRENT.value and not (
            self.scope or self.applicable_versions
        ):
            raise ValueError("usage_status=current 必须说明 scope 或 applicable_versions")
        if self.usage_status == UsageStatus.CURRENT.value and self.approval_status in {
            ApprovalStatus.WITHDRAWN.value,
            ApprovalStatus.DRAFT.value,
        }:
            raise ValueError(
                "withdrawn/draft 资料不能标记为 usage_status=current"
            )
        if (
            self.usage_status == UsageStatus.CURRENT.value
            and self.approval_status == ApprovalStatus.APPROVED.value
        ):
            if not self.reviewed_by or not self.reviewed_at:
                raise ValueError("已批准且现行修订必须记录 reviewed_by 和 reviewed_at")
        if self.usage_status == UsageStatus.EXCLUDED.value:
            if self.disposition != Disposition.EXCLUDED.value:
                raise ValueError("usage_status=excluded 要求 disposition=excluded")
        elif self.disposition == Disposition.EXCLUDED.value:
            raise ValueError("disposition=excluded 要求 usage_status=excluded")
        if self.disposition == Disposition.TEXT_INDEX.value:
            if SourceFormat(self.source_format) not in _TEXT_INDEX_FORMATS:
                raise ValueError("text_index 只适用于可解析文本格式")
        if self.disposition == Disposition.STRUCTURED_INDEX.value:
            if SourceFormat(self.source_format) not in _STRUCTURED_FORMATS:
                raise ValueError("structured_index 只适用于表格格式")
        for relation in (
            "supersedes",
            "equivalent_to",
            "contains",
            "supplements",
            "derived_from",
        ):
            values = getattr(self, relation)
            if self.revision_id in values:
                raise ValueError(f"{relation} 不能引用自身")
            for value in values:
                _require_slug(value, relation)

    @property
    def ingestible(self) -> bool:
        return self.source_format in {SourceFormat.PDF.value, SourceFormat.MD.value}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> "RevisionRecord":
        return _from_dict(cls, data)


@dataclass(frozen=True)
class DocumentFamily:
    """A logical document and its confirmed revisions; membership is explicit."""

    family_id: str
    title: str
    description: str
    revision_ids: tuple[str, ...]
    notes: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        _require_slug(self.family_id, "family_id")
        _require_text(self.title, "title")
        _require_text(self.description, "description")
        if not self.revision_ids:
            raise ValueError("family 必须至少包含一个 revision_id")
        if len(set(self.revision_ids)) != len(self.revision_ids):
            raise ValueError("family revision_ids 不能重复")
        for revision_id in self.revision_ids:
            _require_slug(revision_id, "revision_ids")
        if self.created_at:
            _validate_date(self.created_at, DatePrecision.DAY.value, "created_at")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> "DocumentFamily":
        return _from_dict(cls, data)


@dataclass(frozen=True)
class DispositionRecord:
    """Disposition for every input file, including files that never enter an index."""

    batch_id: str
    batch_relative_path: str
    source_path: str
    source_format: str
    document_kind: str
    priority: str
    disposition: str
    planned_action: str
    reason: str
    target_family_id: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        _require_slug(self.batch_id, "batch_id")
        _require_text(self.batch_relative_path, "batch_relative_path")
        _require_source_path(self.source_path)
        _require_enum(self.source_format, SourceFormat, "source_format")
        _require_format_matches(self.source_path, self.source_format)
        _require_enum(self.document_kind, DocumentKind, "document_kind")
        if self.priority not in {"P0", "P1", "P2", "P3", "exclude"}:
            raise ValueError("priority 必须是 P0/P1/P2/P3/exclude")
        _require_enum(self.disposition, Disposition, "disposition")
        _require_enum(self.planned_action, PlannedAction, "planned_action")
        _require_text(self.reason, "reason")
        if self.target_family_id:
            _require_slug(self.target_family_id, "target_family_id")
        allowed = _DISPOSITION_ACTIONS[Disposition(self.disposition)]
        if PlannedAction(self.planned_action) not in allowed:
            raise ValueError(
                f"disposition={self.disposition} 与 planned_action="
                f"{self.planned_action} 不一致"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> "DispositionRecord":
        return _from_dict(cls, data)


@dataclass(frozen=True)
class RegistryV2:
    """Schema v2 registry: revisions, families and per-file dispositions."""

    schema_version: int
    release_target: str
    generated_on: str
    revisions: tuple[RevisionRecord, ...]
    families: tuple[DocumentFamily, ...]
    dispositions: tuple[DispositionRecord, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 2:
            raise ValueError("schema_version 必须为 2")
        _require_text(self.release_target, "release_target")
        _validate_date(self.generated_on, DatePrecision.DAY.value, "generated_on")
        if not self.revisions:
            raise ValueError("registry 必须至少包含一个 revision")
        if not self.families:
            raise ValueError("registry 必须至少包含一个 family")
        revision_ids = [revision.revision_id for revision in self.revisions]
        source_paths = [revision.source_path for revision in self.revisions]
        if len(set(revision_ids)) != len(revision_ids):
            raise ValueError("registry 存在重复 revision_id")
        if len(set(source_paths)) != len(source_paths):
            raise ValueError("registry 存在重复 source_path")
        family_ids = [family.family_id for family in self.families]
        if len(set(family_ids)) != len(family_ids):
            raise ValueError("registry 存在重复 family_id")
        revisions_by_id = {revision.revision_id: revision for revision in self.revisions}
        for revision in self.revisions:
            if revision.family_id not in set(family_ids):
                raise ValueError(
                    f"revision {revision.revision_id} 引用了不存在的 family "
                    f"{revision.family_id}"
                )
        for family in self.families:
            for revision_id in family.revision_ids:
                revision = revisions_by_id.get(revision_id)
                if revision is None:
                    raise ValueError(
                        f"family {family.family_id} 引用了不存在的 revision "
                        f"{revision_id}"
                    )
                if revision.family_id != family.family_id:
                    raise ValueError(
                        f"revision {revision_id} 的 family_id 与所属 family 不一致"
                    )
            expected = {
                revision.revision_id
                for revision in self.revisions
                if revision.family_id == family.family_id
            }
            if set(family.revision_ids) != expected:
                raise ValueError(
                    f"family {family.family_id} 的 revision_ids 与 registry 不一致"
                )
        disposition_keys = [
            (item.batch_id, item.source_path) for item in self.dispositions
        ]
        if len(set(disposition_keys)) != len(disposition_keys):
            raise ValueError("registry 存在重复 disposition (batch_id, source_path)")
        dispositions_by_path = {
            (item.batch_id, item.source_path): item for item in self.dispositions
        }
        for revision in self.revisions:
            item = dispositions_by_path.get((revision.batch_id, revision.source_path))
            if item is None:
                raise ValueError(
                    f"revision {revision.revision_id} 缺少对应 disposition"
                )
            if item.disposition != revision.disposition:
                raise ValueError(
                    f"revision {revision.revision_id} 与 disposition 的处置不一致"
                )
            if (
                item.target_family_id
                and item.target_family_id != revision.family_id
            ):
                raise ValueError(
                    f"revision {revision.revision_id} 与 disposition 的 "
                    "target_family_id 不一致"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "release_target": self.release_target,
            "generated_on": self.generated_on,
            "revisions": [revision.to_dict() for revision in self.revisions],
            "families": [family.to_dict() for family in self.families],
            "dispositions": [item.to_dict() for item in self.dispositions],
        }

    def summary(self) -> dict[str, Any]:
        def count(values: Iterable[str]) -> dict[str, int]:
            counts: dict[str, int] = {}
            for value in values:
                counts[value] = counts.get(value, 0) + 1
            return dict(sorted(counts.items()))

        return {
            "schema_version": self.schema_version,
            "release_target": self.release_target,
            "revision_count": len(self.revisions),
            "family_count": len(self.families),
            "disposition_count": len(self.dispositions),
            "by_usage_status": count(r.usage_status for r in self.revisions),
            "by_approval_status": count(r.approval_status for r in self.revisions),
            "by_source_format": count(r.source_format for r in self.revisions),
            "by_document_kind": count(r.document_kind for r in self.revisions),
            "by_disposition": count(d.disposition for d in self.dispositions),
            "batches": sorted({r.batch_id for r in self.revisions}),
        }

    def revision(self, revision_id: str) -> RevisionRecord:
        for revision in self.revisions:
            if revision.revision_id == revision_id:
                return revision
        raise KeyError(revision_id)

    def family(self, family_id: str) -> DocumentFamily:
        for family in self.families:
            if family.family_id == family_id:
                return family
        raise KeyError(family_id)

    def validate_batch_coverage(
        self, batch_id: str, expected_source_paths: Iterable[str]
    ) -> None:
        expected = set(expected_source_paths)
        actual = {
            item.source_path
            for item in self.dispositions
            if item.batch_id == batch_id
        }
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        if missing or unexpected:
            raise ValueError(
                f"批次 {batch_id} 处置不完整; 缺少: {missing[:10]}; "
                f"多出: {unexpected[:10]}"
            )

    @classmethod
    def from_dict(cls, data: Any) -> "RegistryV2":
        if not isinstance(data, dict):
            raise ValueError("registry v2 根节点必须是 JSON 对象")
        allowed = {
            "schema_version",
            "release_target",
            "generated_on",
            "revisions",
            "families",
            "dispositions",
        }
        extra = set(data) - allowed
        if extra:
            raise ValueError(f"registry v2 存在未知字段: {', '.join(sorted(extra))}")
        for key in ("revisions", "families", "dispositions"):
            if not isinstance(data.get(key), list):
                raise ValueError(f"registry v2 的 {key} 必须是 JSON 数组")
        return cls(
            schema_version=data["schema_version"],
            release_target=data["release_target"],
            generated_on=data["generated_on"],
            revisions=tuple(
                RevisionRecord.from_dict(item) for item in data["revisions"]
            ),
            families=tuple(
                DocumentFamily.from_dict(item) for item in data["families"]
            ),
            dispositions=tuple(
                DispositionRecord.from_dict(item) for item in data["dispositions"]
            ),
        )


@dataclass(frozen=True)
class ConflictRecord:
    """One unresolved or resolved conflict between two revisions/claims."""

    topic: str
    revision_a: str
    revision_b: str
    evidence_location: str
    conflict_type: str
    applicable_condition: str
    owner: str
    status: str
    resolution: str = ""
    revision_a_id: str = ""
    revision_b_id: str = ""
    external_reference: str = ""

    def __post_init__(self) -> None:
        for name in (
            "topic",
            "revision_a",
            "revision_b",
            "evidence_location",
            "conflict_type",
            "applicable_condition",
            "owner",
        ):
            _require_text(getattr(self, name), name)
        for name in ("revision_a_id", "revision_b_id"):
            value = getattr(self, name)
            if value:
                _require_slug(value, name)
        if not isinstance(self.external_reference, str) or (
            self.external_reference != self.external_reference.strip()
        ):
            raise ValueError("external_reference 必须是无首尾空白的字符串")
        _require_enum(self.status, ConflictStatus, "status")
        if not isinstance(self.resolution, str) or (
            self.resolution != self.resolution.strip()
        ):
            raise ValueError("resolution 必须是无首尾空白的字符串")
        if self.status == ConflictStatus.RESOLVED.value and not self.resolution:
            raise ValueError("resolved 冲突必须填写 resolution")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> "ConflictRecord":
        return _from_dict(cls, data)


@dataclass(frozen=True)
class ConflictLedger:
    """Conflict register kept separate from the revision registry."""

    schema_version: int
    release_target: str
    generated_on: str
    conflicts: tuple[ConflictRecord, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 2:
            raise ValueError("schema_version 必须为 2")
        _require_text(self.release_target, "release_target")
        _validate_date(self.generated_on, DatePrecision.DAY.value, "generated_on")
        keys = [(item.topic, item.revision_a, item.revision_b) for item in self.conflicts]
        if len(set(keys)) != len(keys):
            raise ValueError("冲突台账存在重复 (topic, revision_a, revision_b)")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "release_target": self.release_target,
            "generated_on": self.generated_on,
            "conflicts": [item.to_dict() for item in self.conflicts],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ConflictLedger":
        if not isinstance(data, dict):
            raise ValueError("conflict ledger 根节点必须是 JSON 对象")
        allowed = {"schema_version", "release_target", "generated_on", "conflicts"}
        extra = set(data) - allowed
        if extra:
            raise ValueError(
                f"conflict ledger 存在未知字段: {', '.join(sorted(extra))}"
            )
        if not isinstance(data.get("conflicts"), list):
            raise ValueError("conflicts 必须是 JSON 数组")
        return cls(
            schema_version=data["schema_version"],
            release_target=data["release_target"],
            generated_on=data["generated_on"],
            conflicts=tuple(
                ConflictRecord.from_dict(item) for item in data["conflicts"]
            ),
        )


def load_conflict_ledger(path: str | Path) -> ConflictLedger:
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"conflict ledger 不是合法 JSON: line {exc.lineno}, column {exc.colno}"
        ) from exc
    return ConflictLedger.from_dict(data)


def write_conflict_ledger(ledger: ConflictLedger, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(ledger.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_registry_v2(path: str | Path) -> RegistryV2:
    """Load and validate one Schema v2 registry at the manifest boundary."""

    registry_path = Path(path)
    try:
        with registry_path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"registry v2 不是合法 JSON: line {exc.lineno}, column {exc.colno}"
        ) from exc
    return RegistryV2.from_dict(data)


def write_registry_v2(registry: RegistryV2, path: str | Path) -> None:
    """Write deterministic, reviewable metadata; never called by the runtime."""

    if not isinstance(registry, RegistryV2):
        raise TypeError("write_registry_v2 requires RegistryV2")
    Path(path).write_text(
        json.dumps(registry.to_dict(), ensure_ascii=False, indent=2, sort_keys=False)
        + "\n",
        encoding="utf-8",
    )


def to_document_record(revision: RevisionRecord):
    """Adapter for the frozen v1 ingestion path (PDF/Markdown only)."""

    from accelerator_rag.corpus.registry import DocumentRecord

    if not revision.ingestible:
        raise ValueError(
            "v1 ingestion adapter only accepts pdf/md revisions; "
            f"got {revision.source_format}"
        )
    if revision.usage_status == UsageStatus.EXCLUDED.value:
        raise ValueError(
            f"revision {revision.revision_id} is excluded and must not be ingested"
        )
    status_by_usage = {
        UsageStatus.CURRENT.value: "active",
        UsageStatus.HISTORICAL.value: "deprecated",
        UsageStatus.REFERENCE.value: "reference",
        UsageStatus.PENDING_REVIEW.value: "draft",
        UsageStatus.EXCLUDED.value: "unknown",
    }
    return DocumentRecord(
        doc_id=revision.revision_id,
        title=revision.title,
        source_path=revision.source_path,
        category=revision.category,
        topic=revision.topic,
        document_type=revision.source_format,
        language=revision.language,
        version=revision.revision_label,
        status=status_by_usage[revision.usage_status],
    )


_LEGACY_KIND_BY_ID: dict[str, DocumentKind] = {
    "epics-application-developers-guide-r3-16-2": DocumentKind.STANDARD_SPECIFICATION,
    "epics-documentation-latest-2026-08-18": DocumentKind.STANDARD_SPECIFICATION,
    "european-xfel-full-technical-design-report-2007": DocumentKind.OVERALL_DESIGN,
    "european-xfel-undulator-commissioning-spectrometer-cdr-2011": (
        DocumentKind.SUBSYSTEM_DESIGN
    ),
    "european-xfel-x-ray-optics-beam-transport-tdr-2012": (
        DocumentKind.SUBSYSTEM_DESIGN
    ),
    "european-xfel-standard-e-beam-diagnostics-linac2010": DocumentKind.PAPER,
    "shine-epics-ioc-pv-information-management-pcapac2022": DocumentKind.PAPER,
    "shine-accelerator-fast-interlock-2024": DocumentKind.PAPER,
    "shine-control-system-status-icalepcs2019": DocumentKind.PAPER,
    "shine-cryogenic-control-system-2021": DocumentKind.PAPER,
    "shine-white-rabbit-beam-synchronous-timing-ipac2022": DocumentKind.PAPER,
    "shine-accelerator-control-system-design-presentation": DocumentKind.PAPER,
    "shine-accelerator-preliminary-design-report-2017": DocumentKind.OVERALL_DESIGN,
    "waveform-storage-dataflow": DocumentKind.OPERATION_MANUAL,
    "waveform-alignment-semantics": DocumentKind.OPERATION_MANUAL,
    "waveform-fault-history": DocumentKind.OPERATION_MANUAL,
    "rag-ingestion-verification-rollback": DocumentKind.OPERATION_MANUAL,
}

_LEGACY_SCOPE_BY_ID: dict[str, tuple[str, ...]] = {
    "waveform-storage-dataflow": ("waveform-storage-system@dc50e08",),
    "waveform-alignment-semantics": ("waveform-storage-system@dc50e08",),
    "waveform-fault-history": ("waveform-storage-system@dc50e08",),
    "rag-ingestion-verification-rollback": ("accelerator-rag-prab@0b62844",),
}

_LEGACY_CURRENT_IDS = frozenset(
    {
        "waveform-storage-dataflow",
        "waveform-alignment-semantics",
        "waveform-fault-history",
        "rag-ingestion-verification-rollback",
    }
)

_VERSION_DATE_PATTERN = re.compile(
    r"\((?P<date>\d{4}(?:-\d{2}){0,2})\)"
)


def _date_from_version(version: str) -> tuple[str, str]:
    match = _VERSION_DATE_PATTERN.search(version)
    if match is None:
        return "", DatePrecision.UNKNOWN.value
    value = match.group("date")
    parts = value.split("-")
    precision = {
        1: DatePrecision.YEAR.value,
        2: DatePrecision.MONTH.value,
        3: DatePrecision.DAY.value,
    }[len(parts)]
    return value, precision


def from_legacy_records(
    records: Iterable,
    *,
    generated_on: str,
    release_target: str = "kb-2.0.0",
    batch_id: str = _LEGACY_BATCH_ID,
) -> RegistryV2:
    """Build a conservative Schema v2 registry from the frozen v1 records.

    Legacy ``active`` is preserved only as a source label.  Only documents with
    an explicit version/verification scope become ``current``; every other
    legacy record becomes ``reference`` with ``approval_status=unknown``, so a
    default query cannot present an unreviewed document as the current basis.
    """

    revisions: list[RevisionRecord] = []
    families: list[DocumentFamily] = []
    dispositions: list[DispositionRecord] = []
    for record in records:
        family_id = record.doc_id
        revision_id = record.doc_id
        kind = _LEGACY_KIND_BY_ID.get(record.doc_id, DocumentKind.UNKNOWN)
        role = {
            DocumentKind.OVERALL_DESIGN: EvidenceRole.DESIGN_TARGET,
            DocumentKind.SUBSYSTEM_DESIGN: EvidenceRole.DESIGN_TARGET,
            DocumentKind.STANDARD_SPECIFICATION: (
                EvidenceRole.SPECIFICATION_REQUIREMENT
            ),
            DocumentKind.OPERATION_MANUAL: EvidenceRole.OPERATING_STEP,
            DocumentKind.PAPER: EvidenceRole.BACKGROUND_REFERENCE,
        }.get(kind, EvidenceRole.UNKNOWN)
        scope = _LEGACY_SCOPE_BY_ID.get(record.doc_id, ())
        usage = (
            UsageStatus.CURRENT.value
            if record.doc_id in _LEGACY_CURRENT_IDS
            else UsageStatus.REFERENCE.value
        )
        document_date, precision = _date_from_version(record.version)
        if record.document_type == "md":
            # A Markdown version label names a system build, not a document date.
            document_date, precision = "", DatePrecision.UNKNOWN.value
        reason = (
            "Legacy baseline migration: v1 status "
            f"'{record.status}' retained as a source label; applicability was "
            "not independently re-verified."
        )
        revisions.append(
            RevisionRecord(
                family_id=family_id,
                revision_id=revision_id,
                title=record.title,
                revision_label=record.version,
                batch_id=batch_id,
                original_asset_id=f"asset-{record.doc_id}-original",
                source_path=record.source_path,
                source_format=record.document_type,
                language=record.language,
                document_kind=kind.value,
                category=record.category,
                topic=record.topic,
                evidence_role=role.value,
                usage_status=usage,
                approval_status=ApprovalStatus.UNKNOWN.value,
                disposition=Disposition.TEXT_INDEX.value,
                reason=reason,
                received_at=_LEGACY_RECEIVED_AT,
                document_date=document_date,
                date_precision=precision,
                owner="unknown",
                source_authority="legacy-registry-v1",
                access_scope=AccessScope.INTERNAL.value,
                parser_profile="pending-kb2-build",
                review_record=(
                    f"migrated from v1 status={record.status}; no re-review"
                ),
                scope=scope,
                applicable_versions=scope,
            )
        )
        families.append(
            DocumentFamily(
                family_id=family_id,
                title=record.title,
                description=(
                    "Single-revision legacy family; version relationships are "
                    "not confirmed yet."
                ),
                revision_ids=(revision_id,),
                notes="Created by from_legacy_records; merge only with evidence.",
                created_at=generated_on,
            )
        )
        dispositions.append(
            DispositionRecord(
                batch_id=batch_id,
                batch_relative_path=record.source_path,
                source_path=record.source_path,
                source_format=record.document_type,
                document_kind=kind.value,
                priority="P3",
                disposition=Disposition.TEXT_INDEX.value,
                planned_action=PlannedAction.INGEST.value,
                reason=reason,
                target_family_id=family_id,
                notes="legacy baseline; keep existing document_id/revision_id",
            )
        )
    return RegistryV2(
        schema_version=2,
        release_target=release_target,
        generated_on=generated_on,
        revisions=tuple(revisions),
        families=tuple(families),
        dispositions=tuple(dispositions),
    )
