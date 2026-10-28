"""Public document inventory derived only from the indexes loaded by this runtime."""

from pathlib import Path

import fitz


class DocumentCatalog:
    def __init__(self):
        self._documents = {}
        self._sections = {}
        self._paths = {}

    def add(self, chunk, path: Path):
        row = self._documents.setdefault(
            chunk.document_id,
            {
                "document_id": chunk.document_id,
                "document_title": chunk.document_title,
                "versions": set(),
                "categories": set(),
                "topics": set(),
                "languages": set(),
            },
        )
        row["versions"].add(chunk.document_version)
        row["categories"].add(chunk.category)
        row["topics"].add(chunk.topic)
        row["languages"].add(chunk.language)
        self._sections.setdefault(chunk.document_id, set()).add(chunk.chunk_id)
        self._paths[chunk.document_id] = path

    def finish(self):
        for document_id, row in self._documents.items():
            for field in ("versions", "categories", "topics", "languages"):
                row[field] = sorted(row[field])
            row["indexed_section_count"] = len(self._sections[document_id])
            row["page_count"] = None
            try:
                with fitz.open(self._paths[document_id]) as pdf:
                    row["page_count"] = len(pdf)
            except (OSError, RuntimeError, ValueError):
                # An indexed document remains listed when its original PDF is missing.
                pass
        self._sections.clear()

    def snapshot(self):
        documents = []
        for document_id in sorted(self._documents):
            row = dict(self._documents[document_id])
            available = self._paths[document_id].is_file()
            row.update(
                original_available=available,
                document_url="/v1/rag/documents/" + document_id if available else None,
            )
            documents.append(row)
        return {
            "document_count": len(documents),
            "indexed_section_count": sum(d["indexed_section_count"] for d in documents),
            "documents": documents,
        }
