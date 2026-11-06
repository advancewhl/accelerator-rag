"""Independent API; no Agent routes, graph or Waveform tools."""

from contextlib import asynccontextmanager
from dataclasses import replace
import os
from pathlib import Path
import re
import shutil
import zipfile
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    StringConstraints,
)

from accelerator_rag.corpus.schema_v2 import ApprovalStatus, DocumentKind
from accelerator_rag.corpus.taxonomy_v2 import TOPICS_BY_CATEGORY
from accelerator_rag.domain.model import ModelProviderError
from accelerator_rag.retrieval.scope import (
    RetrievalScope,
    default_scope,
    reference_scope,
    version_scope,
)
from .answer import AnswerContractError
from .reader import DocumentReader, ReaderRecord, ReaderUnavailable
from .release import ReleaseIdentity, release_identity_from_config, release_status


# Slugs are lower-case identities; a filesystem path or mixed-case name must
# never enter a scope.  The pattern matches Schema v2 family/revision IDs.
RevisionId = Annotated[
    StrictStr,
    StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
]
FamilyId = RevisionId
_DOCUMENT_KINDS = frozenset(item.value for item in DocumentKind)
_APPROVAL_STATUSES = frozenset(item.value for item in ApprovalStatus)
_TOPICS = frozenset(
    topic for topics in TOPICS_BY_CATEGORY.values() for topic in topics
)
QUERYABLE_USAGE_STATUSES = frozenset(
    {"current", "historical", "reference", "pending_review"}
)
_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".md": "text/markdown; charset=utf-8",
    ".markdown": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    ".doc": "application/msword",
    ".pptx": (
        "application/vnd.openxmlformats-officedocument."
        "presentationml.presentation"
    ),
    ".xlsx": (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv; charset=utf-8",
}
_RECORD_KEYS = (
    "record_id",
    "revision_id",
    "table_block_id",
    "sheet",
    "row_number",
    "headers",
    "cells",
    "row_text",
    "chunk_id",
)
_OFFICE_SUFFIXES = {".docx", ".doc", ".pptx", ".xlsx", ".xls", ".csv"}
# Only browser-renderable raster formats are served.  SVG is deliberately
# excluded: a same-origin SVG can execute script when opened directly.
_IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}
_MEDIA_NAME = re.compile(r"^[0-9a-f]{16}\.[a-z0-9]{2,5}$")


