from dataclasses import asdict, replace
from unittest.mock import Mock

import numpy as np
import pytest
from qdrant_client import QdrantClient

from accelerator_rag.retrieval.dense import DenseRetriever
from accelerator_rag.retrieval.index_contract import DenseIndexContract
from accelerator_rag.retrieval.passages import PassageBuilder, PassageConfig
from accelerator_rag.storage.qdrant_passages import QdrantPassageStore


def test_contract_identity_excludes_operational_identity(passage_embedder):
    b = PassageBuilder(passage_embedder)
    fp = passage_embedder.fingerprint()
    c = DenseIndexContract.from_fingerprint(fp, b.contract)
    assert (
        c.contract_id
        == DenseIndexContract.from_fingerprint(
            {**fp, "batch_size": 2, "local_model_path": "/another/path", "threads": 32},
            b.contract,
        ).contract_id
    )
    for field, value in {
        "weights_manifest_sha256": "changed",
        "query_template": "query: {query}",
        "document_prefix": "passage: ",
        "tokenizer_sha256": "changed",
        "dimension": 768,
        "passage_contract_id": "changed",
        "distance": "dot",
        "normalize_embeddings": False,
        "model_config_sha256": "changed",
        "encoding_config_sha256": "changed",
        "max_seq_length": 1024,
    }.items():
        assert replace(c, **{field: value}).contract_id != c.contract_id
    assert DenseIndexContract(**asdict(c)) == c


def test_reopen_rejects_new_passage_policy_before_mutation(
    tmp_path, chunk, passage_embedder
):
    path = str(tmp_path / "policies")
    a, b = (
        replace(chunk, document_id="A", chunk_id="A"),
        replace(chunk, document_id="B", chunk_id="B"),
    )
    old = PassageBuilder(passage_embedder, PassageConfig(max_tokens=120))
    x = DenseIndexContract.from_fingerprint(
        passage_embedder.fingerprint(), old.contract
    )
    client = QdrantClient(path=path)
    store = QdrantPassageStore(client, "policy", x)
    dense = DenseRetriever(passage_embedder, store, passage_builder=old)
    dense.index_document("A", [a])
    dense.index_document("B", [b])
    original = client.scroll("policy", limit=100, with_vectors=True)[0]
    client.close()
    client = QdrantClient(path=path)
    try:
        new = PassageBuilder(passage_embedder, PassageConfig(max_tokens=150))
        y = DenseIndexContract.from_fingerprint(
            passage_embedder.fingerprint(), new.contract
        )
        bad = DenseRetriever(
            passage_embedder,
            QdrantPassageStore(client, "policy", y),
            passage_builder=new,
        )
        encoded = list(passage_embedder.encoded)
        passage_embedder.embed_query = Mock(
            side_effect=AssertionError("must reject before query embedding")
        )
        for action in [
            lambda: bad.index_document("A", [a]),
            lambda: bad.index_corpus([a, b], document_ids=["A", "B"]),
            lambda: bad.search("q"),
        ]:
            with pytest.raises(ValueError, match="new collection or rebuild"):
                action()
        assert passage_embedder.encoded == encoded
        passage_embedder.embed_query.assert_not_called()
        assert client.scroll("policy", limit=100, with_vectors=True)[0] == original
    finally:
        client.close()


def test_same_768_dimension_different_model_rejected_after_reopen(
    tmp_path, chunk, passage_embedder
):
    passage_embedder.dimension = 768
    builder = PassageBuilder(passage_embedder)
    fp = passage_embedder.fingerprint()
    x = DenseIndexContract.from_fingerprint(fp, builder.contract)
    path = str(tmp_path / "models")
    client = QdrantClient(path=path)
    store = QdrantPassageStore(client, "models", x)
    ps = builder.build([chunk])
    store.upsert_passages(ps, np.array([[1.0] + [0.0] * 767]))
    original = client.scroll("models", limit=100, with_vectors=True)[0]
    client.close()
    client = QdrantClient(path=path)
    try:
        passage_embedder.fingerprint = Mock(
            return_value={
                **fp,
                "requested_model_name": "E5-like",
                "weights_manifest_sha256": "different-768-model",
            }
        )
        y = DenseIndexContract.from_fingerprint(
            passage_embedder.fingerprint(), builder.contract
        )
        bad = DenseRetriever(
            passage_embedder,
            QdrantPassageStore(client, "models", y),
            passage_builder=builder,
        )
        passage_embedder.embed_query = Mock(
            side_effect=AssertionError("no query encode")
        )
        for action in [
            lambda: bad.search("q"),
            lambda: bad.index_document(chunk.document_id, [chunk]),
            lambda: bad.index_corpus([chunk], document_ids=[chunk.document_id]),
        ]:
            with pytest.raises(ValueError, match="contract mismatch"):
                action()
        passage_embedder.embed_query.assert_not_called()
        assert not passage_embedder.encoded
        assert client.scroll("models", limit=100, with_vectors=True)[0] == original
        # A mixed point anywhere in the collection is also rejected on reads.
        client.set_payload(
            "models",
            payload={"dense_index_contract_id": y.contract_id},
            points=[original[0].id],
        )
        with pytest.raises(ValueError, match="contract mismatch"):
            list(QdrantPassageStore(client, "models", x).all_passages())
    finally:
        client.close()
