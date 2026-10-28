"""The inventory must describe loaded evidence, deduplicate indexes and hide paths."""

from types import SimpleNamespace

import fitz
from fastapi.testclient import TestClient

from accelerator_rag.rag.api import create_app
from accelerator_rag.rag.catalog import DocumentCatalog


def test_loaded_inventory_deduplicates_indexes_and_never_exposes_paths(tmp_path):
    pdf_path = tmp_path / "private-server-location.pdf"
    with fitz.open() as pdf:
        pdf.new_page()
        pdf.new_page()
        pdf.save(pdf_path)
    chunk = dict(
        document_id="design",
        document_title="Design report",
        document_version="2017",
        category="accelerator",
        topic="control",
        language="en",
        chunk_id="section-1",
    )
    catalog = DocumentCatalog()
    catalog.add(SimpleNamespace(**chunk), pdf_path)
    catalog.add(SimpleNamespace(**chunk), pdf_path)  # The second dense index.
    catalog.add(SimpleNamespace(**{**chunk, "chunk_id": "section-2"}), pdf_path)
    catalog.finish()
    with TestClient(create_app(SimpleNamespace(catalog=catalog))) as client:
        response = client.get("/v1/rag/documents")
        assert response.status_code == 200
        data = response.json()
        assert data["document_count"] == 1
        assert data["indexed_section_count"] == 2
        document = data["documents"][0]
        assert document["page_count"] == 2
        assert document["versions"] == ["2017"]
        assert document["document_url"] == "/v1/rag/documents/design"
        assert str(pdf_path) not in response.text
        assert "source_path" not in response.text
        pdf_path.unlink()
        document = client.get("/v1/rag/documents").json()["documents"][0]
        assert document["original_available"] is False
        assert document["document_url"] is None
        assert document["indexed_section_count"] == 2
