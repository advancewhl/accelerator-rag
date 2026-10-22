from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re

from accelerator_rag.corpus.cleaning import clean_page_texts
from accelerator_rag.corpus.pdf_parser import ParsedPdfDocument
from accelerator_rag.corpus.registry import DocumentRecord
from accelerator_rag.domain.knowledge import KnowledgeChunk


CHUNKING_ALGORITHM = "pdf-chunks-v3"


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


def chunk_pdf(
    parsed: ParsedPdfDocument,
    record: DocumentRecord,
    config: ChunkingConfig = ChunkingConfig(),
) -> list[KnowledgeChunk]:
    """Aggregate consecutive text blocks per physical page, then bounded splitting.

    IDs hash pipeline version, configuration, document/version, page, ordinal and
    normalized text. Document metadata is carried separately from parser metadata.
    """
    if parsed.source_path != record.source_path:
        raise ValueError("parsed source_path does not match the registry record")
    chunks = []
    for page_number, text in clean_page_texts(parsed):
        for ordinal, piece in enumerate(_split_page(text, config)):
            identity = json.dumps(
                [
                    CHUNKING_ALGORITHM,
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
                )
            )
    return chunks
