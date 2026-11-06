"""Public document inventory derived only from the indexes loaded by this runtime.

The catalog never exposes source paths.  Schema v2 metadata is reported when a
chunk carries it; legacy v1 chunks keep their existing fields and every absent
governance value is reported as ``unknown`` instead of being inferred.  The one
compatibility mapping is the family: a legacy chunk without ``family_id`` is
grouped under its own ``document_id``, which is exactly the
``KnowledgeChunk.effective_family_id`` rule used by retrieval scopes.
"""

from pathlib import Path

import fitz

from accelerator_rag.domain.position import PositionKind


UNKNOWN = "unknown"
_READER_FORMATS = frozenset(
    {"pdf", "md", "markdown", "docx", "doc", "pptx", "xlsx", "xls", "csv"}
)
_TEXT_FIELDS = (
    ("revision_labels", "revision_label"),
    ("usage_statuses", "usage_status"),
    ("document_kinds", "document_kind"),
    ("evidence_roles", "evidence_role"),
    ("approval_statuses", "approval_status"),
    ("access_scopes", "access_scope"),
)


def _text(chunk, name: str) -> str:
    """Read additive metadata from real chunks and legacy test doubles alike."""

    value = getattr(chunk, name, "")
    return value if isinstance(value, str) else ""


def _reader_kind(document_format: str | None) -> str:
    if document_format == "pdf":
        return "pdf"
    if document_format in {"md", "markdown"}:
        return "markdown"
    if document_format in _READER_FORMATS:
        return "office"
    return ""


def _position_kind(chunk, path: Path) -> str:
    explicit = _text(chunk, "position_kind")
    if explicit:
        return explicit
    effective = getattr(chunk, "effective_position_kind", "")
    if isinstance(effective, str) and effective:
        return effective
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return PositionKind.SECTION.value
    if suffix == ".pdf":
        return PositionKind.PDF_PAGE.value
    return UNKNOWN


class DocumentCatalog:
    def __init__(self):
        self._documents = {}
        self._sections = {}
        self._paths = {}
        self._scopes = {}

    def add(self, chunk, path: Path):
        if _text(chunk, "access_scope") == "restricted":
            # Defense in depth: the runtime also skips restricted chunks, but a
            # catalog constructed by another caller must not expose them.
            return
        row = self._documents.setdefault(
            chunk.document_id,
            {
                "document_id": chunk.document_id,
                "document_title": chunk.document_title,
                "versions": set(),
                "revision_labels": set(),
                "family_ids": set(),
                "usage_statuses": set(),
                "document_kinds": set(),
                "evidence_roles": set(),
                "approval_statuses": set(),
                "access_scopes": set(),
                "position_kinds": set(),
                "categories": set(),
                "topics": set(),
                "languages": set(),
                "tags": set(),
            },
        )
        row["versions"].add(chunk.document_version)
        row["family_ids"].add(_text(chunk, "family_id") or chunk.document_id)
        for row_field, chunk_field in _TEXT_FIELDS:
            row[row_field].add(_text(chunk, chunk_field) or UNKNOWN)
        row["position_kinds"].add(_position_kind(chunk, path))
        row["categories"].add(chunk.category)
        row["topics"].add(chunk.topic)
        row["languages"].add(chunk.language)
        scope = _text(chunk, "scope")
        if scope:
            self._scopes.setdefault(chunk.document_id, set()).update(
                token.strip() for token in scope.split(";") if token.strip()
            )
        row["tags"].update(
            tag.strip()
            for tag in _text(chunk, "tags").split(";")
            if tag.strip()
        )
        self._sections.setdefault(chunk.document_id, set()).add(chunk.chunk_id)
        self._paths[chunk.document_id] = path

    def finish(self):
        for document_id, row in self._documents.items():
            for field in (
                "versions",
                "revision_labels",
                "family_ids",
                "usage_statuses",
                "document_kinds",
                "evidence_roles",
                "approval_statuses",
                "access_scopes",
                "position_kinds",
                "categories",
                "topics",
                "languages",
                "tags",
            ):
                row[field] = sorted(row[field])
            row["indexed_section_count"] = len(self._sections[document_id])
            row["page_count"] = None
            path = self._paths[document_id]
            row["document_format"] = path.suffix.lower().lstrip(".") or None
            if row["document_format"] == "pdf":
                try:
                    with fitz.open(path) as pdf:
                        row["page_count"] = len(pdf)
                except (OSError, RuntimeError, ValueError):
                    # An indexed document remains listed when its original PDF is missing.
                    pass
        self._sections.clear()

    def _families(self, documents: list[dict]) -> list[dict]:
        grouped: dict[str, list[dict]] = {}
        for document in documents:
            family_ids = document["family_ids"]
            family_id = family_ids[0] if family_ids else document["document_id"]
            grouped.setdefault(family_id, []).append(document)
        families = []
        for family_id in sorted(grouped):
            revisions = sorted(grouped[family_id], key=lambda row: row["document_id"])
            families.append(
                {
                    "family_id": family_id,
                    # Any member title is acceptable; pick deterministically.
                    "title": revisions[0]["document_title"],
                    "revisions": [
                        {
                            "document_id": row["document_id"],
                            "revision_label": row["revision_labels"][0],
                            "usage_status": row["usage_statuses"][0],
                            "approval_status": row["approval_statuses"][0],
                            "scope": sorted(
                                self._scopes.get(row["document_id"], set())
                            ),
                            "tags": row["tags"],
                        }
                        for row in revisions
                    ],
                    "revision_count": len(revisions),
                }
            )
        return families

    def get(self, document_id: str):
        """One catalog row without forcing a full snapshot."""

        if document_id not in self._documents:
            return None
        row = dict(self._documents[document_id])
        available = self._paths[document_id].is_file()
        readable = row.get("document_format") in _READER_FORMATS
        row.update(
            original_available=available,
            reader_available=readable,
            document_url=(
                "/v1/rag/documents/" + document_id
                if available and readable
                else None
            ),
            download_url=(
                "/v1/rag/documents/" + document_id if available else None
            ),
            reader_kind=_reader_kind(row.get("document_format")),
        )
        return row

    def snapshot(self):
        documents = []
        for document_id in sorted(self._documents):
            row = self.get(document_id)
            documents.append(row)
        return {
            "document_count": len(documents),
            "indexed_section_count": sum(d["indexed_section_count"] for d in documents),
            "documents": documents,
            "families": self._families(documents),
        }
