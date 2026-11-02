from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re

from accelerator_rag.corpus.cleaning import clean_page_texts
from accelerator_rag.corpus.markdown_parser import clean_markdown_texts
from accelerator_rag.corpus.pdf_parser import ParsedPdfDocument
from accelerator_rag.corpus.registry import DocumentRecord
from accelerator_rag.domain.knowledge import KnowledgeChunk


CHUNKING_ALGORITHM = "pdf-chunks-v3"
MARKDOWN_CHUNKING_ALGORITHM = "md-chunks-v1"


@dataclass(frozen=True)
class ChunkingConfig:
    """No overlap or page crossing. min_chars is a soft lower bound per page."""

    max_chars: int = 1200
    min_chars: int = 300

    def __post_init__(self) -> None:
        if (
            type(self.max_chars) is not int
            or type(self.min_chars) is not int
            or not 0 < self.min_chars <= self.max_chars // 2
        ):
            raise ValueError("chunk sizes must satisfy 0 < min_chars <= max_chars / 2")


def _split_page(text: str, config: ChunkingConfig) -> list[str]:
    pieces = []
    while len(text) > config.max_chars:
        limit = config.max_chars
        if len(text) - limit < config.min_chars:
            limit = len(text) - config.min_chars
        # Prefer block boundaries, then sentences, then whitespace. Hard-split
        # only an oversized unbroken token. Every cut respects the hard maximum.
        cut = limit
        for pattern in (r"\n\n", r"[.!?。！？]\s*", r"\s+"):
            boundaries = [
                m.end()
                for m in re.finditer(pattern, text[:limit])
                if m.end() >= config.min_chars
            ]
            if boundaries:
                cut = boundaries[-1]
                break
        pieces.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        pieces.append(text)
    return pieces


def _build_chunks(
    pages: list[tuple[int, str]],
    record: DocumentRecord,
    config: ChunkingConfig,
    algorithm: str,
    revision=None,
) -> list[KnowledgeChunk]:
    """Turn (page_number, text) pairs into canonical parent chunks.

    IDs hash algorithm, configuration, document/version, page, ordinal and text.
    The PDF path passes `CHUNKING_ALGORITHM` so its existing IDs stay identical.
    Schema v2 metadata is additive and never enters the frozen chunk identity.
    """
    position_kind = (
        "section" if algorithm == MARKDOWN_CHUNKING_ALGORITHM else "pdf_page"
    )
    chunks = []
    for page_number, text in pages:
        for ordinal, piece in enumerate(_split_page(text, config)):
            identity = json.dumps(
                [
                    algorithm,
                    asdict(config),
                    record.doc_id,
                    record.version,
                    page_number,
                    ordinal,
                    piece,
                ],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if revision is None:
                extra = {
                    "family_id": record.doc_id,
                    "revision_label": record.version,
                    "position_kind": position_kind,
                    "position_label": f"{position_kind}-{page_number}",
                }
            else:
                extra = {
                    "family_id": revision.family_id,
                    "revision_label": revision.revision_label,
                    "asset_id": revision.original_asset_id,
                    "document_kind": revision.document_kind,
                    "evidence_role": revision.evidence_role,
                    "usage_status": revision.usage_status,
                    "approval_status": revision.approval_status,
                    "scope": ";".join(revision.scope),
                    "position_kind": position_kind,
                    "position_label": f"{position_kind}-{page_number}",
                    "access_scope": revision.access_scope,
                }
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{record.doc_id}:{sha256(identity.encode()).hexdigest()}",
                    document_id=record.doc_id,
                    document_title=record.title,
                    text=piece,
                    source_path=record.source_path,
                    document_version=record.version,
                    language=record.language,
                    category=record.category,
                    topic=record.topic,
                    page_start=page_number,
                    page_end=page_number,
                    **extra,
                )
            )
    return chunks


def chunk_pdf(
    parsed: ParsedPdfDocument,
    record: DocumentRecord,
    config: ChunkingConfig = ChunkingConfig(),
    *,
    revision=None,
) -> list[KnowledgeChunk]:
    """Aggregate consecutive text blocks per physical page, then bounded splitting.

    Document metadata is carried separately from parser metadata.
    """
    if parsed.source_path != record.source_path:
        raise ValueError("parsed source_path does not match the registry record")
    return _build_chunks(
        clean_page_texts(parsed), record, config, CHUNKING_ALGORITHM, revision
    )


def chunk_markdown(
    parsed: ParsedPdfDocument,
    record: DocumentRecord,
    config: ChunkingConfig = ChunkingConfig(),
    *,
    revision=None,
) -> list[KnowledgeChunk]:
    """Chunk heading sections; `page_start/page_end` mean section index here."""
    if parsed.source_path != record.source_path:
        raise ValueError("parsed source_path does not match the registry record")
    return _build_chunks(
        clean_markdown_texts(parsed),
        record,
        config,
        MARKDOWN_CHUNKING_ALGORITHM,
        revision,
    )
