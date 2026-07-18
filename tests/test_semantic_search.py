from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytest
from numpy.typing import NDArray

from accelerator_rag.retrieval.semantic_search import (
    DocumentChunk,
    InMemorySemanticRetriever,
)

FloatArray = NDArray[np.float32]


class FakeEmbedder:
    """测试专用的假 Embedding 模型。"""

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
            text="PV 是过程变量。",
            metadata={"system": "EPICS"},
        ),
        DocumentChunk(
            id="bpm",
            title="BPM",
            text="BPM 用于测量束流位置。",
            metadata={"system": "Beam Diagnostics"},
        ),
    ]


def test_search_returns_most_similar_chunk(
    chunks: list[DocumentChunk],
) -> None:
    retriever = InMemorySemanticRetriever(
        chunks=chunks,
        embedder=FakeEmbedder(),
    )

    results = retriever.search(
        query="PV 是什么",
        top_k=1,
    )

    assert len(results) == 1
    assert results[0].chunk.id == "pv"
    assert results[0].rank == 1
    assert results[0].score == pytest.approx(1.0)


def test_search_rejects_invalid_top_k(
    chunks: list[DocumentChunk],
) -> None:
    retriever = InMemorySemanticRetriever(
        chunks=chunks,
        embedder=FakeEmbedder(),
    )

    with pytest.raises(
        ValueError,
        match="top_k 必须大于 0",
    ):
        retriever.search(
            query="PV 是什么",
            top_k=0,
        )
