from dataclasses import dataclass
from pathlib import Path

from accelerator_rag.corpus.chunking import ChunkingConfig, chunk_pdf
from accelerator_rag.corpus.pdf_parser import ParsedPdfDocument, parse_pdf
from accelerator_rag.corpus.registry import DocumentRecord, load_registry
from accelerator_rag.domain.knowledge import KnowledgeChunk


@dataclass(frozen=True)
class IngestedDocument:
    record: DocumentRecord
    parsed: ParsedPdfDocument
    chunks: list[KnowledgeChunk]


class IngestionError(RuntimeError):
    """A source failed ingestion; the message includes document and source identity."""


class IngestionService:
    """Read registered PDFs once per run; never consume legacy parsed JSON."""

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

    def _ingest_pdf(self, record: DocumentRecord) -> IngestedDocument:
        try:
            source_root = (self.project_root / "data/l0_raw").resolve()
            local_path = (self.project_root / record.source_path).resolve()
            if not local_path.is_relative_to(source_root):
                raise ValueError("resolved source escapes data/l0_raw")
            parsed = parse_pdf(local_path, source_path=record.source_path)
            return IngestedDocument(
                record, parsed, chunk_pdf(parsed, record, self.chunking)
            )
        except Exception as exc:
            raise IngestionError(
                f"document_id={record.doc_id}, source={record.source_path}: {exc}"
            ) from exc

    def ingest_document(self, document_id: str) -> list[KnowledgeChunk]:
        if document_id not in self.records:
            raise ValueError(f"document_id is not registered: {document_id}")
        record = self.records[document_id]
        if record.document_type != "pdf":
            raise ValueError("only PDF ingestion is supported")
        return self._ingest_pdf(record).chunks

    def ingest_all_registered_pdfs(self) -> list[IngestedDocument]:
        """Serial, fail-fast batch. Retain parsed evidence for the audit, no reparse."""
        return [
            self._ingest_pdf(record)
            for record in self.records.values()
            if record.document_type == "pdf"
        ]
