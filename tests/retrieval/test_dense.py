from dataclasses import replace

import numpy as np
import pytest
from qdrant_client import QdrantClient, models

from accelerator_rag.ingestion import IngestionService
from accelerator_rag.retrieval.dense import DirectChunkDenseRetriever as DenseRetriever
from accelerator_rag.storage import QdrantVectorStore


@pytest.fixture
def client():
    client = QdrantClient(":memory:")
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def store(client):
    return QdrantVectorStore(client, "knowledge", 2)


def test_payload_round_trip_and_delete(store, chunk):
    store.upsert_chunks([chunk], np.array([[1.0, 0.0]]))
    result = store.search(np.array([1.0, 0.0]))[0]
    assert result.chunk == chunk
    assert result.rank == 1 and result.retriever == "qdrant"
    assert result.score == pytest.approx(1.0)
    store.delete_chunks([chunk.chunk_id])
    assert store.search(np.array([1.0, 0.0])) == []


def test_document_replacement_is_idempotent_and_removes_stale_only(store, chunk):
    other_doc = replace(chunk, chunk_id="other:one", document_id="other")
    store.upsert_chunks([chunk, other_doc], np.array([[1.0, 0.0], [0.0, 1.0]]))
    new = replace(
        chunk, chunk_id="new", text="updated evidence", page_start=4, page_end=5
    )
    for _ in range(2):
        store.replace_document(chunk.document_id, [new], np.array([[1.0, 0.0]]))
    results = store.search(np.array([1.0, 0.0]), top_k=10)
    assert {r.chunk.chunk_id for r in results} == {"new", "other:one"}
    assert results[0].chunk == new
    store.replace_document(chunk.document_id, [], np.empty((0, 2)))
    assert [r.chunk for r in store.search(np.array([1.0, 0.0]))] == [other_doc]


@pytest.mark.parametrize(
    "vectors",
    [
        np.array([1.0, 0.0]),
        np.ones((2, 2)),
        np.ones((1, 3)),
        np.array([[np.nan, 1.0]]),
        np.array([[0.0, 0.0]]),
    ],
)
def test_invalid_document_vectors_leave_existing_data(store, chunk, vectors):
    store.upsert_chunks([chunk], np.array([[1.0, 0.0]]))
    with pytest.raises(ValueError):
        store.replace_document(
            chunk.document_id, [replace(chunk, chunk_id="new")], vectors
        )
    assert store.search(np.array([1.0, 0.0]))[0].chunk == chunk


@pytest.mark.parametrize(
    "vector", [np.ones(3), np.ones((1, 2)), np.array([np.inf, 0.0]), np.zeros(2)]
)
def test_invalid_query_vectors(store, vector):
    with pytest.raises(ValueError):
        store.search(vector)


@pytest.mark.parametrize(
    "config",
    [
        models.VectorParams(size=3, distance=models.Distance.COSINE),
        models.VectorParams(size=2, distance=models.Distance.DOT),
        {"named": models.VectorParams(size=2, distance=models.Distance.COSINE)},
    ],
)
def test_incompatible_collections_rejected_before_write_or_search(
    client, chunk, config
):
    client.create_collection("knowledge", vectors_config=config)
    store = QdrantVectorStore(client, "knowledge", 2)
    with pytest.raises(ValueError, match="incompatible"):
        store.upsert_chunks([chunk], np.array([[1.0, 0.0]]))
    with pytest.raises(ValueError, match="incompatible"):
        store.search(np.array([1.0, 0.0]))
    assert client.count("knowledge").count == 0


def test_pdf_to_dense_locates_physical_page(corpus_root, record, store, fake_embedder):
    chunks = IngestionService(corpus_root).ingest_document(record.doc_id)
    retriever = DenseRetriever(fake_embedder, store)
    retriever.index_document(record.doc_id, chunks)
    result = retriever.search("IOC startup", 1)[0]
    assert result.chunk == chunks[1]
    assert result.chunk.page_start == result.chunk.page_end == 3
    assert result.chunk.source_path == record.source_path


@pytest.mark.parametrize("query,k", [("", 1), (" ", 1), ("IOC", 0), ("IOC", -1)])
def test_invalid_search(store, fake_embedder, query, k):
    with pytest.raises(ValueError):
        DenseRetriever(fake_embedder, store).search(query, k)


def test_invalid_payload_fails_without_coercion(client, store, chunk):
    store.ensure_collection()
    client.upsert(
        "knowledge",
        [
            models.PointStruct(
                id=1,
                vector=[1.0, 0.0],
                payload={"text": "missing citation fields"},
            )
        ],
    )
    with pytest.raises(ValueError, match="payload"):
        store.search(np.array([1.0, 0.0]))


def test_replacement_rejects_wrong_document(store, chunk):
    store.upsert_chunks([chunk], np.array([[1.0, 0.0]]))
    with pytest.raises(ValueError, match="document_id"):
        store.replace_document("wrong-document", [chunk], np.array([[1.0, 0.0]]))
    assert store.search(np.array([1.0, 0.0]))[0].chunk == chunk
