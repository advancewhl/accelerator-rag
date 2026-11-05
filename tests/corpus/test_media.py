"""Embedded images keep anchors, media files and selective OCR."""

import base64
from io import BytesIO

from docx import Document
from pptx import Presentation
from pptx.util import Inches
import pytest

from accelerator_rag.corpus import media
from accelerator_rag.corpus.docx_parser import parse_docx
from accelerator_rag.corpus.ocr import OCRToolStatus
from accelerator_rag.corpus.pptx_parser import parse_pptx


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
SOURCE = "data/l0_raw/incoming/batch/manual.docx"


def build_docx(path):
    document = Document()
    document.add_heading("3. 操作界面", level=1)
    document.add_paragraph("启动前确认设备状态。" * 5)
    document.add_picture(BytesIO(PNG))
    document.add_paragraph("图1 操作界面", style="Caption")
    document.save(path)


def build_pptx(path):
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_textbox(Inches(1), Inches(1), Inches(3), Inches(1)).text = "操作界面"
    slide.shapes.add_picture(BytesIO(PNG), Inches(1), Inches(2), Inches(1), Inches(1))
    presentation.save(path)


def test_docx_image_materializes_and_attaches_following_caption(tmp_path):
    path = tmp_path / "manual.docx"
    build_docx(path)
    media_dir = tmp_path / "media"
    parsed = parse_docx(
        path,
        revision_id="media-rev",
        source_path=SOURCE,
        media_dir=media_dir,
        media_prefix="media/media-rev",
        media_min_bytes=0,
    )
    image = next(block for block in parsed.blocks if block.block_type == "image")
    metadata = dict(image.metadata)

    assert image.caption == "图1 操作界面"
    assert metadata["media_path"].startswith("media/media-rev/")
    assert (media_dir / metadata["media_path"].split("/")[-1]).is_file()
    assert len(metadata["media_sha256"]) == 64
    assert dict(parsed.metadata)["image_count"] == "1"


def test_media_budget_skips_file_but_keeps_anchor(tmp_path):
    path = tmp_path / "manual.docx"
    build_docx(path)
    parsed = parse_docx(
        path,
        revision_id="media-rev",
        source_path=SOURCE,
        media_dir=tmp_path / "media",
        media_min_bytes=0,
        media_max_bytes=10,
    )
    image = next(block for block in parsed.blocks if block.block_type == "image")
    metadata = dict(image.metadata)

    assert metadata["media_status"] == "budget_exceeded"
    assert "media_path" not in metadata
    assert not (tmp_path / "media").exists()


def test_pptx_media_budget_leaves_anchor_without_file(tmp_path):
    path = tmp_path / "deck.pptx"
    build_pptx(path)
    parsed = parse_pptx(
        path,
        revision_id="media-rev",
        source_path="data/l0_raw/incoming/batch/deck.pptx",
        media_dir=tmp_path / "media",
        media_min_bytes=0,
        media_max_bytes=10,
    )
    image = next(block for block in parsed.blocks if block.block_type == "image")

    assert dict(image.metadata)["media_status"] == "budget_exceeded"
    assert "media_path" not in dict(image.metadata)


def test_pptx_image_materializes_with_dimensions(tmp_path):
    path = tmp_path / "deck.pptx"
    build_pptx(path)
    media_dir = tmp_path / "media"
    parsed = parse_pptx(
        path,
        revision_id="media-rev",
        source_path="data/l0_raw/incoming/batch/deck.pptx",
        media_dir=media_dir,
        media_min_bytes=0,
    )
    image = next(block for block in parsed.blocks if block.block_type == "image")
    metadata = dict(image.metadata)

    assert metadata["media_ext"] == "png"
    assert metadata["width_emu"]
    assert (media_dir / metadata["media_path"].split("/")[-1]).is_file()


