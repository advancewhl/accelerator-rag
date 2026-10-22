from dataclasses import replace, asdict
import numpy as np
import pytest
from qdrant_client import QdrantClient
from accelerator_rag.retrieval.passages import PassageBuilder, PassageConfig
from accelerator_rag.retrieval.dense import DenseRetriever
from accelerator_rag.storage.qdrant_passages import QdrantPassageStore
from accelerator_rag.embedding import document_embedding_text
from accelerator_rag.retrieval.index_contract import DenseIndexContract


def contract_for(embedder, builder=None):
    builder = builder or PassageBuilder(embedder)
    return DenseIndexContract.from_fingerprint(embedder.fingerprint(), builder.contract)


def test_budget_ids_parent_integrity_and_overlap(chunk, passage_embedder):
    original = replace(
        chunk,
        document_title="Title",
        text="x" * 400 + "BOUNDARY_EVIDENCE_TARGET" + "x" * 500,
    )
    before = asdict(original)
    config = PassageConfig(max_tokens=128, guard_tokens=8, overlap_tokens=32)
    builder = PassageBuilder(passage_embedder, config)
    ps = builder.build([original])
    assert len(ps) > 1 and ps == builder.build([original])
    assert [p.passage_ordinal for p in ps] == list(range(len(ps)))
    assert all(
        p.parent_chunk_id == original.chunk_id and p.parent == original for p in ps
    )
    assert all(
        r["token_count"] <= 128
        for r in passage_embedder.audit_inputs([document_embedding_text(p) for p in ps])
    )
    assert any("BOUNDARY_EVIDENCE_TARGET" in p.text for p in ps)
    changed = PassageBuilder(
        passage_embedder, replace(config, overlap_tokens=24)
    ).build([original])
    assert {p.passage_id for p in changed}.isdisjoint({p.passage_id for p in ps})
    assert asdict(original) == before
    other = replace(original, chunk_id="other")
    assert {p.passage_id for p in builder.build([other])}.isdisjoint(
        {p.passage_id for p in ps}
    )
    # Every non-whitespace source character has passage coverage.
    covered = set(i for p in ps for i in range(p.char_start, p.char_end))
    assert covered == set(range(len(original.text)))


def test_boundary_evidence_needs_overlap(chunk, passage_embedder):
    config = PassageConfig(max_tokens=96, guard_tokens=8, overlap_tokens=32)
    builder = PassageBuilder(passage_embedder, config)
    title = "T"
    budget = 96 - 8 - builder.count(title, "")
    text = "x" * (budget - 9) + "EVIDENCE_AT_BOUNDARY" + "x" * 140
    parent = replace(chunk, document_title=title, text=text)
    ps = builder.build([parent])
    assert any("EVIDENCE_AT_BOUNDARY" in p.text for p in ps)
    zero = PassageBuilder(passage_embedder, replace(config, overlap_tokens=0)).build(
        [parent]
    )
    assert not any("EVIDENCE_AT_BOUNDARY" in p.text for p in zero)


def test_fitting_input_remains_exact_and_title_counted(chunk, passage_embedder):
    c = replace(chunk, text="8 GeV")
    builder = PassageBuilder(passage_embedder)
    ps = builder.build([c])
    assert len(ps) == 1 and ps[0].text == c.text
    assert document_embedding_text(ps[0]) == document_embedding_text(c)
    huge_title = replace(c, document_title="T" * 510, text="body" * 30)
    with pytest.raises(ValueError, match="title"):
        builder.build([huge_title])


def test_natural_paragraph_boundary(chunk, passage_embedder):
    c = replace(chunk, document_title="T", text="a" * 60 + "\n\n" + "b" * 140)
    ps = PassageBuilder(
        passage_embedder,
        PassageConfig(max_tokens=100, guard_tokens=8, overlap_tokens=16),
    ).build([c])
    assert ps[0].text == "a" * 60


