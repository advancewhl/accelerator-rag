from dataclasses import asdict, replace
import json
from unittest.mock import patch

import pymupdf
import pytest

from accelerator_rag.ingestion import IngestionError, IngestionService


def add_second_pdf(corpus_root, record):
    second = replace(
        record,
        doc_id="cryo-system",
        title="Helium controls",
        source_path="data/l0_raw/helium.pdf",
        topic="cryogenics",
    )
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text(
            (72, 72), "Helium cryogenic compressor and refrigerator controls."
        )
        doc.save(corpus_root / second.source_path)
    registry = corpus_root / "data/documents/registry.json"
    non_pdf = replace(
        record,
        doc_id="slides",
        source_path="data/l0_raw/slides.pptx",
        document_type="pptx",
    )
    registry.write_text(json.dumps([asdict(record), asdict(second), asdict(non_pdf)]))
    (corpus_root / "data/l0_raw/slides.pptx").write_bytes(b"not parsed")
    (corpus_root / "data/l0_raw/unregistered.docx").write_bytes(b"not parsed")
    return second


def test_ingests_multiple_pdfs_once_and_ignores_non_pdf(corpus_root, record):
    from accelerator_rag.ingestion import parse_pdf

    second = add_second_pdf(corpus_root, record)
    with patch("accelerator_rag.ingestion.parse_pdf", wraps=parse_pdf) as parser:
        documents = IngestionService(corpus_root).ingest_all_registered_pdfs()
    assert parser.call_count == 2
    assert [d.record.doc_id for d in documents] == [record.doc_id, second.doc_id]
    chunks = [c for d in documents for c in d.chunks]
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert chunks == [
        c
        for d in IngestionService(corpus_root).ingest_all_registered_pdfs()
        for c in d.chunks
    ]


def test_failed_pdf_has_source_context_and_batch_is_fail_fast(corpus_root, record):
    second = add_second_pdf(corpus_root, record)
    (corpus_root / record.source_path).write_bytes(b"corrupt PDF")
    from accelerator_rag.ingestion import parse_pdf

    with patch("accelerator_rag.ingestion.parse_pdf", wraps=parse_pdf) as parser:
        with pytest.raises(
            IngestionError,
            match=f"document_id={record.doc_id}, source={record.source_path}",
        ):
            IngestionService(corpus_root).ingest_all_registered_pdfs()
    assert parser.call_count == 1
    assert (corpus_root / second.source_path).is_file()
