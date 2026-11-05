"""The dual-dense reranker must expose its fixed Top-10 parent pool."""

import pytest

from accelerator_rag.domain.knowledge import KnowledgeChunk, RetrievalResult
from accelerator_rag.retrieval.dense_reranked import DenseRerankedRetriever


def chunk(chunk_id):
    return KnowledgeChunk(
        chunk_id,
        chunk_id.split(":")[0],
        "Design",
        f"winning passage for {chunk_id}",
        "data/l0_raw/design.pdf",
        "2024",
        "en",
        "control",
        "interlock",
        1,
        1,
    )


CHUNKS = [chunk(f"doc{i:02d}:p") for i in range(1, 11)]


class DenseModel:
    def __init__(self):
        self.requested = None

    def search_with_trace(self, query, *, top_k, scope=None):
        self.requested = top_k
        hits = [
            RetrievalResult(rank, 1.0 / rank, item, "fake")
            for rank, item in enumerate(CHUNKS, 1)
        ]
        traces = [
            {
                "parent_chunk_id": item.chunk_id,
                "passage_id": f"passage-{rank}",
                "passage_excerpt": item.text,
            }
            for rank, item in enumerate(CHUNKS, 1)
        ]
        return hits, traces, {}


class Reranker:
    def score(self, query, texts):
        return [1.0 - i / 100 for i, _ in enumerate(texts)]


def test_dual_dense_reranker_returns_ten_parents_for_fusion():
    e5, qwen = DenseModel(), DenseModel()
    retriever = DenseRerankedRetriever(e5, qwen, Reranker())

    hits, trace, candidates = retriever.search_with_trace("interlock", top_k=10)

    assert e5.requested == qwen.requested == 10
    assert [hit.rank for hit in hits] == list(range(1, 11))
    assert len({hit.chunk.chunk_id for hit in hits}) == 10
    assert [row["rank"] for row in trace] == list(range(1, 11))
    assert candidates["parent_count"] == 10


def test_dual_dense_reranker_rejects_more_than_its_parent_pool():
    retriever = DenseRerankedRetriever(DenseModel(), DenseModel(), Reranker())
    with pytest.raises(ValueError, match="one to ten"):
        retriever.search_with_trace("interlock", top_k=11)
