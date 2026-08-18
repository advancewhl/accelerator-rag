from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytest
from numpy.typing import NDArray
from qdrant_client import QdrantClient

from accelerator_rag.retrieval.qdrant_semantic_search import (
    QdrantSemanticRetriever,
)
from accelerator_rag.retrieval.semantic_search import (
    DocumentChunk,
)
from accelerator_rag.storage import (
    QdrantVectorStore,
)

FloatArray = NDArray[np.float32]


class FakeEmbedder:
    """测试专用 Embedding。"""

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> FloatArray:
        assert len(texts) == 2

        return np.array(
            [
                [1.0, 0.0],
                [0.0, 1.0],
            ],
            dtype=np.float32,
        )

    def embed_query(
        self,
        text: str,
    ) -> FloatArray:
        assert text

        return np.array(
            [1.0, 0.0],
            dtype=np.float32,
        )


@pytest.fixture
def chunks() -> list[DocumentChunk]:
    return [
        DocumentChunk(
            id="pv",
            title="PV",
            text="EPICS PV 示例文本。",
            metadata={
                "system": "EPICS",
            },
        ),
        DocumentChunk(
            id="bpm",
            title="BPM",
            text="BPM 束测示例文本。",
            metadata={
                "system": "Beam Diagnostics",
            },
        ),
    ]


def test_qdrant_semantic_search(
    chunks: list[DocumentChunk],
) -> None:
    client = QdrantClient(":memory:")

    try:
        store = QdrantVectorStore(
            client=client,
            collection_name="test_chunks",
            vector_size=2,
        )

        retriever = QdrantSemanticRetriever(
            embedder=FakeEmbedder(),
            vector_store=store,
        )

        retriever.index_chunks(chunks)

        results = retriever.search(
            query="PV 是什么",
            top_k=1,
        )

        assert len(results) == 1
        assert results[0].rank == 1

        assert results[0].chunk.id == "pv"

        assert results[0].score == pytest.approx(1.0)

    finally:
        client.close()


def test_delete_chunk(
    chunks: list[DocumentChunk],
) -> None:
    client = QdrantClient(":memory:")

    try:
        store = QdrantVectorStore(
            client=client,
            collection_name="test_delete",
            vector_size=2,
        )

        store.ensure_collection()

        vectors = np.array(
            [
                [1.0, 0.0],
                [0.0, 1.0],
            ],
            dtype=np.float32,
        )

        store.upsert_chunks(
            chunks,
            vectors,
        )

        store.delete_chunks(["pv"])

        results = store.search(
            np.array(
                [1.0, 0.0],
                dtype=np.float32,
            ),
            top_k=2,
        )

        assert len(results) == 1

        assert results[0].chunk.id == "bpm"

    finally:
        client.close()


def test_invalid_top_k(
    chunks: list[DocumentChunk],
) -> None:
    client = QdrantClient(":memory:")

    try:
        store = QdrantVectorStore(
            client=client,
            collection_name="test_validation",
            vector_size=2,
        )

        retriever = QdrantSemanticRetriever(
            embedder=FakeEmbedder(),
            vector_store=store,
        )

        retriever.index_chunks(chunks)

        with pytest.raises(
            ValueError,
            match="top_k 必须大于 0",
        ):
            retriever.search(
                query="PV",
                top_k=0,
            )

    finally:
        client.close()
