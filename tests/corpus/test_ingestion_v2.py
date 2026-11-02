"""Schema v2 parse orchestration: dispatch, identity and refusal rules."""

from pathlib import Path

from docx import Document
import openpyxl
import pymupdf
from pptx import Presentation
import pytest

from accelerator_rag.corpus import ingestion_v2
from accelerator_rag.corpus.docx_parser import parse_docx
from accelerator_rag.corpus.ingestion_v2 import parse_path, parse_revision
from accelerator_rag.corpus.schema_v2 import RevisionRecord
from accelerator_rag.corpus.structured_parser import UnsupportedStructuredFormat


def revision(**overrides):
    data = {
        "family_id": "sample-family",
        "revision_id": "sample-revision",
        "title": "样例文档",
        "revision_label": "v1",
        "batch_id": "test-batch",
        "original_asset_id": "asset-sample-original",
        "source_path": "data/l0_raw/manual.docx",
        "source_format": "docx",
        "language": "zh",
        "document_kind": "operation_manual",
        "category": "control_system",
        "topic": "timing",
        "evidence_role": "operating_step",
        "usage_status": "reference",
        "approval_status": "unknown",
        "disposition": "text_index",
        "reason": "test fixture",
        "received_at": "2026-11-02",
        "scope": ["test"],
    }
    data.update(overrides)
    return RevisionRecord.from_dict(data)


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "data/l0_raw").mkdir(parents=True)
    return root


def _write_docx(path: Path) -> None:
    document = Document()
    document.add_heading("操作步骤", level=1)
    document.add_paragraph("关闭电源。")
    document.save(path)


def _write_pdf(path: Path) -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Interlock response time is below 100 us.")
    document.save(path)


def test_parse_revision_docx_passes_identity(tmp_path):
    root = _project(tmp_path)
    path = root / "data/l0_raw/manual.docx"
    _write_docx(path)

    parsed = parse_revision(revision(), root)

    assert parsed.revision_id == "sample-revision"
    assert parsed.asset_id == "asset-sample-original"
    assert parsed.title == "样例文档"
    assert parsed.source_path == "data/l0_raw/manual.docx"
    assert parsed.source_format == "docx"
    assert [block.block_type for block in parsed.blocks] == [
        "heading",
        "paragraph",
    ]


def test_parse_revision_markdown_dispatch(tmp_path):
    root = _project(tmp_path)
    path = root / "data/l0_raw/guide.md"
    path.write_text("# 章节\n\n正文内容。\n", encoding="utf-8")

    parsed = parse_revision(
        revision(
            source_path="data/l0_raw/guide.md",
            source_format="md",
        ),
        root,
    )

    assert parsed.source_format == "md"
    assert parsed.position_kinds == ("section",)
    assert [block.block_type for block in parsed.blocks] == [
        "heading",
        "paragraph",
    ]


def test_parse_revision_pdf_dispatch(tmp_path):
    root = _project(tmp_path)
    path = root / "data/l0_raw/interlock.pdf"
    _write_pdf(path)

    parsed = parse_revision(
        revision(
            source_path="data/l0_raw/interlock.pdf",
            source_format="pdf",
            document_kind="subsystem_design",
            evidence_role="design_target",
        ),
        root,
    )

    assert parsed.source_format == "pdf"
    assert parsed.position_kinds == ("pdf_page",)
    assert any("Interlock" in block.text for block in parsed.blocks)


def test_parse_revision_pptx_dispatch(tmp_path):
    root = _project(tmp_path)
    path = root / "data/l0_raw/deck.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = "幻灯片标题"
    presentation.save(path)

    parsed = parse_revision(
        revision(
            source_path="data/l0_raw/deck.pptx",
            source_format="pptx",
        ),
        root,
    )

    assert parsed.source_format == "pptx"
    assert parsed.position_kinds == ("slide",)
    assert parsed.blocks[0].text == "幻灯片标题"


