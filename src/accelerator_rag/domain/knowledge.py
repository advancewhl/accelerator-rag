from dataclasses import dataclass, fields
from pathlib import PurePosixPath


@dataclass(frozen=True)
class KnowledgeChunk:
    """Retrievable evidence with portable source identity and physical PDF pages."""

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

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
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


@dataclass(frozen=True)
class RetrievalResult:
    """Rank within one retriever; BM25 and cosine scores are not comparable."""

    rank: int
    score: float
    chunk: KnowledgeChunk
    retriever: str
