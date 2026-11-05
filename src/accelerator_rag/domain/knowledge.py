from dataclasses import asdict, dataclass, fields
from pathlib import PurePosixPath

from accelerator_rag.domain.position import PositionKind


_OPTIONAL_TEXT_FIELDS = frozenset(
    {
        "family_id",
        "revision_label",
        "asset_id",
        "document_kind",
        "evidence_role",
        "usage_status",
        "approval_status",
        "scope",
        "position_kind",
        "position_label",
        "access_scope",
        # Block-level evidence character.  These are additive and default to
        # empty so historical payloads decode unchanged.
        "source_block_ids",
        "content_role",
        "extraction_method",
        "review_status",
        "formula_status",
        "section_path",
        "section_id",
        "position_locator",
        "media_block_ids",
        "tags",
    }
)

_OPTIONAL_INT_FIELDS = frozenset({"document_ordinal"})


@dataclass(frozen=True)
class KnowledgeChunk:
    """Retrievable evidence with portable identity and an explicit position kind.

    The first eleven fields are the frozen v1 contract.  Schema v2 metadata is
    additive and defaults to empty, so existing Qdrant payloads and historical
    baselines decode unchanged.  ``page_start``/``page_end`` keep their legacy
    names but must be read through ``effective_position_kind``: a Markdown
    section index or a PPTX slide number is not a PDF page.
    """

    chunk_id: str
    document_id: str
    document_title: str
    text: str
    source_path: str
    document_version: str
    language: str
    category: str
    topic: str
    page_start: int
    page_end: int
    family_id: str = ""
    revision_label: str = ""
    asset_id: str = ""
    document_kind: str = ""
    evidence_role: str = ""
    usage_status: str = ""
    approval_status: str = ""
    scope: str = ""
    position_kind: str = ""
    position_label: str = ""
    access_scope: str = ""
    source_block_ids: str = ""
    content_role: str = ""
    extraction_method: str = ""
    review_status: str = ""
    formula_status: str = ""
    section_path: str = ""
    section_id: str = ""
    position_locator: str = ""
    media_block_ids: str = ""
    tags: str = ""
    document_ordinal: int = 0

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name in _OPTIONAL_TEXT_FIELDS:
                if not isinstance(value, str):
                    raise ValueError(f"{field.name} must be a string")
                if value != value.strip():
                    raise ValueError(f"{field.name} must not have outer whitespace")
                continue
            if field.name in _OPTIONAL_INT_FIELDS:
                if type(value) is not int or value < 0:
                    raise ValueError(f"{field.name} must be a nonnegative integer")
                continue
            if field.name not in {"page_start", "page_end"}:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{field.name} must be a nonempty string")
        if (
            type(self.page_start) is not int
            or type(self.page_end) is not int
            or not 1 <= self.page_start <= self.page_end
        ):
            raise ValueError("physical page range must satisfy 1 <= start <= end")
        path = PurePosixPath(self.source_path)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in self.source_path
            or path.as_posix() != self.source_path
            or path.parts[:2] != ("data", "l0_raw")
        ):
            raise ValueError("source_path must be a portable path under data/l0_raw")
        if self.position_kind and self.position_kind not in {
            item.value for item in PositionKind
        }:
            raise ValueError(f"unsupported position_kind: {self.position_kind}")

    @property
    def effective_position_kind(self) -> str:
        """New metadata wins; historical chunks fall back to their source format."""

        if self.position_kind:
            return self.position_kind
        suffix = PurePosixPath(self.source_path).suffix.lower()
        if suffix in {".md", ".markdown"}:
            return PositionKind.SECTION.value
        return PositionKind.PDF_PAGE.value

    @property
    def effective_family_id(self) -> str:
        return self.family_id or self.document_id

    @property
    def effective_usage_status(self) -> str:
        return self.usage_status or "unknown"

    @property
    def tag_list(self) -> tuple[str, ...]:
        return tuple(tag for tag in self.tags.split(";") if tag)

    @property
    def source_block_id_list(self) -> tuple[str, ...]:
        """Parsed-block identities that contributed to this evidence chunk."""

        return tuple(
            block_id
            for block_id in self.source_block_ids.split(",")
            if block_id
        )

    def legacy_dict(self) -> dict:
        """The frozen 11-field v1 shape used by historical baseline hashes.

        Schema v2 metadata is additive; historical reports must still reproduce
        byte-for-byte parent hashes, so they must not hash the new empty fields.
        """

        values = asdict(self)
        for name in _OPTIONAL_TEXT_FIELDS | _OPTIONAL_INT_FIELDS:
            values.pop(name, None)
        return values


@dataclass(frozen=True)
class RetrievalResult:
    """Rank within one retriever; BM25 and cosine scores are not comparable."""

    rank: int
    score: float
    chunk: KnowledgeChunk
    retriever: str
