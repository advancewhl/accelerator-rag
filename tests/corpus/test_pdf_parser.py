from pathlib import Path

import pymupdf
import pytest

from accelerator_rag.corpus.pdf_parser import (
    PdfTextBlock,
    _detect_page_warnings,
    _looks_garbled,
    _looks_two_column,
    parse_pdf,
)


def _create_test_pdf(path: Path) -> None:
    document = pymupdf.open()

    page1 = document.new_page()
    page1.insert_text(
        (72, 72),
        "EPICS provides a distributed control system.",
    )

    page2 = document.new_page()
    page2.insert_text(
        (72, 72),
        "BPM measures beam position.",
    )

    document.save(path)
    document.close()


def test_parse_pdf_preserves_pages_and_text(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _create_test_pdf(pdf_path)

    parsed = parse_pdf(pdf_path)

    assert parsed.page_count == 2
    assert len(parsed.pages) == 2

    assert parsed.pages[0].page_number == 1
    assert parsed.pages[1].page_number == 2

    assert "EPICS" in parsed.pages[0].text
    assert "BPM" in parsed.pages[1].text


def test_parse_pdf_rejects_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pdf"

    with pytest.raises(FileNotFoundError):
        parse_pdf(missing)


def test_parse_pdf_rejects_non_pdf(tmp_path: Path) -> None:
    text_path = tmp_path / "sample.txt"
    text_path.write_text("not a pdf", encoding="utf-8")

    with pytest.raises(ValueError):
        parse_pdf(text_path)


def test_detect_page_warnings_marks_possible_scan() -> None:
    warnings = _detect_page_warnings(
        text="",
        image_count=1,
        blocks=[],
        page_width=600.0,
    )

    assert "empty_text" in warnings
    assert "possible_scanned_page" in warnings


def test_looks_garbled_detects_replacement_character() -> None:
    assert _looks_garbled("EPICS\ufffdcontrol") is True
    assert _looks_garbled("EPICS control system") is False


def test_looks_two_column_detects_left_and_right_blocks() -> None:
    long_text = "accelerator control system " * 10

    blocks = [
        PdfTextBlock(
            block_number=0,
            block_type=0,
            bbox=(50.0, 100.0, 270.0, 180.0),
            text=long_text,
        ),
        PdfTextBlock(
            block_number=1,
            block_type=0,
            bbox=(50.0, 200.0, 270.0, 280.0),
            text=long_text,
        ),
        PdfTextBlock(
            block_number=2,
            block_type=0,
            bbox=(330.0, 100.0, 550.0, 180.0),
            text=long_text,
        ),
        PdfTextBlock(
            block_number=3,
            block_type=0,
            bbox=(330.0, 200.0, 550.0, 280.0),
            text=long_text,
        ),
    ]

    assert _looks_two_column(blocks, page_width=600.0) is True


def test_looks_two_column_ignores_narrow_side_text() -> None:
    long_text = "accelerator control system " * 10

    blocks = [
        PdfTextBlock(
            block_number=0,
            block_type=0,
            bbox=(50.0, 100.0, 270.0, 180.0),
            text=long_text,
        ),
        PdfTextBlock(
            block_number=1,
            block_type=0,
            bbox=(50.0, 200.0, 270.0, 280.0),
            text=long_text,
        ),
        PdfTextBlock(
            block_number=2,
            block_type=0,
            bbox=(570.0, 100.0, 580.0, 500.0),
            text=long_text,
        ),
        PdfTextBlock(
            block_number=3,
            block_type=0,
            bbox=(570.0, 100.0, 580.0, 500.0),
            text=long_text,
        ),
    ]

    assert _looks_two_column(blocks, page_width=600.0) is False


def test_private_use_character_is_not_garbled() -> None:
    assert _looks_garbled("pulse width 2.5\uf06ds") is False


def test_looks_garbled_detects_null_character() -> None:
    assert _looks_garbled("XFEL\x00control") is True
