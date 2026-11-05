"""Office readers use the normalized snapshot or parse the original on demand."""

import json
from types import SimpleNamespace

from docx import Document
from fastapi.testclient import TestClient
import pytest

from accelerator_rag.corpus.docx_parser import parse_docx
from accelerator_rag.rag.api import create_app
from accelerator_rag.rag.reader import (
    DocumentReader,
    ReaderRecord,
    ReaderUnavailable,
)


def make_docx(path):
    document = Document()
    document.add_heading("1. 系统", level=1)
    document.add_paragraph("打开界面后先确认状态。" * 8)
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "设备"
    table.cell(0, 1).text = "阈值"
    table.cell(1, 0).text = "BPM01"
    table.cell(1, 1).text = "100 µs"
    document.save(path)


def make_service(tmp_path, *, snapshot_dir=None):
    pdf = tmp_path / "design.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    markdown = tmp_path / "manual.md"
    markdown.write_text("# 手册\n", encoding="utf-8")
    docx = tmp_path / "manual.docx"
    make_docx(docx)
    unknown = tmp_path / "drawing.dwg"
    unknown.write_bytes(b"AC1032")
    service = SimpleNamespace(
        documents={
            "pdf": pdf,
            "md": markdown,
            "docx": docx,
            "drawing": unknown,
        },
        document_sources={
            "docx": "data/l0_raw/incoming/2026-11-02-shine-control/资料/manual.docx"
        },
        document_titles={"docx": "定时操作手册"},
        snapshot_dir=str(snapshot_dir) if snapshot_dir else None,
    )
    return service


def test_reader_dispatches_supported_formats_and_refuses_unknown(tmp_path):
    service = make_service(tmp_path)
    with TestClient(create_app(service)) as client:
        assert client.get("/v1/rag/documents/pdf/view").status_code == 200
        assert client.get("/v1/rag/documents/md/view").status_code == 200
        assert client.get("/v1/rag/documents/docx/view").status_code == 200
        refused = client.get("/v1/rag/documents/drawing/view")
        assert refused.status_code == 501
        assert refused.json()["detail"] == {
            "code": "READER_NOT_IMPLEMENTED",
            "format": "dwg",
        }


def test_office_content_is_normalized_and_download_uses_correct_mime(tmp_path):
    service = make_service(tmp_path)
    with TestClient(create_app(service)) as client:
        content = client.get("/v1/rag/documents/docx/content")
        assert content.status_code == 200
        payload = content.json()
        assert payload["document_format"] == "docx"
        assert payload["source"] == "on_demand"
        assert "source_path" not in payload
        assert payload["snapshot_missing"] is True
        assert [block["block_type"] for block in payload["blocks"]][:2] == [
            "heading",
            "paragraph",
        ]
        table = next(block for block in payload["blocks"] if block["block_type"] == "table")
        assert table["table"]["rows"][0] == ["设备", "阈值"]
        heading = payload["blocks"][0]
        assert heading["section_path"] == "1. 系统"
        assert payload["total_blocks"] == len(payload["blocks"])
        assert payload["next_offset"] is None

        page = client.get(
            "/v1/rag/documents/docx/content?limit=1"
        ).json()
        assert len(page["blocks"]) == 1
        assert page["next_offset"] == 1
        anchor = payload["blocks"][-1]["block_id"]
        centred = client.get(
            "/v1/rag/documents/docx/content",
            params={"block_id": anchor, "limit": 1},
        ).json()
        assert centred["blocks"][0]["block_id"] == anchor

        download = client.get("/v1/rag/documents/docx")
        assert download.status_code == 200
        assert download.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert download.headers["content-disposition"].startswith("attachment")
        assert client.get("/v1/rag/documents/docx/metadata").json()[
            "reader_kind"
        ] == "office"


def test_snapshot_is_preferred_over_reparsing(tmp_path):
    snapshot = tmp_path / "build"
    (snapshot / "parsed").mkdir(parents=True)
    source = tmp_path / "original.docx"
    make_docx(source)
    parsed = parse_docx(
        source,
        revision_id="docx",
        title="定时操作手册",
        source_path="data/l0_raw/incoming/2026-11-02-shine-control/资料/manual.docx",
    )
    (snapshot / "parsed" / "docx.json").write_text(
        json.dumps(parsed.to_dict(), ensure_ascii=False), encoding="utf-8"
    )
    service = make_service(tmp_path, snapshot_dir=snapshot)
    with TestClient(create_app(service)) as client:
        payload = client.get("/v1/rag/documents/docx/content").json()

    assert payload["source"] == "snapshot"
    assert "snapshot_missing" not in payload


def test_large_document_without_snapshot_is_refused(tmp_path):
    path = tmp_path / "huge.docx"
    path.write_bytes(b"PK" + b"0" * 100)
    reader = DocumentReader(snapshot_dir=None, max_on_demand_bytes=10)
    record = ReaderRecord(
        document_id="huge",
        path=path,
        source_path="data/l0_raw/incoming/batch/huge.docx",
        title="Huge",
    )
    with pytest.raises(ReaderUnavailable, match="snapshot"):
        reader.read(record)


def test_media_endpoint_serves_only_safe_snapshot_raster_files(tmp_path):
    snapshot = tmp_path / "build"
    parsed_dir = snapshot / "parsed"
    parsed_dir.mkdir(parents=True)
    source = tmp_path / "original.docx"
    make_docx(source)
    parsed = parse_docx(
        source,
        revision_id="docx",
        title="定时操作手册",
        source_path="data/l0_raw/incoming/2026-11-02-shine-control/资料/manual.docx",
    )
    payload = parsed.to_dict()
    payload["blocks"][0]["metadata"].append(
        ["media_path", "media/docx/0123456789abcdef.png"]
    )
    (parsed_dir / "docx.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    media_dir = snapshot / "media" / "docx"
    media_dir.mkdir(parents=True)
    (media_dir / "0123456789abcdef.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (media_dir / "0123456789abcdef.svg").write_text(
        "<svg><script>alert(1)</script></svg>", encoding="utf-8"
    )

    service = make_service(tmp_path, snapshot_dir=snapshot)
    with TestClient(create_app(service)) as client:
        content = client.get("/v1/rag/documents/docx/content").json()
        assert content["blocks"][0]["media_url"].endswith(
            "/media/0123456789abcdef.png"
        )
        served = client.get("/v1/rag/documents/docx/media/0123456789abcdef.png")
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/png"
        assert (
            client.get(
                "/v1/rag/documents/docx/media/0123456789abcdef.svg"
            ).status_code
            == 404
        )
        assert (
            client.get(
                "/v1/rag/documents/docx/media/not-a-hash.png"
            ).status_code
            == 404
        )
        assert (
            client.get(
                "/v1/rag/documents/docx/media/..%2F..%2Fsecret.png"
            ).status_code
            == 404
        )


def test_corrupt_office_file_returns_503(tmp_path):
    service = make_service(tmp_path)
    service.documents["broken"] = tmp_path / "broken.docx"
    service.documents["broken"].write_bytes(b"not a zip")
    service.document_sources["broken"] = (
        "data/l0_raw/incoming/batch/broken.docx"
    )
    service.document_titles["broken"] = "Broken"
    with TestClient(create_app(service)) as client:
        response = client.get("/v1/rag/documents/broken/content")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "CONTENT_NOT_AVAILABLE"
    metadata = client.get("/v1/rag/documents/broken/metadata").json()
    assert metadata["content_available"] is False
