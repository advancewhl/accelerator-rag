from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from accelerator_rag.corpus.taxonomy import TOPICS_BY_CATEGORY, VALID_CATEGORIES


VALID_DOCUMENT_TYPES = frozenset({"docx", "md", "pdf", "pptx", "txt"})
VALID_LANGUAGES = frozenset({"en", "unknown", "zh", "zh-en"})
VALID_STATUSES = frozenset(
    {"active", "deprecated", "draft", "reference", "unknown"}
)
_DOC_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_RAW_ROOT_PARTS = ("data", "raw")


@dataclass(frozen=True)
class DocumentRecord:
    """Metadata used to manage one source document before ingestion."""

    doc_id: str
    title: str
    source_path: str
    category: str
    topic: str
    document_type: str
    language: str
    version: str
    status: str

    def __post_init__(self) -> None:
        required_text_fields = {
            "doc_id": self.doc_id,
            "title": self.title,
            "source_path": self.source_path,
            "category": self.category,
            "topic": self.topic,
            "document_type": self.document_type,
            "language": self.language,
            "version": self.version,
            "status": self.status,
        }

        for field_name, value in required_text_fields.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} 不能为空")
            if value != value.strip():
                raise ValueError(f"{field_name} 不能包含首尾空白")

        if not _DOC_ID_PATTERN.fullmatch(self.doc_id):
            raise ValueError(
                "doc_id 只能使用小写字母、数字和单个连字符分隔的 slug"
            )

        if self.document_type not in VALID_DOCUMENT_TYPES:
            raise ValueError(f"不支持的 document_type: {self.document_type}")
        if self.language not in VALID_LANGUAGES:
            raise ValueError(f"不支持的 language: {self.language}")
        if self.status not in VALID_STATUSES:
            raise ValueError(f"不支持的 status: {self.status}")
        if self.category not in VALID_CATEGORIES:
            raise ValueError(f"不支持的 category: {self.category}")

        valid_topics = TOPICS_BY_CATEGORY[self.category]
        if self.topic not in valid_topics:
            raise ValueError(
                f"category={self.category} 不支持 topic: {self.topic}"
            )

        source_path = PurePosixPath(self.source_path)
        if source_path.is_absolute() or ".." in source_path.parts:
            raise ValueError("source_path 必须是 data/raw 下的安全相对路径")
        if source_path.parts[:2] != _RAW_ROOT_PARTS:
            raise ValueError("source_path 必须位于 data/raw 下")
        if source_path.suffix.lower() != f".{self.document_type}":
            raise ValueError("source_path 扩展名必须与 document_type 一致")


@dataclass(frozen=True)
class CorpusInventory:
    """Registry-to-filesystem reconciliation and corpus statistics."""

    registered_count: int
    raw_file_count: int
    registered_size_bytes: int
    missing_files: tuple[str, ...]
    unregistered_files: tuple[str, ...]
    by_category: dict[str, int]
    by_topic: dict[str, int]
    by_document_type: dict[str, int]
    by_language: dict[str, int]
    by_status: dict[str, int]

    @property
    def is_consistent(self) -> bool:
        return not self.missing_files and not self.unregistered_files


def load_registry(path: str | Path) -> list[DocumentRecord]:
    """Load a registry JSON file and validate every record."""

    registry_path = Path(path)
    try:
        with registry_path.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"registry 文件不是合法 JSON: line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(raw_data, list):
        raise ValueError("registry 根节点必须是 JSON 数组")

    records: list[DocumentRecord] = []
    seen_doc_ids: set[str] = set()
    seen_source_paths: set[str] = set()

    for index, item in enumerate(raw_data):
        if not isinstance(item, dict):
            raise ValueError(f"registry 第 {index} 条记录必须是 JSON 对象")

        try:
            record = DocumentRecord(**item)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"registry 第 {index} 条记录无效: {exc}") from exc

        if record.doc_id in seen_doc_ids:
            raise ValueError(f"registry 存在重复 doc_id: {record.doc_id}")
        if record.source_path in seen_source_paths:
            raise ValueError(f"registry 存在重复 source_path: {record.source_path}")

        seen_doc_ids.add(record.doc_id)
        seen_source_paths.add(record.source_path)
        records.append(record)

    return records


def discover_raw_files(project_root: str | Path) -> tuple[str, ...]:
    """Return all non-placeholder files currently present under data/raw."""

    root = Path(project_root).resolve()
    raw_root = root.joinpath(*_RAW_ROOT_PARTS)
    if not raw_root.is_dir():
        raise ValueError(f"raw 目录不存在: {raw_root}")

    return tuple(
        sorted(
            path.relative_to(root).as_posix()
            for path in raw_root.rglob("*")
            if path.is_file() and path.name != ".gitkeep"
        )
    )


def build_inventory(
    records: list[DocumentRecord],
    project_root: str | Path,
) -> CorpusInventory:
    """Reconcile registry records with data/raw and calculate statistics."""

    root = Path(project_root).resolve()
    registered_paths = {record.source_path for record in records}
    raw_paths = set(discover_raw_files(root))
    existing_registered_paths = registered_paths & raw_paths

    return CorpusInventory(
        registered_count=len(records),
        raw_file_count=len(raw_paths),
        registered_size_bytes=sum(
            (root / source_path).stat().st_size
            for source_path in existing_registered_paths
        ),
        missing_files=tuple(sorted(registered_paths - raw_paths)),
        unregistered_files=tuple(sorted(raw_paths - registered_paths)),
        by_category=_count(records, "category"),
        by_topic=_count(records, "topic"),
        by_document_type=_count(records, "document_type"),
        by_language=_count(records, "language"),
        by_status=_count(records, "status"),
    )


def validate_inventory(inventory: CorpusInventory) -> None:
    """Raise a concise error when registry and data/raw disagree."""

    problems: list[str] = []
    if inventory.missing_files:
        problems.append("登记但缺失: " + ", ".join(inventory.missing_files))
    if inventory.unregistered_files:
        problems.append("存在但未登记: " + ", ".join(inventory.unregistered_files))

    if problems:
        raise ValueError("; ".join(problems))


def _count(records: list[DocumentRecord], field_name: str) -> dict[str, int]:
    counts = Counter(getattr(record, field_name) for record in records)
    return dict(sorted(counts.items()))
