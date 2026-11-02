"""Markdown ingestion: parser, chunk identity, service dispatch, serving."""

from contextlib import closing
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from accelerator_rag.corpus.chunking import (
    CHUNKING_ALGORITHM,
    MARKDOWN_CHUNKING_ALGORITHM,
    ChunkingConfig,
    chunk_markdown,
)
from accelerator_rag.corpus.markdown_parser import (
    parse_markdown,
    split_front_matter,
    split_sections,
)
from accelerator_rag.corpus.registry import DocumentRecord
from accelerator_rag.ingestion import IngestionService
from accelerator_rag.rag.api import create_app
from accelerator_rag.rag.catalog import DocumentCatalog

MD = """---
applicable_system_version: "waveform@dc50e08"
owner: "未指派"
---

# 测试手册

前言一段。

## 0. 结论先行

结论正文。
```python
# 这不是标题
print(1)
```

## 1. 参数

| 项 | 值 |
| --- | --- |
| min | 1.0 |
"""


def test_split_front_matter_keeps_raw_block_as_evidence():
    metadata, body = split_front_matter(MD)
    assert metadata["applicable_system_version"] == "waveform@dc50e08"
    assert metadata["owner"] == "未指派"
    assert body.startswith("---\napplicable_system_version")
    assert "# 测试手册" in body


def test_split_sections_ignores_headings_inside_fences():
    _, body = split_front_matter(MD)
    sections = split_sections(body)
    assert len(sections) == 3
    assert sections[0].startswith("---")
    assert sections[1].startswith("## 0. 结论先行")
    # A "# " line inside the fenced block must not start a new section.
    assert "print(1)" in sections[1]
    assert sections[2].startswith("## 1. 参数")


def test_parse_markdown_numbers_sections_from_one(tmp_path):
    path = tmp_path / "manual.md"
    path.write_text(MD, encoding="utf-8")
    parsed = parse_markdown(path, source_path="data/l0_raw/kb/manual.md")
    assert parsed.page_count == 3
    assert [p.page_number for p in parsed.pages] == [1, 2, 3]
    assert parsed.metadata["format"] == "markdown"
    assert parsed.metadata["section_split_level"] == 2
    assert parsed.source_path == "data/l0_raw/kb/manual.md"


def test_parse_markdown_rejects_non_markdown(tmp_path):
    path = tmp_path / "manual.txt"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="Expected a Markdown file"):
        parse_markdown(path)


def records(md_path):
    return DocumentRecord(
        doc_id="waveform-manual",
        title="测试手册",
        source_path=md_path,
        category="beam_diagnostics",
        topic="waveform",
        document_type="md",
        language="zh",
        version="waveform@dc50e08",
        status="active",
    )


def test_markdown_chunks_are_stable_and_section_scoped(tmp_path):
    path = tmp_path / "manual.md"
    path.write_text(MD, encoding="utf-8")
    record = records("data/l0_raw/kb/manual.md")
    parsed = parse_markdown(path, source_path=record.source_path)
    chunks = chunk_markdown(parsed, record)
    assert chunks and chunks == chunk_markdown(parsed, record)
    assert all(c.page_start == c.page_end for c in chunks)
    assert {c.page_start for c in chunks} <= {1, 2, 3}
    assert all(c.chunk_id.startswith("waveform-manual:") for c in chunks)
    assert all(len(c.text) <= ChunkingConfig().max_chars for c in chunks)
    assert MARKDOWN_CHUNKING_ALGORITHM != CHUNKING_ALGORITHM


def test_ingestion_service_dispatches_markdown(tmp_path):
    root = tmp_path / "project"
    raw = root / "data/l0_raw/kb"
    raw.mkdir(parents=True)
    (raw / "manual.md").write_text(MD, encoding="utf-8")
    registry = [
        {
            "doc_id": "waveform-manual",
            "title": "测试手册",
            "source_path": "data/l0_raw/kb/manual.md",
            "category": "beam_diagnostics",
            "topic": "waveform",
            "document_type": "md",
            "language": "zh",
            "version": "waveform@dc50e08",
            "status": "active",
        },
        {
            "doc_id": "inventory-only",
            "title": "未支持类型",
            "source_path": "data/l0_raw/kb/notes.txt",
            "category": "beam_diagnostics",
            "topic": "waveform",
            "document_type": "txt",
            "language": "zh",
            "version": "v1",
            "status": "active",
        },
    ]
    (raw / "notes.txt").write_text("plain text", encoding="utf-8")
    path = root / "data/documents/registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")

    service = IngestionService(root)
    chunks = service.ingest_document("waveform-manual")
    assert chunks and chunks[0].document_id == "waveform-manual"
    assert [d.record.doc_id for d in service.ingest_all_registered()] == [
        "waveform-manual"
    ]
    assert [d.record.doc_id for d in service.ingest_all_registered_pdfs()] == []
    with pytest.raises(ValueError, match="unsupported ingestion type: txt"):
        service.ingest_document("inventory-only")


