from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

# from pydoc import text
from typing import Any

# import warnings

import pymupdf


@dataclass(frozen=True)
class PdfTextBlock:
    block_number: int
    block_type: int
    bbox: tuple[float, float, float, float]
    text: str


@dataclass(frozen=True)
class PdfPage:
    page_number: int
    width: float
    height: float
    text: str
    char_count: int
    blocks: list[PdfTextBlock]
    image_count: int
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedPdfDocument:
    source_path: str
    file_name: str
    page_count: int
    metadata: dict[str, Any]
    pages: list[PdfPage]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extract_text_blocks(page: pymupdf.Page) -> list[PdfTextBlock]:
    raw_blocks = page.get_text("blocks")

    blocks: list[PdfTextBlock] = []

    for raw_block in raw_blocks:
        x0, y0, x1, y1, text, block_number, block_type = raw_block[:7]

        normalized_text = text.strip()

        if not normalized_text:
            continue

        blocks.append(
            PdfTextBlock(
                block_number=int(block_number),
                block_type=int(block_type),
                bbox=(
                    float(x0),
                    float(y0),
                    float(x1),
                    float(y1),
                ),
                text=normalized_text,
            )
        )

    return blocks


def _looks_two_column(
    blocks: list[PdfTextBlock],
    page_width: float,
) -> bool:
    if page_width <= 0:
        return False

    midpoint = page_width / 2
    center_margin = page_width * 0.08

    left_blocks = 0
    right_blocks = 0

    for block in blocks:
        if block.block_type != 0:
            continue

        if len(block.text) < 80:
            continue

        x0, _, x1, _ = block.bbox
        block_width = x1 - x0
        relative_width = block_width / page_width

        # 横跨大部分页面的标题、摘要标题等，
        # 不拿来判断左右栏。
        if relative_width < 0.20 or relative_width > 0.72:
            continue

        block_center = (x0 + x1) / 2

        if block_center < midpoint and x1 <= midpoint + center_margin:
            left_blocks += 1

        elif block_center > midpoint and x0 >= midpoint - center_margin:
            right_blocks += 1

    return left_blocks >= 2 and right_blocks >= 2


def _looks_garbled(text: str) -> bool:
    if not text:
        return False

    return "\ufffd" in text or "\x00" in text


def _contains_private_use_characters(text: str) -> bool:
    return any(0xE000 <= ord(char) <= 0xF8FF for char in text)


def _detect_page_warnings(
    *,
    text: str,
    image_count: int,
    blocks: list[PdfTextBlock],
    page_width: float,
) -> list[str]:
    warnings: list[str] = []

    char_count = len(text.strip())

    if char_count == 0:
        warnings.append("empty_text")

    if char_count < 50 and image_count > 0:
        warnings.append("possible_scanned_page")

    if _looks_two_column(blocks, page_width):
        warnings.append("possible_two_column")

    if _looks_garbled(text):
        warnings.append("possible_garbled_text")

    if _contains_private_use_characters(text):
        warnings.append("private_use_characters")

    return warnings


def _parse_page(page: pymupdf.Page, page_index: int) -> PdfPage:
    text = page.get_text("text").strip()

    blocks = _extract_text_blocks(page)

    image_count = len(page.get_images(full=True))

    rect = page.rect

    warnings = _detect_page_warnings(
        text=text,
        image_count=image_count,
        blocks=blocks,
        page_width=float(rect.width),
    )

    return PdfPage(
        page_number=page_index + 1,
        width=float(rect.width),
        height=float(rect.height),
        text=text,
        char_count=len(text),
        blocks=blocks,
        image_count=image_count,
        warnings=warnings,
    )


def parse_pdf(path: str | Path) -> ParsedPdfDocument:
    pdf_path = Path(path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file: {pdf_path}")

    pages: list[PdfPage] = []
    document_warnings: list[str] = []

    with pymupdf.open(pdf_path) as document:
        for page_index, page in enumerate(document):
            pages.append(_parse_page(page, page_index))

        if not pages:
            document_warnings.append("empty_document")

        if pages and all(page.char_count == 0 for page in pages):
            document_warnings.append("no_extractable_text")

        metadata = {
            str(key): value
            for key, value in document.metadata.items()
            if value is not None
        }

        page_count = document.page_count

    return ParsedPdfDocument(
        source_path=pdf_path.as_posix(),
        file_name=pdf_path.name,
        page_count=page_count,
        metadata=metadata,
        pages=pages,
        warnings=document_warnings,
    )
