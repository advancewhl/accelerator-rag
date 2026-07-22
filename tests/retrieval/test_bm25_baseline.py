from __future__ import annotations

import pytest

from accelerator_rag.retrieval.bm25_baseline import (
    BM25BaselineRetriever,
    tokenize,
)
from accelerator_rag.retrieval.semantic_search import DocumentChunk


@pytest.fixture
def chunks() -> list[DocumentChunk]:
    return [
        DocumentChunk(
            id="pv",
            title="EPICS PV",
            text="PV 是 EPICS 中的 Process Variable，也就是过程变量。",
            metadata={"system": "EPICS"},
        ),
        DocumentChunk(
            id="bpm",
            title="BPM",
            text="BPM 用于测量加速器中的束流位置。",
            metadata={"system": "Beam Diagnostics"},
        ),
        DocumentChunk(
            id="pv-name",
            title="PV Name",
            text="束流位置的水平读数可以通过 SR:BPM01:X 获取。",
            metadata={"system": "EPICS"},
        ),
    ]


def test_tokenize_preserves_pv_name() -> None:
    tokens = tokenize("读取 SR:BPM01:X 的值")

    assert "sr:bpm01:x" in tokens


def test_search_exact_acronym(
    chunks: list[DocumentChunk],
) -> None:
    retriever = BM25BaselineRetriever(chunks)

    results = retriever.search(
        "BPM",
        top_k=1,
    )

    assert len(results) == 1
    assert results[0].chunk.id == "bpm"


def test_search_exact_pv_name(
    chunks: list[DocumentChunk],
) -> None:
    retriever = BM25BaselineRetriever(chunks)

    results = retriever.search(
        "SR:BPM01:X",
        top_k=1,
    )

    assert len(results) == 1
    assert results[0].chunk.id == "pv-name"


def test_unrelated_query_returns_empty(
    chunks: list[DocumentChunk],
) -> None:
    retriever = BM25BaselineRetriever(chunks)

    results = retriever.search(
        "superconducting cavity",
    )

    assert results == []


def test_invalid_top_k(
    chunks: list[DocumentChunk],
) -> None:
    retriever = BM25BaselineRetriever(chunks)

    with pytest.raises(
        ValueError,
        match="top_k",
    ):
        retriever.search(
            "BPM",
            top_k=0,
        )