def test_passage_roundtrip_reopen_dedupe_max_score_and_oversampling(
    tmp_path, chunk, passage_embedder
):
    builder = PassageBuilder(
        passage_embedder,
        PassageConfig(max_tokens=80, guard_tokens=8, overlap_tokens=16),
    )
    a = replace(chunk, text="a" * 500)
    b = replace(chunk, chunk_id="b", text="Other evidence")
    ps = builder.build([a, b])
    n = len(ps)
    path = tmp_path / "passages"
    client = QdrantClient(path=str(path))
    store = QdrantPassageStore(
        client, "passages", contract_for(passage_embedder, builder)
    )
    vectors = np.array(
        [[1.0, 0.0] if p.parent_chunk_id == a.chunk_id else [0.8, 0.6] for p in ps]
    )
    store.upsert_passages(ps, vectors)
    assert list(store.all_passages()) and store.point_count() == n
    client.close()
    client = QdrantClient(path=str(path))
    store = QdrantPassageStore(
        client, "passages", contract_for(passage_embedder, builder)
    )
    try:
        dense = DenseRetriever(
            passage_embedder, store, passage_builder=builder, oversample_factor=1
        )
        results = dense.search("q", 2)
        assert [r.chunk for r in results] == [a, b]
        assert [r.rank for r in results] == [1, 2]
        assert results[0].score == pytest.approx(1)
        assert results[1].score == pytest.approx(0.8)
        assert len(dense.last_candidate_limits) > 1
        assert dense.last_passage_trace[0]["parent_chunk_id"] == a.chunk_id
        assert dense.last_passage_trace[0]["passage_excerpt"] in a.text
    finally:
        client.close()


def test_index_once_idempotence_stale_passages_and_owner(chunk, passage_embedder):
    chunks = [replace(chunk, text="startup " + "x" * 300)]
    builder = PassageBuilder(passage_embedder, PassageConfig(max_tokens=100))
    client = QdrantClient(":memory:")
    store = QdrantPassageStore(
        client, "knowledge_test", contract_for(passage_embedder, builder)
    )
    try:
        dense = DenseRetriever(passage_embedder, store, passage_builder=builder)
        ps = builder.build(chunks)
        for _ in range(2):
            assert dense.index_corpus(chunks, document_ids=[chunk.document_id])[
                "point_count"
            ] == len(ps)
        assert len(passage_embedder.encoded) == 2 * len(ps)
        old_ids = {p.passage_id for p in store.all_passages()}
        changed = [replace(chunks[0], text="new content")]
        result = dense.index_corpus(changed, document_ids=[chunk.document_id])
        assert old_ids.isdisjoint({p.passage_id for p in store.all_passages()})
        assert result["point_count"] == 1
        with pytest.raises(ValueError, match="unrelated"):
            dense.index_corpus(
                [replace(chunk, document_id="other")], document_ids=["other"]
            )
    finally:
        client.close()


def test_oversized_input_rejected_before_embedding_or_writes(chunk, passage_embedder):
    client = QdrantClient(":memory:")
    store = QdrantPassageStore(client, "test", contract_for(passage_embedder))
    try:
        dense = DenseRetriever(passage_embedder, store)
        ps = dense.builder.build([chunk])
        bad = replace(
            ps[0],
            parent=replace(chunk, text="x" * 600),
            text="x" * 600,
            char_start=0,
            char_end=600,
        )
        with pytest.raises(ValueError, match="budget"):
            dense.index_corpus(
                [bad.parent], document_ids=[chunk.document_id], passages=[bad]
            )
        assert not passage_embedder.encoded and store.point_count() == 0
    finally:
        client.close()


def test_canonical_payload_collection_is_not_passage_owned(chunk, passage_embedder):
    from accelerator_rag.storage import QdrantVectorStore

    client = QdrantClient(":memory:")
    try:
        QdrantVectorStore(client, "foreign", 2).upsert_chunks(
            [chunk], np.array([[1.0, 0.0]])
        )
        store = QdrantPassageStore(client, "foreign", contract_for(passage_embedder))
        with pytest.raises(ValueError, match="payload"):
            DenseRetriever(passage_embedder, store).index_corpus(
                [chunk], document_ids=[chunk.document_id]
            )
        assert store.point_count() == 1
    finally:
        client.close()