class AnswerScopeRequest(BaseModel):
    """Optional request-wide eligibility; omitted fields preserve old behavior."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    mode: Literal["default", "version", "reference", "compare"] = "default"
    release_id: StrictStr = Field(default="", max_length=128)
    revision_ids: list[RevisionId] = Field(default_factory=list, max_length=32)
    family_ids: list[FamilyId] = Field(default_factory=list, max_length=32)
    usage_statuses: list[StrictStr] = Field(default_factory=list, max_length=4)
    document_kinds: list[StrictStr] = Field(default_factory=list, max_length=16)
    approval_statuses: list[StrictStr] = Field(default_factory=list, max_length=8)
    tags: list[StrictStr] = Field(default_factory=list, max_length=16)
    topics: list[StrictStr] = Field(default_factory=list, max_length=32)


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: StrictStr = Field(min_length=1, max_length=8000)
    scope: AnswerScopeRequest | None = None


def _scope_filters(scope: AnswerScopeRequest) -> dict:
    """Translate explicitly supplied filters into ``RetrievalScope`` fields."""

    filters = {}
    if scope.revision_ids:
        filters["revision_ids"] = frozenset(scope.revision_ids)
    if scope.family_ids:
        filters["family_ids"] = frozenset(scope.family_ids)
    if scope.usage_statuses:
        statuses = frozenset(scope.usage_statuses)
        if statuses - QUERYABLE_USAGE_STATUSES:
            raise HTTPException(
                422, detail={"code": "INVALID_RAG_INPUT"}
            )
        filters["usage_statuses"] = statuses
    if scope.document_kinds:
        kinds = frozenset(scope.document_kinds)
        if kinds - _DOCUMENT_KINDS:
            raise HTTPException(422, detail={"code": "INVALID_RAG_INPUT"})
        filters["document_kinds"] = kinds
    if scope.approval_statuses:
        statuses = frozenset(scope.approval_statuses)
        if statuses - _APPROVAL_STATUSES:
            raise HTTPException(422, detail={"code": "INVALID_RAG_INPUT"})
        filters["approval_statuses"] = statuses
    if scope.topics:
        topics = frozenset(scope.topics)
        if topics - _TOPICS:
            raise HTTPException(422, detail={"code": "INVALID_RAG_INPUT"})
        filters["topics"] = topics
    if scope.tags:
        filters["tags"] = frozenset(scope.tags)
    return filters


def _answer_scope(
    scope: AnswerScopeRequest | None,
    effective_release_id: str = "unknown",
) -> RetrievalScope | None:
    """Build one scope before any recall path runs.

    A client may narrow within the running release, but it cannot claim an
    arbitrary release ID: the response and trace must name the index actually
    being searched.  ``compare`` is deliberately not implemented at this stage.
    """

    if scope is None:
        return None
    if scope.mode == "compare":
        raise HTTPException(422, detail={"code": "COMPARE_NOT_IMPLEMENTED"})
    requested_release = scope.release_id.strip()
    if requested_release and effective_release_id in {"", "unknown"}:
        raise HTTPException(422, detail={"code": "RELEASE_NOT_CONFIGURED"})
    if (
        requested_release
        and effective_release_id not in {"", "unknown"}
        and requested_release != effective_release_id
    ):
        raise HTTPException(422, detail={"code": "RELEASE_NOT_FOUND"})
    release_id = requested_release or effective_release_id
    filters = _scope_filters(scope)
    if scope.mode == "version" and not scope.revision_ids and not scope.family_ids:
        raise HTTPException(422, detail={"code": "VERSION_SCOPE_REQUIRED"})
    if scope.mode == "default":
        if not filters and not release_id:
            return None
        base = default_scope(release_id)
        return replace(base, **filters) if filters else base
    if scope.mode == "version":
        if scope.revision_ids:
            base = version_scope(scope.revision_ids, release_id=release_id)
        else:
            base = RetrievalScope(
                release_id=release_id,
                family_ids=frozenset(scope.family_ids),
                usage_statuses=frozenset(QUERYABLE_USAGE_STATUSES),
                allow_unknown_usage=False,
            )
        extra = {key: value for key, value in filters.items() if key != "revision_ids"}
        return replace(base, **extra) if extra else base
    assert scope.mode == "reference"
    base = reference_scope(
        release_id=release_id,
        revision_ids=scope.revision_ids or None,
    )
    extra = {key: value for key, value in filters.items() if key != "revision_ids"}
    return replace(base, **extra) if extra else base


def _reader_record(app, document_id: str) -> ReaderRecord | None:
    registry = getattr(app.state.rag, "documents", {})
    path = registry.get(document_id)
    if path is None or not path.is_file():
        return None
    sources = getattr(app.state.rag, "document_sources", {})
    titles = getattr(app.state.rag, "document_titles", {})
    source_path = sources.get(document_id) or (
        f"data/l0_raw/office/{path.name}"
    )
    return ReaderRecord(
        document_id=document_id,
        path=path,
        source_path=source_path,
        title=titles.get(document_id) or path.stem,
    )


def _office_content_available(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in {".docx", ".pptx", ".xlsx"}:
        return zipfile.is_zipfile(path)
    if suffix in {".doc", ".xls"}:
        return shutil.which("soffice") is not None
    return suffix == ".csv"


def _reader(app) -> DocumentReader:
    reader = getattr(app.state, "reader", None)
    if reader is None:
        reader = DocumentReader(
            snapshot_dir=getattr(app.state.rag, "snapshot_dir", None)
        )
        app.state.reader = reader
    return reader


def create_app(service=None, *, config_path=None):
    @asynccontextmanager
    async def lifespan(app):
        if service is not None:
            app.state.rag = service
            app.state.reader = getattr(service, "reader", None)
            yield
        else:
            from .runtime import RagRuntime

            with RagRuntime(config_path or os.environ["RAG_CONFIG"]) as runtime:
                runtime.check_generation_service()
                app.state.rag = runtime
                app.state.reader = getattr(runtime, "reader", None)
                yield

    app = FastAPI(title="Standalone RAG", lifespan=lifespan)
    web = Path(__file__).with_name("web")
    app.mount("/assets", StaticFiles(directory=web), name="rag-assets")

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(web / "index.html")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/v1/rag/releases/current")
    def current_release():
        rag = app.state.rag
        identity = getattr(rag, "release", None)
        if not isinstance(identity, ReleaseIdentity):
            identity = release_identity_from_config(getattr(rag, "config", None))
        catalog = getattr(rag, "catalog", None)
        snapshot = catalog.snapshot() if catalog is not None else None
        return release_status(identity, snapshot)

    @app.get("/v1/rag/documents")
    def documents():
        catalog = getattr(app.state.rag, "catalog", None)
        if catalog is None:
            return {
                "document_count": 0,
                "indexed_section_count": 0,
                "documents": [],
                "families": [],
            }
        return catalog.snapshot()

    @app.get("/v1/rag/documents/{document_id}/view", include_in_schema=False)
    def document_view(document_id: str):
        registry = getattr(app.state.rag, "documents", {})
        if document_id not in registry or not registry[document_id].is_file():
            raise HTTPException(404, detail={"code": "DOCUMENT_NOT_FOUND"})
        suffix = registry[document_id].suffix.lower()
        if suffix == ".pdf":
            return FileResponse(web / "document.html")
        if suffix in {".md", ".markdown"}:
            return FileResponse(web / "markdown-document.html")
        if suffix in _OFFICE_SUFFIXES:
            return FileResponse(web / "office-document.html")
        # Unknown formats are registered but have no curated reader.  Never
        # silently show the Markdown or PDF reader for another source type.
        raise HTTPException(
            501,
            detail={
                "code": "READER_NOT_IMPLEMENTED",
                "format": suffix.lstrip(".") or "unknown",
            },
        )

    @app.get("/v1/rag/documents/{document_id}/content")
    def document_content(
        document_id: str,
        offset: int = 0,
        limit: int = 200,
        block_id: str | None = None,
    ):
        if offset < 0 or not 1 <= limit <= 500:
            raise HTTPException(422, detail={"code": "INVALID_CONTENT_RANGE"})
        record = _reader_record(app, document_id)
        if record is None:
            raise HTTPException(404, detail={"code": "DOCUMENT_NOT_FOUND"})
        if record.path.suffix.lower() not in _OFFICE_SUFFIXES:
            raise HTTPException(422, detail={"code": "NATIVE_READER"})
        try:
            payload = _reader(app).read(record)
        except ReaderUnavailable as exc:
            raise HTTPException(
                503,
                detail={
                    "code": "CONTENT_NOT_AVAILABLE",
                    "format": record.path.suffix.lower().lstrip("."),
                    "reason": str(exc),
                },
            ) from exc
        blocks = payload["blocks"]
        total = len(blocks)
        start = min(offset, total)
        if block_id:
            index = next(
                (
                    position
                    for position, block in enumerate(blocks)
                    if block["block_id"] == block_id
                ),
                None,
            )
            if index is None:
                raise HTTPException(
                    404, detail={"code": "ANCHOR_NOT_FOUND"}
                )
            start = max(0, index - 20)
            if index >= start + limit:
                start = max(0, index - limit + 1)
        end = min(start + limit, total)
        outline = [
            {
                "ordinal": block["ordinal"],
                "text": block["text"],
                "heading_level": block["heading_level"],
            }
            for block in blocks
            if block["block_type"] == "heading" and block["text"].strip()
        ]
        return {
            **{key: value for key, value in payload.items() if key != "blocks"},
            "blocks": blocks[start:end],
            "total_blocks": total,
            "offset": start,
            "next_offset": end if end < total else None,
            "outline": outline,
        }

    @app.get("/v1/rag/documents/{document_id}/media/{name}")
    def document_media(document_id: RevisionId, name: str):
        if not _MEDIA_NAME.fullmatch(name):
            raise HTTPException(404, detail={"code": "MEDIA_NOT_FOUND"})
        if _reader_record(app, document_id) is None:
            raise HTTPException(404, detail={"code": "DOCUMENT_NOT_FOUND"})
        snapshot_dir = getattr(app.state.rag, "snapshot_dir", None)
        if not snapshot_dir:
            raise HTTPException(404, detail={"code": "MEDIA_NOT_FOUND"})
        media_root = (Path(snapshot_dir) / "media").resolve()
        path = (media_root / document_id / name).resolve()
        media_type = _IMAGE_TYPES.get(path.suffix.lower())
        if (
            not path.is_relative_to(media_root)
            or path.is_symlink()
            or not path.is_file()
            or media_type is None
        ):
            raise HTTPException(404, detail={"code": "MEDIA_NOT_FOUND"})
        return FileResponse(
            path,
            media_type=media_type,
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, max-age=3600",
            },
        )

    @app.get("/v1/rag/documents/{document_id}/metadata")
    def document_metadata(document_id: str):
        record = _reader_record(app, document_id)
        if record is None:
            raise HTTPException(404, detail={"code": "DOCUMENT_NOT_FOUND"})
        catalog = getattr(app.state.rag, "catalog", None)
        getter = getattr(catalog, "get", None)
        row = getter(document_id) if callable(getter) else None
        suffix = record.path.suffix.lower()
        return {
            "document": row,
            "document_id": document_id,
            "document_title": record.title,
            "document_format": suffix.lstrip("."),
            "reader_kind": (
                "pdf"
                if suffix == ".pdf"
                else "markdown"
                if suffix in {".md", ".markdown"}
                else "office"
            ),
            "content_available": (
                _office_content_available(record.path)
                if suffix in _OFFICE_SUFFIXES
                else suffix in {".md", ".markdown"}
            ),
            "snapshot_available": bool(
                getattr(app.state.rag, "snapshot_dir", None)
            ),
        }

    @app.get("/v1/rag/documents/{document_id}/sections")
    def document_sections(document_id: str):
        from accelerator_rag.corpus.markdown_parser import parse_markdown

        path = getattr(app.state.rag, "documents", {}).get(document_id)
        if path is None or not path.is_file():
            raise HTTPException(404, detail={"code": "DOCUMENT_NOT_FOUND"})
        if path.suffix.lower() not in {".md", ".markdown"}:
            raise HTTPException(422, detail={"code": "NOT_MARKDOWN"})
        parsed = parse_markdown(path)
        return {
            "sections": [{"index": p.page_number, "text": p.text} for p in parsed.pages]
        }

    @app.get("/v1/rag/documents/{document_id}")
    def document(document_id: str):
        registry = getattr(app.state.rag, "documents", {})
        path = registry.get(document_id)
        if path is None or not path.is_file():
            raise HTTPException(404, detail={"code": "DOCUMENT_NOT_FOUND"})
        suffix = path.suffix.lower()
        media_type = _MEDIA_TYPES.get(suffix, "application/octet-stream")
        disposition = "attachment" if suffix in _OFFICE_SUFFIXES else "inline"
        filename = quote(path.name, safe="")
        return FileResponse(
            path,
            media_type=media_type,
            headers={
                "Content-Disposition": (
                    f"{disposition}; filename*=UTF-8''{filename}"
                ),
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, max-age=0, must-revalidate",
            },
        )

    @app.get("/v1/rag/structured/lookup")
    def structured_lookup(
        q: str,
        document_id: list[str] | None = Query(default=None),
        limit: int = 50,
    ):
        """Ranked exact row matches with headers bound to every value.

        ``records`` keeps the near-best rows the answer path also injects;
        ``hits`` adds the score, matched constraints and reader location so a
        workbench can show the row and open the source at that row.
        """

        q = q.strip()
        if not q or len(q) > 500:
            raise HTTPException(422, detail={"code": "INVALID_LOOKUP_QUERY"})
        limit = max(1, min(int(limit), 200))
        index = getattr(app.state.rag, "table_records", None)
        if index is None:
            return {"query": q, "count": 0, "records": [], "hits": []}
        revision_ids = set(document_id) if document_id else None
        search = getattr(index, "search", None)
        if not callable(search):
            records = index.lookup_in_text(q, revision_ids=revision_ids)
            return {
                "query": q,
                "count": len(records),
                "records": [record.to_dict() for record in records],
                "hits": [],
            }
        hits = search(q, revision_ids, limit=limit)
        best = hits[0].score if hits else 0.0
        catalog = getattr(app.state.rag, "catalog", None)
        getter = getattr(catalog, "get", None)
        rows = []
        for hit in hits:
            record = hit.record
            row = getter(record.revision_id) if callable(getter) else None
            payload = hit.to_dict()
            payload["near_best"] = hit.score >= best * 0.85
            payload["fields"] = [
                {
                    "column": column,
                    "header": header,
                    "value": value,
                }
                for (column, value), header in zip(
                    record.cells, record.headers, strict=False
                )
                if value
            ]
            payload["location"] = f"{record.sheet}!{record.row_number}"
            payload["document_title"] = (
                (row or {}).get("document_title") or record.revision_id
            )
            payload["document_format"] = (row or {}).get("document_format", "")
            payload["usage_statuses"] = (row or {}).get("usage_statuses", [])
            payload["document_url"] = f"/v1/rag/documents/{record.revision_id}"
            payload["view_url"] = (
                f"/v1/rag/documents/{record.revision_id}/view?embedded=1"
                f"&block_id={quote(record.table_block_id, safe='')}"
                f"&row={record.row_number}"
            )
            rows.append(payload)
        unmatched_fn = getattr(index, "unmatched_identifiers", None)
        unmatched = (
            unmatched_fn(q, revision_ids) if callable(unmatched_fn) else []
        )
        if unmatched:
            for item in rows:
                item["near_best"] = False
        near = [item for item in rows if item["near_best"]]
        return {
            "query": q,
            "unmatched_identifiers": unmatched,
            "count": len(near),
            "records": [
                {key: item[key] for key in _RECORD_KEYS} for item in near
            ],
            "hits": rows,
        }

    @app.post("/v1/rag/answer")
    def answer(request: AnswerRequest):
        try:
            effective_release = (
                getattr(app.state.rag, "release_id", "unknown") or "unknown"
            )
            scope = _answer_scope(request.scope, effective_release)
            return app.state.rag.answer(request.query, scope=scope)
        except AnswerContractError as exc:
            raise HTTPException(
                502, detail={"code": "INVALID_GROUNDED_ANSWER"}
            ) from exc
        except ModelProviderError as exc:
            raise HTTPException(502, detail={"code": exc.code}) from exc
        except ValueError as exc:
            raise HTTPException(422, detail={"code": "INVALID_RAG_INPUT"}) from exc

    return app
