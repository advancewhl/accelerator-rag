from dataclasses import replace
import json
import pytest
from accelerator_rag.domain.knowledge import RetrievalResult
from accelerator_rag.evaluation.retrieval import (
    EvaluationQuery,
    EvidenceTarget,
    EvidenceGroup,
    evaluate,
    load_queries,
    normalize_evidence,
)


class Results:
    def __init__(self, rows):
        self.rows = rows

    def search(self, query, *, top_k):
        return self.rows[query][:top_k]


def group(chunk, excerpt, page=None):
    return EvidenceGroup(
        (EvidenceTarget(chunk.document_id, page or chunk.page_start, excerpt),)
    )


def test_all_groups_joint_chunks_first_complete_rank(chunk):
    a = replace(chunk, text="RF frequency 1300 MHz")
    b = replace(chunk, text="Nominal energy 20 GeV", chunk_id="b")
    wrong = replace(chunk, text="wrong evidence on correct page", chunk_id="wrong")
    groups = (group(a, "1300 MHz"), group(b, "20 GeV"))
    q = EvaluationQuery("q", "q", "en", "accelerator_design", True, groups)
    rs = [RetrievalResult(i, 0.8, c, "test") for i, c in enumerate([wrong, a, b], 1)]
    report = evaluate(Results({"q": rs}), [q])
    m = report["metrics"]
    assert m["Hit@1"] == 0 and m["Hit@3"] == m["Hit@5"] == 1
    assert m["MRR@5"] == pytest.approx(1 / 3)
    case = report["cases"][0]
    assert case["first_complete_rank"] == 3
    assert case["groups_satisfied_at_k"] == {"1": 0, "3": 2, "5": 2}
    assert not case["results"][0]["judged_relevant"]


def test_any_alternative_and_no_answer_excluded(chunk):
    g = EvidenceGroup(
        (
            EvidenceTarget("wrong", 3, "missing"),
            EvidenceTarget(chunk.document_id, 3, "IOC"),
        )
    )
    q = EvaluationQuery(
        "q",
        "q",
        "zh",
        "ioc",
        True,
        (g, group(chunk, "not in text")),
        judgment_mode="any",
    )
    no = EvaluationQuery("n", "n", "en", "ioc", False, (), negative_type="hard_domain")
    hit = RetrievalResult(1, 0.5, chunk, "test")
    r = evaluate(Results({"q": [hit], "n": [hit]}), [q, no])
    assert r["metrics"]["count"] == 1 and r["metrics"]["Hit@1"] == 1
    assert r["cases"][1]["first_complete_rank"] is None
    assert r["top1_scores"]["hard_domain"]["query_count"] == 1
    assert r["by_query_language"]["zh"]["count"] == 1


def test_page_mismatch(chunk):
    q = EvaluationQuery("q", "q", "en", "ioc", True, (group(chunk, "IOC", 99),))
    r = evaluate(Results({"q": [RetrievalResult(1, 0.5, chunk, "test")]}), [q])
    assert r["metrics"]["Hit@5"] == r["metrics"]["MRR@5"] == 0


def dataset(record):
    return {
        "schema_version": 2,
        "judgment_revision": "test",
        "queries": [
            {
                "id": "q",
                "query": "startup?",
                "language": "en",
                "category": "ioc",
                "answerable": True,
                "judgment_mode": "all",
                "judgment_note": "raw inspected",
                "evidence_groups": [
                    {
                        "alternatives": [
                            {
                                "document_id": record.doc_id,
                                "page": 3,
                                "excerpt": "IOC startup submits installation path",
                            }
                        ]
                    }
                ],
            }
        ],
    }


def test_loader_final_eligible_invariant(corpus_root, record):
    from accelerator_rag.ingestion import IngestionService

    docs = IngestionService(corpus_root).ingest_all_registered_pdfs()
    path = corpus_root / "queries.json"
    data = dataset(record)
    path.write_text(json.dumps(data))
    assert len(load_queries(path, docs)) == 1
    with pytest.raises(ValueError, match="not retrievable after cleaning/chunking.*q"):
        load_queries(path, docs, eligible_chunks=[])
    data["queries"][0]["evidence_groups"][0]["alternatives"][0]["excerpt"] = (
        "fabricated source"
    )
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="evidence not found"):
        load_queries(path, docs)


@pytest.mark.parametrize(
    "change", ["empty_group", "invalid_negative", "invalid_mode", "answerable_negative"]
)
def test_invalid_contract(corpus_root, record, change):
    from accelerator_rag.ingestion import IngestionService

    d = dataset(record)
    q = d["queries"][0]
    if change == "empty_group":
        q["evidence_groups"] = [{"alternatives": []}]
    elif change == "invalid_negative":
        q.update(answerable=False, evidence_groups=[], negative_type="random")
    elif change == "answerable_negative":
        q["negative_type"] = "hard_domain"
    else:
        q["judgment_mode"] = "sometimes"
    p = corpus_root / "q.json"
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        load_queries(p, IngestionService(corpus_root).ingest_all_registered_pdfs())


