import numpy as np
import pytest

from accelerator_rag.evidence_pack.dense_local import (
    CachedPassageDenseChannel,
    FusedDenseChannel,
)


def test_parent_score_is_max_over_passages():
    channel = CachedPassageDenseChannel(
        name="e5",
        passage_parents=("p1", "p1", "p2"),
        passage_vectors=np.asarray(
            [[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]], dtype=np.float32
        ),
        query_vectors={"q": np.asarray([1.0, 0.0], dtype=np.float32)},
    )
    hits = channel.search("q", {"p1", "p2"}, top_k=2)
    assert hits[0][0] == "p1"
    assert hits[0][1] == pytest.approx(1.0)
    assert hits[1][0] == "p2"


def test_fused_channel_uses_rrf_and_rejects_unknown_query():
    left = CachedPassageDenseChannel(
        name="e5",
        passage_parents=("a", "b"),
        passage_vectors=np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
        query_vectors={"q": np.asarray([1.0, 0.0], dtype=np.float32)},
    )
    right = CachedPassageDenseChannel(
        name="qwen3",
        passage_parents=("b", "c"),
        passage_vectors=np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32),
        query_vectors={"q": np.asarray([0.0, 1.0], dtype=np.float32)},
    )
    fused = FusedDenseChannel((left, right))
    hits = fused.search("q", {"a", "b", "c"}, top_k=3)
    assert hits[0][0] == "b"
    with pytest.raises(KeyError):
        fused.search("unknown", {"a"}, top_k=1)
