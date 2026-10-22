from argparse import Namespace
import json
from pathlib import Path
from unittest.mock import patch

from accelerator_rag.retrieval.corpus_baseline import run


def test_batch_entry_writes_reports_and_global_index(
    corpus_root, record, fake_embedder
):
    import pymupdf

    pdf_path = corpus_root / record.source_path
    with pymupdf.open(pdf_path) as pdf:
        pdf.new_page().insert_text((72, 72), "THANK YOU")
        pdf.saveIncr()
    fake_embedder.dimension = 2
    fake_embedder.QUERY_TEMPLATE = "instruction:{query}"
    query_path = corpus_root / "queries.json"
    data = {
        "schema_version": 2,
        "judgment_revision": "fixture",
        "queries": [
            {
                "id": "startup",
                "query": "IOC startup",
                "language": "en",
                "category": "ioc",
                "answerable": True,
                "judgment_mode": "all",
                "judgment_note": "fixture raw",
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
            },
            {
                "id": "no",
                "query": "nonexistenttopic",
                "language": "en",
                "category": "none",
                "answerable": False,
                "judgment_mode": "all",
                "judgment_note": "fixture negative",
                "negative_type": "obvious",
                "evidence_groups": [],
            },
        ],
    }
    query_path.write_text(json.dumps(data))
    fake_embedder.max_seq_length = 512
    fake_embedder.audit_inputs = lambda texts: [
        {
            "token_count": 20,
            "would_truncate": False,
            "truncated_token_count": 0,
            "truncation_ratio": 0,
        }
        for _ in texts
    ]
    args = Namespace(
        project_root=corpus_root,
        qdrant_path=Path("tmp/index"),
        collection="knowledge_stage25_fixture",
        batch_size=1,
        model="local-fixture",
        many_chunks_per_page=10,
        generated_on="2026-10-19",
        queries=query_path,
    )
    with patch(
        "accelerator_rag.retrieval.corpus_baseline.EmbeddingModel",
        return_value=fake_embedder,
    ):
        report = run(args)
    assert report["index"]["point_count"] == report["index"]["unique_chunk_count"] == 2
    assert report["retrieval_eligibility"]["total_chunks"] == 3
    assert report["retrieval_eligibility"]["ineligible_chunks"] == 1
    assert all(
        "THANK YOU" not in r["chunk"]["text"]
        for name in ("bm25", "dense")
        for c in report[name]["cases"]
        for r in c["results"]
    )
    assert report["bm25"]["metrics"]["Hit@1"] == 1
    assert report["dense"]["metrics"]["Hit@1"] == 1
    for name in ["corpus-audit", "retrieval-baseline"]:
        for extension in ["json", "md"]:
            assert (
                corpus_root / f"reports/rag-stage-two-five-{name}.{extension}"
            ).stat().st_size > 0
