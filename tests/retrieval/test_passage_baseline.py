from argparse import Namespace
from pathlib import Path
import json
from unittest.mock import patch
from accelerator_rag.retrieval.corpus_baseline import run as stage25
from accelerator_rag.retrieval.passage_baseline import run


def test_full_ab_fixture_reuses_history_and_freezes_controls(
    corpus_root, record, passage_embedder
):
    import pymupdf

    with pymupdf.open(corpus_root / record.source_path) as pdf:
        pdf.new_page().insert_text((72, 72), "THANK YOU")
        pdf.saveIncr()
    passage_embedder.dimension = 2
    passage_embedder.QUERY_TEMPLATE = "为这个句子生成表示以用于检索相关文章：{query}"
    path = corpus_root / "data/evaluation/retrieval_baseline.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "judgment_revision": "evidence-contract-v1",
                "queries": [
                    {
                        "id": "q",
                        "query": "IOC startup",
                        "language": "en",
                        "category": "ioc",
                        "answerable": True,
                        "judgment_mode": "all",
                        "judgment_note": "fixture",
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
        )
    )
    args = Namespace(
        project_root=corpus_root,
        qdrant_path=Path("tmp/stage25"),
        collection="knowledge_stage25_fixture",
        batch_size=2,
        model="fixture",
        many_chunks_per_page=10,
        generated_on="2026-10-19",
        queries=path,
    )
    with patch(
        "accelerator_rag.retrieval.corpus_baseline.EmbeddingModel",
        return_value=passage_embedder,
    ):
        stage25(args)
    history = corpus_root / "reports/rag-stage-two-five-retrieval-baseline.json"
    before = history.read_bytes()
    args = Namespace(
        project_root=corpus_root,
        qdrant_path=Path("tmp/stage26"),
        collection="knowledge_stage26_fixture",
        batch_size=2,
        guard_tokens=16,
        overlap_tokens=32,
        oversample_factor=4,
    )
    with patch(
        "accelerator_rag.retrieval.passage_baseline.EmbeddingModel",
        return_value=passage_embedder,
    ):
        report = run(args)
    assert report["controls"]["bm25_metrics_rankings_scores_identical"]
    assert report["controls"]["live_stage25_dense_metrics_rankings_match_history"]
    assert report["passage_statistics"]["passages_exceeding_limit"] == 0
    assert report["index"]["point_count"] == report["index"]["unique_parent_count"] == 2
    assert history.read_bytes() == before
    assert (
        corpus_root / "reports/rag-stage-two-six-dense-passage.md"
    ).stat().st_size > 0
    # Fixture project has no src tree; record the actual installed implementation.
    from hashlib import sha256

    installed = Path(__file__).resolve().parents[2] / "src/accelerator_rag"
    history26 = corpus_root / "reports/rag-stage-two-six-dense-passage.json"
    fixture_report = json.loads(history26.read_text())
    fixture_report["metadata"]["code_sha256"] = {
        "src/accelerator_rag/" + p.relative_to(installed).as_posix(): sha256(
            p.read_bytes()
        ).hexdigest()
        for p in installed.rglob("*.py")
    }
    history26.write_text(json.dumps(fixture_report))
    # Run the new comparison end to end against the verified historical control.
    from accelerator_rag.retrieval.model_baseline import run as compare, CONTROL

    args = Namespace(
        project_root=corpus_root, batch_size=2, threads=2, models=[CONTROL]
    )
    with patch(
        "accelerator_rag.retrieval.model_baseline.EmbeddingModel",
        return_value=passage_embedder,
    ):
        comparison = compare(args)
        encoded = len(passage_embedder.encoded)
        repeated = compare(args)
    assert (
        comparison["models"][CONTROL]["evaluation"]["metrics"]
        == report["dense_b"]["metrics"]
    )
    assert len(passage_embedder.encoded) == encoded
    assert repeated["models"][CONTROL]["vectors_reused"]
    assert (
        corpus_root / "reports/rag-stage-two-seven-embedding-comparison.md"
    ).stat().st_size > 0

    def load_candidate(name, **kwargs):
        if name != CONTROL:
            raise OSError("incomplete local weights")
        return passage_embedder

    args.models = ["BAAI/bge-base-zh-v1.5", CONTROL]
    with patch(
        "accelerator_rag.retrieval.model_baseline.EmbeddingModel",
        side_effect=load_candidate,
    ):
        partial = compare(args)
    assert list(partial["models"]) == [CONTROL]
    assert partial["excluded"][0]["reason"] == "incomplete local weights"
