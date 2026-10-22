from dataclasses import replace

import pytest
from qdrant_client import QdrantClient

from accelerator_rag.retrieval.bm25 import BM25Retriever
from accelerator_rag.retrieval.dense import DirectChunkDenseRetriever as DenseRetriever
from accelerator_rag.storage import QdrantVectorStore


def test_full_bm25_searches_across_documents(chunk):
    other = replace(
        chunk,
        document_id="cryo",
        document_title="Cryogenic controls",
        chunk_id="cryo:one",
        text="Helium refrigerator compressor.",
    )
    results = BM25Retriever([chunk, other]).search("helium compressor")
    assert results[0].chunk.document_id == "cryo"


def test_full_qdrant_global_idempotence_and_single_embedding_per_run(
    chunk, fake_embedder
):
    chunks = [
        replace(chunk, text="IOC startup"),
        replace(
            chunk, document_id="cryo", chunk_id="cryo:one", text="Helium compressor"
        ),
    ]
    calls = []
    original = fake_embedder.embed_documents

    def track(texts):
        calls.extend(texts)
        return original(texts)

    fake_embedder.embed_documents = track
    client = QdrantClient(":memory:")
    try:
        store = QdrantVectorStore(client, "knowledge_stage2_test", 2)
        retriever = DenseRetriever(fake_embedder, store)
        for _ in range(2):
            indexed = retriever.index_corpus(
                chunks, document_ids=[chunk.document_id, "cryo"], batch_size=1
            )
            assert indexed["point_count"] == len(chunks)
        assert len(calls) == len(chunks) * 2
        assert store.document_ids() == {chunk.document_id, "cryo"}
        assert retriever.search("startup")[0].chunk == chunks[0]
        changed = [replace(chunks[0], chunk_id="new"), chunks[1]]
        retriever.index_corpus(changed, document_ids=[chunk.document_id, "cryo"])
        assert store.point_count() == 2
        with pytest.raises(ValueError, match="unrelated"):
            retriever.index_corpus([chunks[0]], document_ids=[chunk.document_id])
        assert store.point_count() == 2
    finally:
        client.close()


def test_eligible_subset_indexed_idempotently(chunk, fake_embedder):
    from accelerator_rag.corpus.eligibility import eligibility_audit

    cs = [chunk, replace(chunk, chunk_id="thanks", text="THANK YOU")]
    eligible, audit = eligibility_audit(cs)
    assert audit["ineligible_chunks"] == 1
    client = QdrantClient(":memory:")
    try:
        store = QdrantVectorStore(client, "knowledge_stage25_test", 2)
        dense = DenseRetriever(fake_embedder, store)
        for _ in range(2):
            result = dense.index_corpus(eligible, document_ids=[chunk.document_id])
            assert result["point_count"] == len(eligible) == 1
        assert dense.search("IOC")[0].chunk == chunk
    finally:
        client.close()
