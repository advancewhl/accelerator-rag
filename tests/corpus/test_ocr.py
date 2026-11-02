"""OCR detection and page planning must fail loudly, never fabricate text."""

from pathlib import Path

import pymupdf
import pytest

from accelerator_rag.corpus import ocr
from accelerator_rag.corpus.ocr import (
    OCRToolStatus,
    OCRUnavailable,
    detect_ocr_tool,
    ocr_pdf_pages,
    ocr_plan_digest,
    plan_pdf_ocr,
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
    assert document.blocks[0].position.kind == "pdf_page"
