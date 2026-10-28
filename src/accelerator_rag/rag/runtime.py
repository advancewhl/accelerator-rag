"""Load signed existing indexes and local models, without ingestion or embedding writes."""

from contextlib import ExitStack, closing
import json
import os
from pathlib import Path

import httpx
from qdrant_client import QdrantClient

from accelerator_rag.embedding import EmbeddingModel
from accelerator_rag.providers.model import OpenAICompatibleModelProvider
from accelerator_rag.retrieval.dense import DenseRetriever
from accelerator_rag.retrieval.dense_reranked import DenseRerankedRetriever
from accelerator_rag.retrieval.index_contract import DenseIndexContract
from accelerator_rag.retrieval.passages import PassageBuilder
from accelerator_rag.retrieval.reranker import Qwen3Reranker
from accelerator_rag.storage.qdrant_passages import QdrantPassageStore
from .service import RagService
from .catalog import DocumentCatalog
from .retrieval import RequirementRetriever


class BoundedGenerationTransport(httpx.BaseTransport):
    """Add RAG-only deterministic decoding without changing the shared provider."""

    def __init__(self, max_tokens=4096):
        if type(max_tokens) is not int or not 1 <= max_tokens <= 4096:
            raise ValueError("generation_max_tokens must be between 1 and 4096")
        self.max_tokens = max_tokens
        self.inner = httpx.HTTPTransport(trust_env=False)

    def handle_request(self, request):
        payload = json.loads(request.content)
        payload.update(
            max_tokens=self.max_tokens,
            temperature=0,
            parallel_tool_calls=False,
            chat_template_kwargs={"enable_thinking": False},
        )
        if len(payload.get("tools", [])) == 1:
            payload["tool_choice"] = {
                "type": "function",
                "function": {"name": payload["tools"][0]["function"]["name"]},
            }
        headers = httpx.Headers(request.headers)
        headers.pop("content-length", None)
        bounded = httpx.Request(
            request.method,
            request.url,
            headers=headers,
            json=payload,
            extensions=request.extensions,
        )
        return self.inner.handle_request(bounded)

    def close(self):
        self.inner.close()


class RagRuntime:
    def __init__(self, config_path: str | Path):
        self.resources = ExitStack()
        try:
            config = json.loads(Path(config_path).read_text())
            self.config = config
            base_url = os.environ.get(
                "ACCELERATOR_MODEL_BASE_URL",
                config.get("model_base_url", "http://127.0.0.1:8000/v1"),
            )
            model_name = os.environ.get(
                "ACCELERATOR_MODEL_NAME", config.get("model_name", "qwen3.8-Flash-Next")
            )
            api_key = os.environ.get("ACCELERATOR_MODEL_API_KEY")
            config.update(model_base_url=base_url, model_name=model_name)
            # Stage 3 data authorization covers only this group service and local
            # deployment/SSH forwards. Redirects and environment proxies are disabled.
            if httpx.URL(base_url).host not in {
                "127.0.0.1",
                "localhost",
                "10.101.9.190",
            }:
                raise ValueError("model endpoint is outside the authorized group")
            dense = []
            canonical_chunks = {}
            self.documents = {}
            self.catalog = DocumentCatalog()
            for entry, name in zip(
                config["indexes"],
                ("intfloat/multilingual-e5-base", "Qwen/Qwen3-Embedding-0.6B"),
                strict=True,
            ):
                if entry["model_name"] != name:
                    raise ValueError("frozen dual-dense model order mismatch")
                embedder = EmbeddingModel(
                    name,
                    model_path=entry["model_path"],
                    device=entry["device"],
                    dtype=entry.get("dtype", "float32"),
                    batch_size=8,
                )
                builder = PassageBuilder(embedder)
                contract = DenseIndexContract.from_fingerprint(
                    embedder.fingerprint(), builder.contract
                )
                if contract.contract_id != entry["dense_index_contract_id"]:
                    raise ValueError(
                        "model or passage contract differs from frozen index"
                    )
                # Refuse absent paths/collections rather than creating an empty index.
                path = Path(entry["index_path"])
                if not (path / "meta.json").is_file():
                    raise ValueError("existing local Qdrant index required")
                client = self.resources.enter_context(
                    closing(QdrantClient(path=str(path)))
                )
                if not client.collection_exists(entry["collection"]):
                    raise ValueError("existing signed collection required")
                store = QdrantPassageStore(client, entry["collection"], contract)
                store.freeze_read_only()
                for passage in store.all_passages():
                    c = passage.parent
                    previous = canonical_chunks.setdefault(c.chunk_id, c)
                    if previous != c:
                        raise ValueError("canonical evidence differs across indexes")
                    source = Path(c.source_path).resolve()
                    root = Path(config.get("source_root", "data/l0_raw")).resolve()
                    if source.is_relative_to(root) and source.suffix.lower() == ".pdf":
                        self.documents[c.document_id] = source
                        self.catalog.add(c, source)
                if store.point_count() != entry["point_count"]:
                    raise ValueError("frozen index point count mismatch")
                dense.append(DenseRetriever(embedder, store, passage_builder=builder))
            self.catalog.finish()
            reranker = Qwen3Reranker(**config["reranker"])
            provider = self.resources.enter_context(
                OpenAICompatibleModelProvider(
                    base_url,
                    model_name,
                    api_key=api_key,
                    read_timeout=120,
                    transport=BoundedGenerationTransport(
                        config.get("generation_max_tokens", 4096)
                    ),
                )
            )
            self.service = RagService(
                DenseRerankedRetriever(*dense, reranker),
                provider,
                requirement_retriever=RequirementRetriever(
                    DenseRerankedRetriever(*dense, reranker),
                    list(canonical_chunks.values()),
                    reranker,
                ),
                count_tokens=lambda text: len(
                    reranker.tokenizer.encode(text, add_special_tokens=False)
                ),
                trace_dir=config.get("trace_dir"),
            )
        except BaseException:
            self.resources.close()
            raise

    def check_generation_service(self):
        key = os.environ.get("ACCELERATOR_MODEL_API_KEY")
        with httpx.Client(
            trust_env=False,
            follow_redirects=False,
            timeout=10,
            headers={"Authorization": f"Bearer {key}"} if key else {},
        ) as http:
            response = http.get(self.config["model_base_url"].rstrip("/") + "/models")
            response.raise_for_status()
            if self.config["model_name"] not in {
                m["id"] for m in response.json()["data"]
            }:
                raise ValueError("configured generation model is not served")

    def answer(self, query: str) -> dict:
        return self.service.answer(query)

    def close(self):
        self.resources.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
