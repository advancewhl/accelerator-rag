"""Independent API; no Agent routes, graph or Waveform tools."""

from contextlib import asynccontextmanager
from dataclasses import replace
import os
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    StringConstraints,
)

from accelerator_rag.corpus.schema_v2 import DocumentKind
from accelerator_rag.corpus.taxonomy_v2 import TOPICS_BY_CATEGORY
from accelerator_rag.domain.model import ModelProviderError
from accelerator_rag.retrieval.scope import (
    RetrievalScope,
    default_scope,
    reference_scope,
    version_scope,
)
from .answer import AnswerContractError
from .release import ReleaseIdentity, release_identity_from_config, release_status


# Slugs are lower-case identities; a filesystem path or mixed-case name must
# never enter a scope.  The pattern matches Schema v2 family/revision IDs.
RevisionId = Annotated[
    StrictStr,
    StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
]
FamilyId = RevisionId
_DOCUMENT_KINDS = frozenset(item.value for item in DocumentKind)
_TOPICS = frozenset(
    topic for topics in TOPICS_BY_CATEGORY.values() for topic in topics
)
QUERYABLE_USAGE_STATUSES = frozenset(
    {"current", "historical", "reference", "pending_review"}
)


class AnswerScopeRequest(BaseModel):
    """Optional request-wide eligibility; omitted fields preserve old behavior."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    mode: Literal["default", "version", "reference", "compare"] = "default"
    release_id: StrictStr = Field(default="", max_length=128)
    revision_ids: list[RevisionId] = Field(default_factory=list, max_length=32)
    family_ids: list[FamilyId] = Field(default_factory=list, max_length=32)
    usage_statuses: list[StrictStr] = Field(default_factory=list, max_length=4)
    document_kinds: list[StrictStr] = Field(default_factory=list, max_length=16)
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
    if scope.topics:
        topics = frozenset(scope.topics)
        if topics - _TOPICS:
            raise HTTPException(422, detail={"code": "INVALID_RAG_INPUT"})
        filters["topics"] = topics
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


def create_app(service=None, *, config_path=None):
    @asynccontextmanager
    async def lifespan(app):
        if service is not None:
            app.state.rag = service
            yield
        else:
            from .runtime import RagRuntime

            with RagRuntime(config_path or os.environ["RAG_CONFIG"]) as runtime:
                runtime.check_generation_service()
                app.state.rag = runtime
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
        # DOCX/PPTX/XLSX reading copies belong to the frozen release package;
        # silently showing the Markdown reader would misrepresent the source.
        raise HTTPException(
            501,
            detail={
                "code": "READER_NOT_IMPLEMENTED",
                "format": suffix.lstrip(".") or "unknown",
            },
        )

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
        media_type = (
            "text/markdown; charset=utf-8"
            if path.suffix.lower() in {".md", ".markdown"}
            else "application/pdf"
        )
        return FileResponse(
            path,
            media_type=media_type,
            headers={
                "Content-Disposition": "inline",
                "X-Content-Type-Options": "nosniff",
            },
        )

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
