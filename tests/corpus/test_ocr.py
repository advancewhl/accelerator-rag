"""OCR detection and page planning must fail loudly, never fabricate text."""

from pathlib import Path

import pymupdf
import pytest

from accelerator_rag.corpus import ocr
from accelerator_rag.corpus.ocr import (
    OCRToolStatus,
    OCRUnavailable,
    _words_text,
    detect_ocr_tool,
    ocr_pdf_pages,
    ocr_plan_digest,
    plan_pdf_ocr,
    reconstruct_ocr_table,
)


def make_pdf(path: Path) -> Path:
    with pymupdf.open() as pdf:
        first = pdf.new_page()
        first.insert_text(
            (72, 72),
            "SHINE uses EPICS for distributed controls. " * 2,
        )
        pdf.new_page()  # blank, no image
        third = pdf.new_page()
        # A tiny generated PNG gives the page an image but no text layer.
        from PIL import Image

        image_path = path.with_suffix(".png")
        Image.new("RGB", (8, 8), "white").save(image_path)
        third.insert_image(pymupdf.Rect(0, 0, 100, 100), filename=str(image_path))
        pdf.save(path)
    return path


def test_detect_ocr_tool_reports_environment_honestly():
    status = detect_ocr_tool()

    assert isinstance(status, OCRToolStatus)
    if status.available:
        assert status.executable
        assert status.languages
    else:
        assert status.reason


def test_plan_classifies_text_blank_and_image_only_pages(tmp_path):
    path = make_pdf(tmp_path / "sample.pdf")
    plans = plan_pdf_ocr(path)

    assert [plan.page_number for plan in plans] == [1, 2, 3]
    assert plans[0].reason == "has_text_layer"
    assert plans[0].recommended is False
    assert plans[1].reason == "blank_page"
    assert plans[1].recommended is False
    assert plans[2].reason == "no_text_layer"
    assert plans[2].recommended is True
    assert ocr_plan_digest(plans) == ocr_plan_digest(plans)


def test_missing_tool_raises_instead_of_returning_empty_text(tmp_path, monkeypatch):
    path = make_pdf(tmp_path / "sample.pdf")
    monkeypatch.setattr(
        ocr,
        "detect_ocr_tool",
        lambda: OCRToolStatus(False, "", "", (), "tesseract not installed"),
    )
    with pytest.raises(OCRUnavailable, match="tesseract not installed"):
        ocr_pdf_pages(
            path,
            revision_id="scan-document-r1",
            asset_id="asset-scan-original",
            source_path="data/l0_raw/incoming/2026-11-02-shine-control/资料/scan.pdf",
            title="扫描件",
        )


def test_missing_language_raises_with_available_list(tmp_path, monkeypatch):
    path = make_pdf(tmp_path / "sample.pdf")
    monkeypatch.setattr(
        ocr,
        "detect_ocr_tool",
        lambda: OCRToolStatus(True, "/usr/bin/tesseract", "tesseract 5", ("eng",)),
    )
    with pytest.raises(OCRUnavailable, match="chi_sim"):
        ocr_pdf_pages(
            path,
            revision_id="scan-document-r1",
            asset_id="asset-scan-original",
            source_path="data/l0_raw/incoming/2026-11-02-shine-control/资料/scan.pdf",
            title="扫描件",
        )


@pytest.mark.skipif(
    not detect_ocr_tool().available, reason="tesseract is not installed here"
)
def test_actual_ocr_records_review_requirement(tmp_path):
    path = make_pdf(tmp_path / "sample.pdf")
    document = ocr_pdf_pages(
        path,
        revision_id="scan-document-r1",
        asset_id="asset-scan-original",
        source_path="data/l0_raw/incoming/2026-11-02-shine-control/资料/scan.pdf",
        title="扫描件",
        pages=[3],
        languages=("eng",),
    )
    assert document.parser_profile == "tesseract-pdf-v1"
    assert document.ocr_profile
    assert dict(document.metadata)["manual_review_required"] == "true"
    assert all(
        block.position.kind == "pdf_page" for block in document.blocks
    )


def test_mixed_page_is_flagged_without_replacing_its_text_layer(tmp_path):
    path = tmp_path / "mixed.pdf"
    from PIL import Image

    image_path = tmp_path / "large.png"
    Image.new("RGB", (32, 32), "white").save(image_path)
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "控制参数表如下，正文文字足够长。" * 6)
        page.insert_image(pymupdf.Rect(100, 100, 500, 500), filename=str(image_path))
        pdf.save(path)

    plan = plan_pdf_ocr(path)[0]

    assert plan.reason == "mixed_text_and_image"
    assert plan.mixed_candidate is True
    assert plan.recommended is False
    assert plan.image_area_ratio > 0.15


