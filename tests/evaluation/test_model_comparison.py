import pytest
from accelerator_rag.evaluation.model_comparison import complementarity, pairwise


def report(ranks, score):
    return {
        "cases": [
            {
                "id": q,
                "answerable": True,
                "first_complete_rank": rank,
                "top1_score": score,
            }
            for q, rank in ranks.items()
        ]
    }


def test_complementarity_and_rank_comparison_ignore_raw_cosine():
    a = report({"both": 2, "bm": 1, "dense": None, "miss": None}, 0.99)
    b = report({"both": 1, "bm": None, "dense": 5, "miss": None}, 0.1)
    result = complementarity(a, b)
    assert result["counts"] == {
        "both_hit": 1,
        "bm25_only": 1,
        "dense_only": 1,
        "both_miss": 1,
    }
    assert result["query_ids"]["dense_only"] == ["dense"]
    comparison = pairwise({"A": a, "B": b})[0]
    assert comparison["counts"] == {"a_wins": 1, "b_wins": 2, "same": 1}
    assert comparison["query_ids"]["same"] == ["miss"]
    assert (
        comparison
        == pairwise(
            {"A": report({"both": 2, "bm": 1, "dense": None, "miss": None}, -1), "B": b}
        )[0]
    )
    with pytest.raises(ValueError, match="query sets"):
        complementarity(a, report({"other": 1}, 0))
