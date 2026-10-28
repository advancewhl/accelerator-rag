"""Independent API; no Agent routes, graph or Waveform tools."""

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from accelerator_rag.domain.model import ModelProviderError
from .answer import AnswerContractError


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: StrictStr = Field(min_length=1, max_length=8000)


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

    @app.get("/v1/rag/documents")
    def documents():
        catalog = getattr(app.state.rag, "catalog", None)
        if catalog is None:
            return {"document_count": 0, "indexed_section_count": 0, "documents": []}
        return catalog.snapshot()

    @app.get("/v1/rag/documents/{document_id}/view", include_in_schema=False)
    def document_view(document_id: str):
        registry = getattr(app.state.rag, "documents", {})
        if document_id not in registry:
            raise HTTPException(404, detail={"code": "DOCUMENT_NOT_FOUND"})
        return FileResponse(web / "document.html")

    @app.get("/v1/rag/documents/{document_id}")
    def document(document_id: str):
        registry = getattr(app.state.rag, "documents", {})
        path = registry.get(document_id)
        if path is None or not path.is_file():
            raise HTTPException(404, detail={"code": "DOCUMENT_NOT_FOUND"})
        return FileResponse(
            path,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "inline",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.post("/v1/rag/answer")
    def answer(request: AnswerRequest):
        try:
            return app.state.rag.answer(request.query)
        except AnswerContractError as exc:
            raise HTTPException(
                502, detail={"code": "INVALID_GROUNDED_ANSWER"}
            ) from exc
        except ModelProviderError as exc:
            raise HTTPException(502, detail={"code": exc.code}) from exc
        except ValueError as exc:
            raise HTTPException(422, detail={"code": "INVALID_RAG_INPUT"}) from exc

    return app
