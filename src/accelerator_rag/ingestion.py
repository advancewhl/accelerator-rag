from dataclasses import dataclass
from pathlib import Path

from accelerator_rag.corpus.chunking import (
    ChunkingConfig,
    chunk_markdown,
    chunk_pdf,
)
from accelerator_rag.corpus.markdown_parser import parse_markdown
from accelerator_rag.corpus.pdf_parser import ParsedPdfDocument, parse_pdf
from accelerator_rag.corpus.registry import DocumentRecord, load_registry
from accelerator_rag.domain.knowledge import KnowledgeChunk


# Only these document types have a parser today. Registry accepts more types
# (docx/txt/pptx) for inventory purposes; ingestion rejects them explicitly.
SUPPORTED_INGESTION_TYPES = frozenset({"pdf", "md"})


@dataclass(frozen=True)
class IngestedDocument:
    record: DocumentRecord
    parsed: ParsedPdfDocument
    chunks: list[KnowledgeChunk]


class IngestionError(RuntimeError):
    """A source failed ingestion; the message includes document and source identity."""


class IngestionService:
    """Read registered PDFs/Markdown once per run; never consume legacy parsed JSON."""

    def __init__(
        self,
        project_root: str | Path,
        registry_path: str | Path = "data/documents/registry.json",
        chunking: ChunkingConfig = ChunkingConfig(),
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.records = {
            r.doc_id: r for r in load_registry(self.project_root / registry_path)
        }
        self.chunking = chunking

    def _local_source(self, record: DocumentRecord) -> Path:
        source_root = (self.project_root / "data/l0_raw").resolve()
        local_path = (self.project_root / record.source_path).resolve()
        if not local_path.is_relative_to(source_root):
            raise ValueError("resolved source escapes data/l0_raw")
        return local_path

    def _ingest(self, record: DocumentRecord) -> IngestedDocument:
        try:
            local_path = self._local_source(record)
            if record.document_type == "pdf":
                parsed = parse_pdf(local_path, source_path=record.source_path)
                chunks = chunk_pdf(parsed, record, self.chunking)
            elif record.document_type == "md":
                parsed = parse_markdown(local_path, source_path=record.source_path)
                chunks = chunk_markdown(parsed, record, self.chunking)
            else:
                raise ValueError(
                    "unsupported ingestion type: "
                    f"{record.document_type} (supported: "
                    f"{', '.join(sorted(SUPPORTED_INGESTION_TYPES))})"
                )
            return IngestedDocument(record, parsed, chunks)
        except Exception as exc:
            raise IngestionError(
                f"document_id={record.doc_id}, source={record.source_path}: {exc}"
            ) from exc

    def ingest_document(self, document_id: str) -> list[KnowledgeChunk]:
        return self.ingest_document_record(document_id).chunks

    def ingest_document_record(self, document_id: str) -> IngestedDocument:
        """Same as `ingest_document` but keeps the parsed source for audits."""
        if document_id not in self.records:
            raise ValueError(f"document_id is not registered: {document_id}")
        record = self.records[document_id]
        if record.document_type not in SUPPORTED_INGESTION_TYPES:
            raise ValueError(
                "unsupported ingestion type: "
                f"{record.document_type} (supported: "
                f"{', '.join(sorted(SUPPORTED_INGESTION_TYPES))})"
            )
        return self._ingest(record)

    def ingest_all_registered(self) -> list[IngestedDocument]:
        """Serial, fail-fast batch over every supported registered document."""
        return [
            self._ingest(record)
            for record in self.records.values()
            if record.document_type in SUPPORTED_INGESTION_TYPES
        ]

    def ingest_all_registered_pdfs(self) -> list[IngestedDocument]:
        """PDF-only batch kept for the frozen Stage 2 baselines.

        New corpora must use `ingest_all_registered`; this method exists so
        historical reports can be reproduced byte-for-byte.
        """
        return [
            self._ingest(record)
            for record in self.records.values()
            if record.document_type == "pdf"
        ]