def test_max_child_score_not_mean_and_continuous_parent_ranks(chunk, passage_embedder):
    a = replace(chunk, text="a" * 180)
    b = replace(chunk, chunk_id="b", text="b")
    builder = PassageBuilder(
        passage_embedder,
        PassageConfig(max_tokens=120, guard_tokens=8, overlap_tokens=16),
    )
    ps = builder.build([a, b])
    scores = []
    for p in ps:
        scores.append(
            0.82
            if p.parent_chunk_id == a.chunk_id and p.passage_ordinal == 0
            else 0.80
            if p.parent_chunk_id == a.chunk_id
            else 0.78
        )
    vectors = np.array([[s, np.sqrt(1 - s * s)] for s in scores])
    client = QdrantClient(":memory:")
    try:
        store = QdrantPassageStore(
            client, "test", contract_for(passage_embedder, builder)
        )
        store.upsert_passages(ps, vectors)
        dense = DenseRetriever(passage_embedder, store, passage_builder=builder)
        results = dense.search("q", 2)
        assert [r.chunk for r in results] == [a, b]
        assert [r.rank for r in results] == [1, 2]
        assert [r.score for r in results] == pytest.approx([0.82, 0.78])
        assert dense.last_passage_trace[0]["passage_ordinal"] == 0
    finally:
        client.close()


def test_config_model_and_payload_integrity_errors(chunk, passage_embedder):
    with pytest.raises(ValueError):
        PassageConfig(overlap_tokens=-1)
    with pytest.raises(ValueError):
        PassageBuilder(passage_embedder, PassageConfig(max_tokens=513))
    with pytest.raises(ValueError, match="payload"):
        QdrantPassageStore.decode({"payload_type": "not-owned"})
    builder = PassageBuilder(passage_embedder)
    with pytest.raises(ValueError, match="duplicate"):
        builder.build([chunk, chunk])


def test_persistent_document_replacement_preserves_other_points(
    tmp_path, chunk, passage_embedder
):
    path = str(tmp_path / "multi")
    a = replace(chunk, document_id="A", chunk_id="A", text="a" * 600)
    b = replace(chunk, document_id="B", chunk_id="B", text="B evidence")

    def open_index(limit=120):
        client = QdrantClient(path=path)
        builder = PassageBuilder(passage_embedder, PassageConfig(max_tokens=limit))
        store = QdrantPassageStore(
            client, "multi", contract_for(passage_embedder, builder)
        )
        return (
            client,
            store,
            DenseRetriever(passage_embedder, store, passage_builder=builder),
        )

    client, store, dense = open_index()
    dense.index_document("A", [a])
    old = {p.passage_id for p in store.all_passages()}
    client.close()
    client, store, dense = open_index()
    dense.index_document("B", [b])
    assert store.document_ids() == {"A", "B"}
    b_before = client.scroll("multi", limit=100, with_vectors=True)[0]
    b_before = [r for r in b_before if r.payload["document_id"] == "B"]
    encoded = len(passage_embedder.encoded)
    new = replace(a, text="new A evidence")
    dense.index_document("A", [new])
    assert passage_embedder.encoded[encoded:] == [document_embedding_text(new)]
    assert old.isdisjoint({p.passage_id for p in store.all_passages()})
    b_after = client.scroll("multi", limit=100, with_vectors=True)[0]
    assert [r for r in b_after if r.payload["document_id"] == "B"] == b_before
    assert store.point_count() == 2
    with pytest.raises(ValueError, match="another document"):
        dense.index_document("A", [replace(b, document_id="A")])
    assert passage_embedder.encoded[encoded:] == [document_embedding_text(new)]
    dense.index_document("A", [new])
    assert store.point_count() == 2
    client.close()
    client, store, dense = open_index()
    try:
        assert {r.chunk for r in dense.search("q", 2)} == {new, b}
        assert store.document_ids() == {"A", "B"}
        assert not any(
            hasattr(store, method)
            for method in [
                "upsert_chunks",
                "replace_document",
                "search",
                "delete_chunks",
            ]
        )
        other = QdrantPassageStore(client, "other_model", dense.contract)
        assert other.point_count() == 0 and store.point_count() == 2
    finally:
        client.close()


def test_model_contract_changes_passages_without_changing_parent(
    chunk, passage_embedder
):
    first = PassageBuilder(passage_embedder).build([chunk])
    passage_embedder.model_name = "another-tokenizer-contract"
    second = PassageBuilder(passage_embedder).build([chunk])
    assert first[0].parent == second[0].parent == chunk
    assert first[0].passage_id != second[0].passage_id