def test_selective_image_ocr_adds_review_required_text(tmp_path, monkeypatch):
    path = tmp_path / "manual.docx"
    build_docx(path)
    media_dir = tmp_path / "media"
    parsed = parse_docx(
        path,
        revision_id="media-rev",
        source_path=SOURCE,
        media_dir=media_dir,
        media_prefix="media/media-rev",
        media_min_bytes=0,
    )
    monkeypatch.setattr(
        media,
        "detect_ocr_tool",
        lambda: OCRToolStatus(True, "/usr/bin/tesseract", "5", ("chi_sim", "eng")),
    )
    monkeypatch.setattr(media, "ocr_image_file", lambda *args, **kwargs: "启动按钮")
    enriched = media.enrich_image_ocr(
        parsed, media_root=media_dir, max_images=5, min_bytes=0
    )
    ocr = next(
        block
        for block in enriched.blocks
        if dict(block.metadata).get("source") == "image_ocr"
    )

    assert ocr.text == "启动按钮"
    assert dict(ocr.metadata)["manual_review_required"] == "true"
    assert dict(ocr.metadata)["media_block_id"] == next(
        block.block_id for block in parsed.blocks if block.block_type == "image"
    )
    assert "image_ocr_count:1" in enriched.warnings


def test_ocr_is_skipped_without_operation_or_parameter_context(tmp_path, monkeypatch):
    path = tmp_path / "manual.docx"
    document = Document()
    document.add_heading("1. 背景", level=1)
    document.add_picture(BytesIO(PNG))
    document.save(path)
    parsed = parse_docx(
        path,
        revision_id="media-rev",
        source_path=SOURCE,
        media_dir=tmp_path / "media",
        media_min_bytes=0,
    )
    monkeypatch.setattr(
        media,
        "detect_ocr_tool",
        lambda: OCRToolStatus(True, "tesseract", "5", ("chi_sim", "eng")),
    )
    called = []
    monkeypatch.setattr(
        media, "ocr_image_file", lambda *args, **kwargs: called.append(1) or "x"
    )
    enriched = media.enrich_image_ocr(
        parsed, media_root=tmp_path / "media", max_images=5
    )

    assert not called
    assert not any(
        dict(block.metadata).get("source") == "image_ocr"
        for block in enriched.blocks
    )


def test_operation_manual_selects_images_without_keyword_heading(
    tmp_path, monkeypatch
):
    path = tmp_path / "manual.docx"
    document = Document()
    document.add_heading("1. 背景", level=1)
    document.add_picture(BytesIO(PNG))
    document.save(path)
    parsed = parse_docx(
        path,
        revision_id="media-rev",
        source_path=SOURCE,
        media_dir=tmp_path / "media",
        media_min_bytes=0,
    )
    monkeypatch.setattr(
        media,
        "detect_ocr_tool",
        lambda: OCRToolStatus(True, "tesseract", "5", ("chi_sim", "eng")),
    )
    monkeypatch.setattr(media, "ocr_image_file", lambda *args, **kwargs: "按钮")
    enriched = media.enrich_image_ocr(
        parsed,
        media_root=tmp_path / "media",
        max_images=5,
        min_bytes=0,
        document_kind="operation_manual",
    )

    assert any(
        dict(block.metadata).get("source") == "image_ocr"
        for block in enriched.blocks
    )


def test_image_ocr_unavailable_is_a_warning_not_a_failure(tmp_path, monkeypatch):
    path = tmp_path / "manual.docx"
    build_docx(path)
    parsed = parse_docx(
        path,
        revision_id="media-rev",
        source_path=SOURCE,
        media_dir=tmp_path / "media",
        media_min_bytes=0,
    )
    monkeypatch.setattr(
        media,
        "detect_ocr_tool",
        lambda: OCRToolStatus(False, "", "", (), "missing"),
    )
    enriched = media.enrich_image_ocr(
        parsed, media_root=tmp_path / "media", max_images=5, min_bytes=0
    )

    assert "image_ocr_unavailable" in enriched.warnings


@pytest.mark.parametrize("max_images", [0, -1])
def test_image_ocr_can_be_disabled(tmp_path, max_images):
    path = tmp_path / "manual.docx"
    build_docx(path)
    parsed = parse_docx(
        path,
        revision_id="media-rev",
        source_path=SOURCE,
        media_dir=tmp_path / "media",
        media_min_bytes=0,
    )
    assert media.enrich_image_ocr(
        parsed, media_root=tmp_path / "media", max_images=max_images
    ) == parsed
