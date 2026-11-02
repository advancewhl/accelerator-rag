"""The reader must not silently present a DOCX/PPTX/XLSX as Markdown."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from accelerator_rag.rag.api import create_app


def test_reader_dispatches_supported_formats_and_refuses_others(tmp_path):
    pdf = tmp_path / "design.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    markdown = tmp_path / "manual.md"
    markdown.write_text("# 手册\n", encoding="utf-8")
    docx = tmp_path / "manual.docx"
    docx.write_bytes(b"PK")
    service = SimpleNamespace(
        documents={"pdf": pdf, "md": markdown, "docx": docx}
    )
    with TestClient(create_app(service)) as client:
        assert client.get("/v1/rag/documents/pdf/view").status_code == 200
        assert client.get("/v1/rag/documents/md/view").status_code == 200
        refused = client.get("/v1/rag/documents/docx/view")
        assert refused.status_code == 501
        assert refused.json()["detail"] == {
            "code": "READER_NOT_IMPLEMENTED",
            "format": "docx",
        }
