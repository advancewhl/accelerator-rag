import json
import os
from pathlib import Path
import subprocess
import sys


def test_cli_returns_inspectable_citations(corpus_root, record):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "accelerator_rag.retrieval.cli",
            "--project-root",
            str(corpus_root),
            "--document-id",
            record.doc_id,
            "--query",
            "IOC startup",
            "--top-k",
            "1",
        ],
        env={**os.environ, "PYTHONPATH": str(root / "src")},
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["chunk_count"] == 2
    hit = payload["results"][0]
    assert hit["rank"] == 1 and hit["score"] > 0 and hit["retriever"] == "bm25"
    chunk = hit["chunk"]
    assert chunk["document_id"] == record.doc_id
    assert chunk["document_title"] == record.title
    assert chunk["page_start"] == chunk["page_end"] == 3
    assert chunk["chunk_id"] and "IOC startup" in chunk["text"]
    assert chunk["source_path"] == record.source_path