def test_parse_revision_structured_dispatch(tmp_path):
    root = _project(tmp_path)
    csv_path = root / "data/l0_raw/terminals.csv"
    csv_path.write_text("端子,信号\nA1,24V\n", encoding="utf-8")
    xlsx_path = root / "data/l0_raw/params.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["名称", "数值"])
    sheet.append(["增益", "2"])
    workbook.save(xlsx_path)

    csv_parsed = parse_revision(
        revision(
            source_path="data/l0_raw/terminals.csv",
            source_format="csv",
            disposition="structured_index",
            document_kind="structured_list",
            evidence_role="specification_requirement",
        ),
        root,
    )
    xlsx_parsed = parse_revision(
        revision(
            source_path="data/l0_raw/params.xlsx",
            source_format="xlsx",
            disposition="structured_index",
            document_kind="structured_list",
            evidence_role="specification_requirement",
        ),
        root,
    )

    assert csv_parsed.source_format == "csv"
    assert csv_parsed.position_kinds == ("cell_range",)
    assert csv_parsed.blocks[0].table.rows == (("端子", "信号"), ("A1", "24V"))
    assert xlsx_parsed.source_format == "xlsx"
    assert xlsx_parsed.position_kinds == ("cell_range",)
    assert xlsx_parsed.blocks[0].table.rows == (("名称", "数值"), ("增益", "2"))


def test_parse_revision_ods_refuses(tmp_path):
    root = _project(tmp_path)
    path = root / "data/l0_raw/table.ods"
    path.write_bytes(b"not really an ods")

    with pytest.raises(UnsupportedStructuredFormat, match="odfpy"):
        parse_revision(
            revision(
                source_path="data/l0_raw/table.ods",
                source_format="ods",
                disposition="structured_index",
                document_kind="structured_list",
            ),
            root,
        )


def test_parse_revision_doc_dispatch_without_soffice(tmp_path, monkeypatch):
    root = _project(tmp_path)
    doc_path = root / "data/l0_raw/manual.doc"
    doc_path.write_bytes(b"legacy doc placeholder")
    prepared_docx = tmp_path / "prepared.docx"
    _write_docx(prepared_docx)

    captured = {}

    def fake_parse_doc(path, **kwargs):
        captured.update(kwargs)
        return parse_docx(
            prepared_docx,
            revision_id=kwargs["revision_id"],
            asset_id=kwargs["asset_id"],
            title=kwargs["title"],
            source_path=kwargs["source_path"],
            source_format="doc",
        )

    monkeypatch.setattr(ingestion_v2, "parse_doc", fake_parse_doc)

    parsed = parse_revision(
        revision(
            source_path="data/l0_raw/manual.doc",
            source_format="doc",
        ),
        root,
    )

    assert captured["revision_id"] == "sample-revision"
    assert captured["asset_id"] == "asset-sample-original"
    assert captured["title"] == "样例文档"
    assert captured["source_path"] == "data/l0_raw/manual.doc"
    assert captured["timeout"] == 180
    assert captured["output_dir"] is None
    assert parsed.source_format == "doc"
    assert parsed.source_path == "data/l0_raw/manual.doc"
    assert parsed.blocks[0].text == "操作步骤"


def test_excluded_revision_is_rejected(tmp_path):
    root = _project(tmp_path)
    excluded = revision(
        usage_status="excluded",
        disposition="excluded",
    )

    with pytest.raises(ValueError, match="excluded"):
        parse_revision(excluded, root)


@pytest.mark.parametrize(
    "disposition", ["attachment_only", "catalog_only", "deferred"]
)
def test_non_index_disposition_is_rejected(tmp_path, disposition):
    root = _project(tmp_path)

    with pytest.raises(ValueError, match="does not allow parsing"):
        parse_revision(revision(disposition=disposition), root)


def test_missing_source_file_is_reported(tmp_path):
    root = _project(tmp_path)

    with pytest.raises(FileNotFoundError, match="missing"):
        parse_revision(revision(), root)


def test_source_symlink_escape_is_rejected(tmp_path):
    root = _project(tmp_path)
    outside = tmp_path / "outside.docx"
    _write_docx(outside)
    link = root / "data/l0_raw/escape.docx"
    link.symlink_to(outside)

    with pytest.raises(ValueError, match="escapes"):
        parse_revision(
            revision(source_path="data/l0_raw/escape.docx"),
            root,
        )


def test_parse_path_dispatch_and_unknown_format(tmp_path):
    path = tmp_path / "quick.docx"
    _write_docx(path)

    parsed = parse_path(
        path,
        revision_id="quick-check",
        source_path="data/l0_raw/tests/quick.docx",
    )

    assert parsed.revision_id == "quick-check"
    assert parsed.asset_id == "asset-quick-check-original"
    assert parsed.source_path == "data/l0_raw/tests/quick.docx"
    assert parsed.blocks[0].block_type == "heading"

    unknown = tmp_path / "blob.bin"
    unknown.write_bytes(b"\x00\x01")
    with pytest.raises(ValueError, match="cannot determine"):
        parse_path(unknown, revision_id="quick-check")