def test_normalization_deterministic():
    assert normalize_evidence("温度\n为 8 GeV") == normalize_evidence("温度为8 GeV")
    assert normalize_evidence("hun-\ndreds") == normalize_evidence("hundreds")
    assert normalize_evidence("real-time") != normalize_evidence("realtime")


def test_bilingual_sources_and_mixed_relationship(corpus_root, record):
    from accelerator_rag.ingestion import IngestionService

    docs = IngestionService(corpus_root).ingest_all_registered_pdfs()
    data = dataset(record)
    data["queries"][0]["language"] = "zh"
    path = corpus_root / "q.json"
    path.write_text(json.dumps(data))
    assert load_queries(path, docs)[0].language_relation == "cross_language"
    docs[0] = replace(docs[0], record=replace(docs[0].record, language="zh-en"))
    assert load_queries(path, docs)[0].language_relation == "same_language"


def test_no_answer_only_metrics_have_empty_denominator(chunk):
    q = EvaluationQuery("n", "n", "en", "ioc", False, (), negative_type="obvious")
    report = evaluate(Results({"n": [RetrievalResult(1, 0.9, chunk, "test")]}), [q])
    assert report["metrics"]["count"] == 0
    assert report["metrics"]["Hit@5"] is None and report["metrics"]["MRR@5"] is None
    assert report["top1_scores"]["obvious"]["query_count"] == 1


def test_all_can_share_one_chunk_and_completion_at_five(chunk):
    groups = (group(chunk, "EPICS"), group(chunk, "IOC"))
    q = EvaluationQuery("q", "q", "en", "ioc", True, groups)
    wrong = replace(chunk, text="wrong chunk")
    rs = [
        RetrievalResult(i, 0.5, wrong if i < 5 else chunk, "test") for i in range(1, 6)
    ]
    r = evaluate(Results({"q": rs}), [q])
    assert r["metrics"]["Hit@1"] == r["metrics"]["Hit@3"] == 0
    assert r["metrics"]["Hit@5"] == 1 and r["metrics"]["MRR@5"] == 0.2


def test_raw_exists_but_chunk_text_removed_fails(corpus_root, record):
    from accelerator_rag.ingestion import IngestionService

    docs = IngestionService(corpus_root).ingest_all_registered_pdfs()
    doc = docs[0]
    docs[0] = replace(
        doc, chunks=[replace(c, text="unrelated surviving body") for c in doc.chunks]
    )
    path = corpus_root / "queries.json"
    path.write_text(json.dumps(dataset(record)))
    with pytest.raises(ValueError, match="not retrievable after cleaning/chunking"):
        load_queries(path, docs)


@pytest.mark.parametrize("label", ["obvious", "hard_domain"])
def test_negative_labels_accepted(corpus_root, record, label):
    from accelerator_rag.ingestion import IngestionService

    data = dataset(record)
    data["queries"][0].update(answerable=False, evidence_groups=[], negative_type=label)
    path = corpus_root / "queries.json"
    path.write_text(json.dumps(data))
    assert (
        load_queries(path, IngestionService(corpus_root).ingest_all_registered_pdfs())[
            0
        ].negative_type
        == label
    )


def test_historical_comparison_separates_contract_regression(chunk):
    from dataclasses import asdict
    from accelerator_rag.evaluation.comparison import compare_stage_two

    query = EvaluationQuery(
        "q", "q", "en", "ioc", True, (group(chunk, "IOC"), group(chunk, "missing fact"))
    )
    old = {
        "metrics": {"Recall@1": 1, "Recall@3": 1, "Recall@5": 1, "MRR": 1},
        "cases": [
            {
                "id": "q",
                "query": "q",
                "answerable": True,
                "first_relevant_rank": 1,
                "results": [asdict(RetrievalResult(1, 0.8, chunk, "test"))],
            }
        ],
    }
    history = {"index": {"chunk_count": 1}, "bm25": old, "dense": old}
    current_result = evaluate(
        Results({"q": [RetrievalResult(1, 0.8, chunk, "test")]}), [query]
    )
    current = {
        "index": {"point_count": 1},
        "retrieval_eligibility": {"total_chunks": 1},
        "bm25": current_result,
        "dense": current_result,
    }
    compared = compare_stage_two(history, current, [query])
    assert compared["bm25"]["contract_change_on_same_rankings"]["hit_to_fail"] == ["q"]
    assert compared["bm25"]["ranking_change_under_same_contract"]["hit_to_fail"] == []
