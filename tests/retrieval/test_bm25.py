from dataclasses import replace

import pytest

from accelerator_rag.ingestion import IngestionService
from accelerator_rag.retrieval.bm25 import BM25Retriever, tokenize


def test_technical_tokens():
    assert tokenize("SR:BPM01:X IOC EPICS camonitor") == [
        "sr:bpm01:x",
        "ioc",
        "epics",
        "camonitor",
    ]


def test_ranking_and_non_matches(chunk):
    other = replace(
        chunk, chunk_id="other", text="Beam optics lattice", document_title="Optics"
    )
    retriever = BM25Retriever([other, chunk])
    for query in ["SR:BPM01:X", "IOC", "EPICS", "camonitor"]:
        result = retriever.search(query)[0]
        assert result.chunk == chunk
        assert result.rank == 1 and result.score > 0 and result.retriever == "bm25"
    assert retriever.search("xyzzzz") == []
    assert retriever.search("!!!") == []


@pytest.mark.parametrize("query,k", [("", 1), ("  ", 1), ("IOC", 0), ("IOC", -1)])
def test_invalid_search(chunk, query, k):
    with pytest.raises(ValueError):
        BM25Retriever([chunk]).search(query, top_k=k)


def test_pdf_to_bm25_locates_physical_page(corpus_root, record):
    chunks = IngestionService(corpus_root).ingest_document(record.doc_id)
    result = BM25Retriever(chunks).search("IOC startup installation path", top_k=1)[0]
    assert result.chunk.page_start == result.chunk.page_end == 3
    assert result.chunk.source_path == record.source_path
    assert result.chunk.document_id == record.doc_id
