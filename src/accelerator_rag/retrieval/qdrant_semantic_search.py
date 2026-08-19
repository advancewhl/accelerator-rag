from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from accelerator_rag.retrieval.semantic_search import (
    DocumentChunk,
    SearchResult,
    TextEmbedder,
)
from accelerator_rag.storage import QdrantVectorStore


class QdrantSemanticRetriever:
    """基于 Qdrant 的语义检索器。"""

    def __init__(
        self,
        embedder: TextEmbedder,
        vector_store: QdrantVectorStore,
    ) -> None:
        self._embedder = embedder
        self._vector_store = vector_store

    def index_chunks(
        self,
        chunks: Sequence[DocumentChunk],
    ) -> None:
        """为文本块生成 Embedding 并写入 Qdrant。"""

        if not chunks:
            raise ValueError("chunks 不能为空")

        texts = [f"{chunk.title}\n{chunk.text}" for chunk in chunks]

        vectors = self._embedder.embed_documents(texts)

        self._vector_store.ensure_collection()

        self._vector_store.upsert_chunks(
            chunks,
            vectors,
        )

    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[SearchResult]:
        """执行语义检索。"""

        if not query.strip():
            raise ValueError("query 不能为空")

        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        query_vector = self._embedder.embed_query(query)

        query_vector = np.asarray(
            query_vector,
            dtype=np.float32,
        )

        return self._vector_store.search(query_vector, top_k=top_k)
