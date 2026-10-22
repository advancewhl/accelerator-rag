from dataclasses import replace
from accelerator_rag.evaluation.retrieval import (
    EvaluationQuery,
    EvidenceTarget,
    EvidenceGroup,
)
from accelerator_rag.evaluation.passage_comparison import truncation_diagnosis


def test_real_token_prefix_evidence_before_crosses_after(chunk, passage_embedder):
    passage_embedder.max_seq_length = 16
    c = replace(chunk, document_title="T", text="abcdeFGHIJ12345KLMNOP")
    queries = []
    for ident, text in [("before", "abcde"), ("cross", "12345"), ("after", "KLMNOP")]:
        queries.append(
            EvaluationQuery(
                ident,
                ident,
                "en",
                "epics",
                True,
                (EvidenceGroup((EvidenceTarget(c.document_id, c.page_start, text),)),),
            )
        )
    old = {"cases": [{"id": q.id, "first_complete_rank": None} for q in queries]}
    r = truncation_diagnosis(passage_embedder, queries, [c], old)
    assert r["position_counts"] == {
        "fully_before_limit": 1,
        "crosses_limit": 1,
        "fully_after_limit": 1,
    }
    assert r["failures_with_truncating_relevant_parent"] == 3
    assert r["failures_with_required_group_not_fully_visible"] == 2
