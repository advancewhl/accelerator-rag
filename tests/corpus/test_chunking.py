from dataclasses import replace

import pytest

from accelerator_rag.corpus.chunking import ChunkingConfig, chunk_pdf
from accelerator_rag.corpus.pdf_parser import parse_pdf, PdfTextBlock
from accelerator_rag.ingestion import IngestionError, IngestionService
from accelerator_rag.corpus.cleaning import normalize_text


def test_pdf_to_chunks_preserves_citation_and_blank_pages(corpus_root, record):
    service = IngestionService(corpus_root)
    chunks = service.ingest_document(record.doc_id)
    assert len(chunks) == 2
    assert chunks == service.ingest_document(record.doc_id)
    assert [c.page_start for c in chunks] == [1, 3]
    assert all(c.page_end == c.page_start for c in chunks)
    assert all(
        c.document_id == record.doc_id
        and c.document_title == record.title
        and c.source_path == record.source_path
        and c.text.strip()
        and c.document_version == record.version
        for c in chunks
    )
    assert "SHINE uses" in chunks[0].text and "MySQL stores" in chunks[0].text


def test_oversized_blocks_are_split_and_tiny_tail_balanced(corpus_root, record):
    parsed = parse_pdf(corpus_root / record.source_path, source_path=record.source_path)
    block = PdfTextBlock(0, 0, (0, 0, 100, 100), "x" * 1250)
    page = replace(parsed.pages[0], blocks=[block])
    parsed = replace(parsed, pages=[page])
    chunks = chunk_pdf(parsed, record)
    assert [len(c.text) for c in chunks] == [950, 300]
    assert "".join(c.text for c in chunks) == block.text
    assert len({c.chunk_id for c in chunks}) == 2
    assert chunks == chunk_pdf(parsed, record)
    assert (
        chunks[0].chunk_id
        != chunk_pdf(parsed, record, ChunkingConfig(1000, 200))[0].chunk_id
    )
    assert (
        chunks[0].chunk_id
        != chunk_pdf(parsed, replace(record, version="2"))[0].chunk_id
    )
    changed = replace(
        parsed, pages=[replace(page, blocks=[replace(block, text="y" * 1250)])]
    )
    assert chunks[0].chunk_id != chunk_pdf(changed, record)[0].chunk_id


def test_many_short_blocks_aggregate_and_preserve_all_content(corpus_root, record):
    parsed = parse_pdf(corpus_root / record.source_path, source_path=record.source_path)
    blocks = [
        PdfTextBlock(i, 0, (0, 0, 100, 100), f"Block {i}. " * 12) for i in range(30)
    ]
    parsed = replace(parsed, pages=[replace(parsed.pages[0], blocks=blocks)])
    chunks = chunk_pdf(parsed, record, ChunkingConfig(400, 100))
    assert 1 < len(chunks) < len(blocks)
    assert all(100 <= len(c.text) <= 400 for c in chunks)
    assert " ".join(" ".join(c.text.split()) for c in chunks) == " ".join(
        " ".join(b.text.split()) for b in blocks
    )


def test_normalization():
    assert (
        normalize_text("  EPICS   IOC\nhandles\n\n\nPV  ") == "EPICS IOC handles\n\nPV"
    )
    assert (
        normalize_text("infor-\nmation", vocabulary=frozenset({"information"}))
        == "information"
    )
    assert normalize_text("SR:BPM01:X\ncamonitor") == "SR:BPM01:X camonitor"
    assert normalize_text(" \n \n") == ""


@pytest.mark.parametrize("maximum,minimum", [(0, 1), (100, 0), (100, 80)])
def test_invalid_chunk_configuration(maximum, minimum):
    with pytest.raises(ValueError):
        ChunkingConfig(maximum, minimum)


def test_ingestion_rejects_unknown_and_missing_sources(corpus_root, record):
    service = IngestionService(corpus_root)
    with pytest.raises(ValueError, match="not registered"):
        service.ingest_document("missing")
    (corpus_root / record.source_path).unlink()
    with pytest.raises(IngestionError, match="document_id=.*source="):
        service.ingest_document(record.doc_id)


def test_source_cannot_escape_through_symlink(corpus_root, record, tmp_path):
    source = corpus_root / record.source_path
    source.unlink()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"not opened")
    source.symlink_to(outside)
    with pytest.raises(IngestionError, match="escapes"):
        IngestionService(corpus_root).ingest_document(record.doc_id)


def test_parsed_source_must_match_record(corpus_root, record):
    parsed = parse_pdf(corpus_root / record.source_path)
    with pytest.raises(ValueError, match="source_path"):
        chunk_pdf(parsed, record)
