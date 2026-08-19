from accelerator_rag.evaluation.baseline import (
    decide_winner,
    find_best_rank,
    EvaluationCase,
    validate_evaluation_cases,
)
from accelerator_rag.retrieval.semantic_search import (
    DocumentChunk,
    SearchResult,
)

import pytest

def build_result(
    chunk_id: str,
    rank: int,
) -> SearchResult:
    chunk = DocumentChunk(
        id=chunk_id,
        title=chunk_id,
        text="test",
        metadata={},
    )

    return SearchResult(
        rank=rank,
        score=1.0,
        chunk=chunk,
    )


def test_find_best_rank_returns_first_relevant_result() -> None:
    results = [
        build_result("wrong-a", 1),
        build_result("correct-b", 2),
        build_result("correct-c", 3),
    ]

    rank = find_best_rank(
        results=results,
        expected_ids=[
            "correct-b",
            "correct-c",
        ],
    )

    assert rank == 2


def test_find_best_rank_returns_none_when_not_found() -> None:
    results = [
        build_result("wrong-a", 1),
        build_result("wrong-b", 2),
    ]

    rank = find_best_rank(
        results=results,
        expected_ids=["correct"],
    )

    assert rank is None


def test_decide_winner_prefers_lower_rank() -> None:
    assert decide_winner(1, 2) == "Dense"
    assert decide_winner(3, 1) == "BM25"


def test_decide_winner_handles_tie() -> None:
    assert decide_winner(1, 1) == "并列"


def test_decide_winner_handles_missing_results() -> None:
    assert decide_winner(None, 2) == "BM25"
    assert decide_winner(2, None) == "Dense"
    assert (
        decide_winner(None, None)
        == "双方均未命中"
    )

def test_validate_evaluation_cases_accepts_valid_ground_truth() -> None:
    chunks = [
        DocumentChunk(
            id="chunk-a",
            title="A",
            text="test",
            metadata={},
        )
    ]

    cases = [
        EvaluationCase(
            id="q001",
            question="test?",
            expected_ids=("chunk-a",),
            category="test",
            scored=True,
        )
    ]

    validate_evaluation_cases(
        cases=cases,
        chunks=chunks,
    )


def test_validate_evaluation_cases_rejects_missing_ground_truth() -> None:
    chunks = [
        DocumentChunk(
            id="chunk-a",
            title="A",
            text="test",
            metadata={},
        )
    ]

    cases = [
        EvaluationCase(
            id="q001",
            question="test?",
            expected_ids=("missing-chunk",),
            category="test",
            scored=True,
        )
    ]

    with pytest.raises(
        ValueError,
        match="missing-chunk",
    ):
        validate_evaluation_cases(
            cases=cases,
            chunks=chunks,
        )