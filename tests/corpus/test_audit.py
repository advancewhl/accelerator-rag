from dataclasses import replace

import pytest

from accelerator_rag.corpus.audit import AuditConfig, audit_corpus, distribution
from accelerator_rag.corpus.chunking import ChunkingConfig
from accelerator_rag.corpus.pdf_parser import ParsedPdfDocument, PdfPage
from accelerator_rag.ingestion import IngestedDocument


def make_documents(record, chunk):
    first = replace(
        chunk,
        chunk_id="first",
        page_start=1,
        page_end=1,
        text=("information in-formation \ufffd\x00\ue001" + "x" * 50)[:50],
    )
    second = replace(
        chunk,
        chunk_id="second",
        text=("ISBN:123\ncopyright\nAB12\n123\n" + "x" * 100)[:100],
    )
    third = replace(chunk, chunk_id="third", text="x" * 150)
    other_record = replace(record, doc_id="cryo", source_path="data/l0_raw/cryo.pdf")
    other = replace(
        chunk,
        chunk_id="fourth",
        document_id="cryo",
        source_path=other_record.source_path,
        text="x" * 200,
        page_start=1,
        page_end=1,
    )
    pages = [
        PdfPage(1, 600, 800, "first", 5, [], 0, ["possible_two_column"]),
        PdfPage(2, 600, 800, "", 0, [], 1, ["empty_text", "possible_scanned_page"]),
        PdfPage(3, 600, 800, "third", 5, [], 0, ["private_use_characters"]),
    ]
    return [
        IngestedDocument(
            record,
            ParsedPdfDocument(record.source_path, "source.pdf", 3, {}, pages),
            [first, second, third],
        ),
        IngestedDocument(
            other_record,
            ParsedPdfDocument(
                other_record.source_path,
                "cryo.pdf",
                1,
                {},
                [PdfPage(1, 600, 800, "cryo", 4, [], 0)],
            ),
            [other],
        ),
    ]


def test_statistics_warning_quality_and_attribution(record, chunk):
    docs = make_documents(record, chunk)
    audit = audit_corpus(
        docs,
        2,
        ChunkingConfig(150, 50),
        generated_on="2026-10-19",
        config=AuditConfig(many_chunks_per_page=1),
    ).to_dict()
    assert audit["overview"] == {
        "registered_documents": 2,
        "successfully_ingested_documents": 2,
        "total_pages": 4,
        "total_chunks": 4,
        "total_chunk_chars": 500,
    }
    lengths = audit["chunk_lengths"]
    assert lengths["min"] == 50 and lengths["max"] == 200 and lengths["mean"] == 125
    assert (
        lengths["p10"] == 65
        and lengths["median"] == 125
        and lengths["p95"] == pytest.approx(192.5)
    )
    assert lengths["very_short_chunks"] == 1 and lengths["very_long_chunks"] == 1
    assert audit["parser_warnings"]["possible_scanned_page"] == 1
    assert audit["documents"][0]["warning_counts"]["empty_text"] == 1
    assert audit["page_distribution"]["pages_without_chunks"][0]["page"] == 2
    assert audit["page_distribution"]["pages_with_very_many_chunks"][0]["page"] == 3
    assert audit["page_distribution"]["chunks_per_page"]["min"] == 0
    for key in ["replacement", "null", "private_use"]:
        assert audit["quality"][key]["occurrences"] == 1
        assert audit["quality"][key]["examples"][0]["chunk_id"] == "first"
        assert audit["quality"][key]["per_document"] == {record.doc_id: 1}
    hyphen = audit["quality"]["suspicious_hyphenation"]
    assert hyphen["count"] == 1 and hyphen["top_examples"][0]["token"] == "in-formation"
    assert hyphen["examples"][0]["page_start"] == 1
    assert audit["quality"]["publication_identifiers"]["occurrences"] == 1
    assert audit["quality"]["isolated_page_numbers"]["occurrences"] == 1
    assert audit["quality"]["running_publication_codes"]["occurrences"] == 1
    assert audit["identity"]["all_unique"]
    assert audit["documents"][1]["chunk_count"] == 1


def test_duplicate_chunk_ids_fail(record, chunk):
    docs = make_documents(record, chunk)
    docs[1].chunks.append(docs[0].chunks[0])
    with pytest.raises(ValueError, match="duplicate corpus chunk"):
        audit_corpus(docs, 2, ChunkingConfig(), generated_on="2026-10-19")


def test_distribution_empty_and_linear():
    assert distribution([]) == {"count": 0}
    assert distribution([0, 10])["p25"] == pytest.approx(2.5)


def test_audit_reports_have_required_sections_without_testing_style(record, chunk):
    from accelerator_rag.evaluation.reporting import audit_markdown

    audit = audit_corpus(
        make_documents(record, chunk), 2, ChunkingConfig(), generated_on="2026-10-19"
    ).to_dict()
    rendered = audit_markdown(audit)
    assert "SHINE controls" not in rendered or record.doc_id in rendered
    assert record.doc_id in rendered and "replacement" in rendered
    assert "\x00" not in rendered and "\\u0000" in rendered