def test_ocr_word_rows_rebuild_a_table():
    words = []
    headers = ["设备", "端子号", "信号名"]
    data = [["BPM01", "X09", "SR:BPM01:X"], ["BPM02", "X09A", "SR:BPM02:X"]]
    for line, values in enumerate([headers, *data]):
        for column, text in enumerate(values):
            words.append(
                {
                    "text": text,
                    "conf": 92,
                    "left": column * 100,
                    "top": line * 20,
                    "width": 60,
                    "height": 12,
                    "line": (1, 1, line),
                }
            )
    table = reconstruct_ocr_table(words)

    assert table is not None
    assert table.header_rows == 1
    assert table.rows[0] == ("设备", "端子号", "信号名")
    assert table.rows[1][1] == "X09"
    assert _words_text(words).splitlines()[0] == "设备 端子号 信号名"


def test_prose_lines_do_not_become_a_table():
    words = [
        {
            "text": f"第{line}行正文",
            "conf": 90,
            "left": 20 + line * 5,
            "top": line * 20,
            "width": 80,
            "height": 12,
            "line": (1, 1, line),
        }
        for line in range(4)
    ]

    assert reconstruct_ocr_table(words) is None


def _word(text, left, top, line, width=50, height=12, conf=92):
    return {
        "text": text,
        "conf": conf,
        "left": left,
        "top": top,
        "width": width,
        "height": height,
        "line": (1, 1, line),
    }


def test_empty_cell_keeps_the_row_and_multiword_cell_stays_one_cell():
    words = [
        _word("设备", 0, 0, 0), _word("端子", 100, 0, 0), _word("信号", 200, 0, 0),
        _word("BPM01", 0, 20, 1), _word("X09", 100, 20, 1), _word("SR", 200, 20, 1),
        _word("BPM02", 0, 40, 2), _word("SR2", 200, 40, 2),
        _word("BPM03", 0, 60, 3), _word("X09A", 95, 60, 3), _word("A", 125, 60, 3),
    ]
    table = reconstruct_ocr_table(words)

    assert table is not None
    assert len(table.rows) == 4
    assert table.rows[2][1] == ""
    assert table.rows[3][1] == "X09A A"


def test_two_column_table_is_accepted():
    words = [
        _word("设备", 0, 0, 0), _word("阈值", 120, 0, 0),
        _word("BPM01", 0, 20, 1), _word("100", 120, 20, 1),
        _word("BPM02", 0, 40, 2), _word("120", 120, 40, 2),
    ]
    table = reconstruct_ocr_table(words)

    assert table is not None
    assert table.rows[0] == ("设备", "阈值")


def test_repeated_same_image_is_not_double_counted(tmp_path):
    path = tmp_path / "repeated.pdf"
    from PIL import Image

    image_path = tmp_path / "tiny.png"
    Image.new("RGB", (8, 8), "white").save(image_path)
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "正文文字足够长，不触发稀疏页规则。" * 5)
        for index in range(5):
            page.insert_image(
                pymupdf.Rect(20 + index * 30, 100, 40 + index * 30, 120),
                filename=str(image_path),
            )
        pdf.save(path)

    plan = plan_pdf_ocr(path)[0]

    assert plan.image_area_ratio < 0.10
    assert plan.mixed_candidate is False


def test_table_reconstruction_keeps_the_full_page_text_block(tmp_path, monkeypatch):
    path = make_pdf(tmp_path / "sample.pdf")
    words = [
        _word("设备", 0, 0, 0), _word("端子", 100, 0, 0), _word("信号", 200, 0, 0),
        _word("BPM01", 0, 20, 1), _word("X09", 100, 20, 1), _word("SR1", 200, 20, 1),
        _word("BPM02", 0, 40, 2), _word("X09A", 100, 40, 2), _word("SR2", 200, 40, 2),
    ]
    monkeypatch.setattr(
        ocr,
        "detect_ocr_tool",
        lambda: OCRToolStatus(True, "tesseract", "5", ("eng",)),
    )
    monkeypatch.setattr(ocr, "_ocr_page_words", lambda *args, **kwargs: words)
    monkeypatch.setattr(ocr, "_ocr_page", lambda *args, **kwargs: "full page text")
    document = ocr_pdf_pages(
        path,
        revision_id="scan-document-r1",
        asset_id="asset-scan-original",
        source_path="data/l0_raw/incoming/2026-11-02-shine-control/资料/scan.pdf",
        title="扫描件",
        pages=[3],
        languages=("eng",),
    )

    kinds = [block.block_type for block in document.blocks]
    assert "paragraph" in kinds
    assert "table" in kinds
    paragraph = next(block for block in document.blocks if block.block_type == "paragraph")
    table = next(block for block in document.blocks if block.block_type == "table")
    assert paragraph.position.label == table.position.label
    assert paragraph.metadata and table.metadata