def test_catalog_and_api_serve_markdown_without_pdf_pages(tmp_path):
    path = tmp_path / "manual.md"
    path.write_text(MD, encoding="utf-8")
    chunk = SimpleNamespace(
        document_id="waveform-manual",
        document_title="测试手册",
        document_version="waveform@dc50e08",
        category="beam_diagnostics",
        topic="waveform",
        language="zh",
        chunk_id="waveform-manual:1",
    )
    catalog = DocumentCatalog()
    catalog.add(chunk, path)
    catalog.finish()
    service = SimpleNamespace(documents={"waveform-manual": path}, catalog=catalog)
    with TestClient(create_app(service)) as client:
        listed = client.get("/v1/rag/documents").json()["documents"][0]
        assert listed["document_format"] == "md"
        assert listed["page_count"] is None
        assert listed["document_url"] == "/v1/rag/documents/waveform-manual"
        raw = client.get("/v1/rag/documents/waveform-manual")
        assert raw.status_code == 200
        assert raw.headers["content-type"].startswith("text/markdown")
        view = client.get("/v1/rag/documents/waveform-manual/view")
        assert view.status_code == 200
        assert view.headers["content-type"].startswith("text/html")
        sections = client.get("/v1/rag/documents/waveform-manual/sections").json()
        assert sections["sections"][1]["index"] == 2
        assert "结论先行" in sections["sections"][1]["text"]
        path.unlink()
        assert client.get("/v1/rag/documents/waveform-manual/view").status_code == 404
        assert (
            client.get("/v1/rag/documents/waveform-manual/sections").status_code == 404
        )


def test_nested_fence_markers_do_not_expose_code_headings():
    text = "# Manual\n\n## One\n````markdown\n```python\n## code\n```\n~~~\n## still code\n````\n## Two\nBody"
    sections = split_sections(text)
    assert len(sections) == 3
    assert "## still code" in sections[1]
    assert sections[2].startswith("## Two")


def test_markdown_update_replaces_stale_vectors_and_keeps_other_documents(
    tmp_path, passage_embedder, chunk
):
    from dataclasses import replace
    from qdrant_client import QdrantClient
    from accelerator_rag.retrieval.dense import DenseRetriever
    from accelerator_rag.retrieval.index_contract import DenseIndexContract
    from accelerator_rag.retrieval.passages import PassageBuilder
    from accelerator_rag.storage.qdrant_passages import QdrantPassageStore

    path = tmp_path / "manual.md"
    path.write_text(MD)
    record = records("data/l0_raw/kb/manual.md")
    original = chunk_markdown(
        parse_markdown(path, source_path=record.source_path), record
    )
    builder = PassageBuilder(passage_embedder)
    contract = DenseIndexContract.from_fingerprint(
        passage_embedder.fingerprint(), builder.contract
    )
    with closing(QdrantClient(":memory:")) as client:
        store = QdrantPassageStore(client, "md", contract)
        dense = DenseRetriever(passage_embedder, store, passage_builder=builder)
        dense.index_document(chunk.document_id, [chunk])
        dense.index_document(record.doc_id, original)
        old_ids = {c.chunk_id for c in original}
        path.write_text("# Revised\n\n## Frequency\nNew frequency support and version.")
        updated = chunk_markdown(
            parse_markdown(path, source_path=record.source_path),
            replace(record, version="v2"),
        )
        dense.index_document(record.doc_id, updated)
        actual = {p.parent_chunk_id: p.parent for p in store.all_passages()}
        assert old_ids.isdisjoint(actual)
        assert actual == {c.chunk_id: c for c in [chunk, *updated]}
        count = store.point_count()
        dense.index_document(record.doc_id, updated)
        assert store.point_count() == count


def test_index_script_apply_updates_existing_collection(
    tmp_path, passage_embedder, monkeypatch
):
    """Exercise the real --apply path with local Qdrant and a test embedder."""
    from dataclasses import asdict
    import importlib.util
    from pathlib import Path
    from qdrant_client import QdrantClient
    import accelerator_rag.embedding
    from accelerator_rag.retrieval.index_contract import DenseIndexContract
    from accelerator_rag.retrieval.passages import PassageBuilder
    from accelerator_rag.storage.qdrant_passages import QdrantPassageStore

    source = Path(__file__).resolve().parents[2] / "scripts/build_markdown_index.py"
    spec = importlib.util.spec_from_file_location("md_indexer", source)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    monkeypatch.setattr(script, "ROOT", tmp_path)
    record = records("data/l0_raw/kb/manual.md")
    raw = tmp_path / record.source_path
    raw.parent.mkdir(parents=True)
    raw.write_text(MD)
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps([asdict(record)]))
    builder = PassageBuilder(passage_embedder)
    contract = DenseIndexContract.from_fingerprint(
        passage_embedder.fingerprint(), builder.contract
    )
    index = tmp_path / "index"
    with closing(QdrantClient(path=str(index))) as client:
        QdrantPassageStore(client, "md", contract).ensure_collection()
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "indexes": [
                    {
                        "index_path": str(index),
                        "model_name": "fixture",
                        "model_path": "unused",
                        "device": "cpu",
                        "dense_index_contract_id": contract.contract_id,
                        "collection": "md",
                        "point_count": 0,
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(
        accelerator_rag.embedding, "EmbeddingModel", lambda *a, **kw: passage_embedder
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_markdown_index.py",
            "--apply",
            "--registry",
            str(registry),
            "--config",
            str(config),
        ],
    )
    assert script.main() == 0
    with closing(QdrantClient(path=str(index))) as client:
        parents = {
            p.parent_chunk_id
            for p in QdrantPassageStore(client, "md", contract).all_passages()
        }
    expected = IngestionService(tmp_path, registry).ingest_document(record.doc_id)
    assert parents == {c.chunk_id for c in expected}
    raw.write_text("")
    with pytest.raises(ValueError, match="no eligible chunks"):
        script.collect(registry)
