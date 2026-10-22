from copy import deepcopy
from dataclasses import replace

import pytest

from accelerator_rag.domain.knowledge import RetrievalResult
from accelerator_rag.evaluation.retrieval import (
    EvaluationQuery,
    EvidenceGroup,
    EvidenceTarget,
    judge_results,
    ranking_sha256,
    rejudge,
)


def test_new_alternative_changes_judgment_only_and_keeps_all_groups(chunk):
    q = EvaluationQuery(
        "q",
        "q",
        "en",
        "design",
        True,
        (EvidenceGroup((EvidenceTarget(chunk.document_id, 99, "missing"),)),),
    )
    result = RetrievalResult(1, 0.123456789, chunk, "saved")
    case = judge_results(q, [result])
    case["passage_trace"] = [
        {
            "passage_id": "immutable-child",
            "passage_excerpt": chunk.text,
            "passage_score": result.score,
            "matched_evidence": False,
            "matched_evidence_groups": [],
            "candidate_limits": [10, 20],
        }
    ]
    frozen = deepcopy(case)
    new = replace(
        q,
        evidence_groups=(
            EvidenceGroup(
                (
                    q.evidence_groups[0].alternatives[0],
                    EvidenceTarget(chunk.document_id, chunk.page_start, chunk.text),
                )
            ),
        ),
    )
    report = rejudge([case], [new])
    assert report["metrics"]["Hit@1"] == report["metrics"]["MRR@5"] == 1
    assert report["cases"][0]["first_complete_passage_rank"] == 1
    assert ranking_sha256([case]) == ranking_sha256(report["cases"])
    assert report["cases"][0]["results"][0]["score"] == 0.123456789
    assert report["cases"][0]["passage_trace"] == frozen["passage_trace"]
    assert case == frozen

    old_multi = replace(
        q,
        evidence_groups=(
            *q.evidence_groups,
            EvidenceGroup(
                (
                    EvidenceTarget(
                        chunk.document_id, chunk.page_start, "another required fact"
                    ),
                )
            ),
        ),
    )
    old_case = judge_results(old_multi, [result])
    new_multi = replace(
        new, evidence_groups=(*new.evidence_groups, old_multi.evidence_groups[1])
    )
    partial = rejudge([old_case], [new_multi])
    assert partial["cases"][0]["groups_satisfied_at_k"]["5"] == 1
    assert partial["cases"][0]["first_complete_rank"] is None
    assert partial["metrics"]["Hit@5"] == 0
    assert ranking_sha256([old_case]) == ranking_sha256(partial["cases"])


def test_rejudge_rejects_query_changes_or_invalid_ranks(chunk):
    q = EvaluationQuery(
        "q",
        "q",
        "en",
        "design",
        True,
        (
            EvidenceGroup(
                (EvidenceTarget(chunk.document_id, chunk.page_start, chunk.text),)
            ),
        ),
    )
    case = judge_results(q, [RetrievalResult(1, 0.5, chunk, "saved")])
    with pytest.raises(ValueError, match="metadata changed"):
        rejudge([case], [replace(q, query="changed")])
    with pytest.raises(ValueError, match="unique IDs"):
        rejudge([case, case], [q])
    case["results"][0]["rank"] = 2
    with pytest.raises(ValueError, match="consecutive"):
        rejudge([case], [q])


def test_ranking_digest_includes_scores_parent_payload_and_entire_trace(chunk):
    from dataclasses import asdict

    case = {
        "id": "q",
        "query": "q",
        "results": [asdict(RetrievalResult(1, 0.5, chunk, "saved"))],
        "passage_trace": [{"matched_evidence": False, "passage_id": "child"}],
    }
    digest = ranking_sha256([case])
    for change in ("score", "payload", "trace", "rank"):
        new = deepcopy(case)
        if change == "score":
            new["results"][0]["score"] = 0.50000001
        elif change == "payload":
            new["results"][0]["chunk"]["document_title"] = "other title"
        elif change == "rank":
            new["results"][0]["rank"] = 2
        else:
            new["passage_trace"][0]["matched_evidence"] = True
        assert ranking_sha256([new]) != digest


def test_versioned_audit_rejects_missing_queries_or_relaxed_groups():
    import json
    from pathlib import Path
    from accelerator_rag.evaluation.evidence_audit import validate_revision

    data = Path(__file__).resolve().parents[2] / "data/evaluation"
    old = json.loads((data / "retrieval-baseline-v1.json").read_text())
    new = json.loads((data / "retrieval_baseline.json").read_text())
    audit = json.loads((data / "stage271-evidence-audit.json").read_text())
    assert len(validate_revision(old, new, audit)) == 21
    broken = deepcopy(audit)
    broken["records"].pop()
    with pytest.raises(ValueError, match="every answerable"):
        validate_revision(old, new, broken)
    broken = deepcopy(new)
    broken["queries"][0]["evidence_groups"].pop()
    with pytest.raises(ValueError, match="required groups changed"):
        validate_revision(old, broken, audit)


def test_manual_review_reproduces_frozen_report_and_rejects_other_measurement():
    import json
    from pathlib import Path
    from accelerator_rag.evaluation.manual_review import apply_manual_review
    from accelerator_rag.evaluation.model_comparison import markdown

    root = Path(__file__).resolve().parents[2]
    path = root / "reports/rag-stage-two-seven-embedding-comparison.json"
    measurement = json.loads(path.read_text())
    review = json.loads(
        (root / "data/evaluation/stage27-manual-review.json").read_text()
    )
    assert (
        markdown(apply_manual_review(measurement, review))
        == path.with_suffix(".md").read_text()
    )
    measurement["bm25"]["cases"][0]["results"][0]["score"] += 0.1
    with pytest.raises(ValueError, match="different measurement"):
        apply_manual_review(measurement, review)
