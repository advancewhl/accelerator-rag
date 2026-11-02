"""Markdown sources parsed into the page-shaped structure used by chunking.

A Markdown document has no physical pages, so each heading-delimited section is
numbered as one "page" in reading order. Consequence to keep explicit: for a
Markdown chunk, `page_start` / `page_end` mean **section index**, not a PDF
page. Section numbers stay stable for a given source text and split level.

Only parsing lives here. Cleaning and chunking stay in their own modules so the
PDF pipeline (`pdf-chunks-v3`) keeps its exact chunk identities.
"""

from __future__ import annotations

import re
from pathlib import Path

from accelerator_rag.corpus.pdf_parser import (
    ParsedPdfDocument,
    PdfPage,
    PdfTextBlock,
)

_SPLIT_LEVEL_CAP = 2
_ATX = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_FRONT_MATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)

# Synthetic page geometry: blocks sit inside the page, away from the PDF margin
# bands, so running PDF cleaning on this structure would drop nothing.
_WIDTH = 1000.0
_HEIGHT = 1000.0
_BLOCK_Y0 = 300.0
_BLOCK_Y1 = 400.0


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Return (metadata, body). The raw block is kept in the body as evidence.

    `applicable_system_version` / `verified_date` / `owner` live in front matter
    and must stay retrievable, so the block is not silently dropped.
    """
    match = _FRONT_MATTER.match(text)
    if match is None:
        return {}, text
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    block = "---\n" + match.group(1).strip() + "\n---"
    return metadata, block + "\n\n" + text[match.end() :].lstrip("\n")


def _headings(lines: list[str]) -> dict[int, int]:
    """ATX boundaries outside fences, respecting delimiter kind and length."""
    headings = {}
    fence = None
    for index, line in enumerate(lines):
        marker = _FENCE.match(line)
        if fence is not None:
            if (
                marker
                and marker[1][0] == fence[0]
                and len(marker[1]) >= len(fence)
                and not marker[2].strip()
            ):
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        match = _ATX.match(line.lstrip())
        if match and len(line) - len(line.lstrip()) <= 3:
            headings[index] = len(match[1])
    return headings


def _split_level(lines: list[str]) -> int:
    levels = set(_headings(lines).values())
    # Prefer the deepest supported level so a document title (#) does not become
    # the only section boundary; fall back to shallower headings when absent.
    for level in range(_SPLIT_LEVEL_CAP, 0, -1):
        if level in levels:
            return level
    return _SPLIT_LEVEL_CAP


def split_sections(text: str) -> list[str]:
    """Split at the deepest heading level up to two; fences never split."""
    lines = text.splitlines()
    level = _split_level(lines)
    sections: list[list[str]] = []
    current: list[str] = []
    headings = _headings(lines)
    for index, line in enumerate(lines):
        # Split on the chosen level only: a document title (#) above the chosen
        # section level stays attached to the first section.
        if headings.get(index) == level:
            if any(part.strip() for part in current):
                sections.append(current)
            current = [line]
        else:
            current.append(line)
    if any(part.strip() for part in current):
        sections.append(current)
    merged = ["\n".join(section).strip() for section in sections]
    return [section for section in merged if section]


def clean_markdown_texts(parsed: ParsedPdfDocument) -> list[tuple[int, str]]:
    """Keep authored line structure (tables, lists); only normalize spacing."""
    cleaned: list[tuple[int, str]] = []
    for page in parsed.pages:
        text = page.text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
        text = "\n".join(line.rstrip() for line in text.splitlines())
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if text:
            cleaned.append((page.page_number, text))
    return cleaned


def parse_markdown(
    path: str | Path, *, source_path: str | None = None
) -> ParsedPdfDocument:
    """Read a local Markdown file; `source_path` is its registry identifier."""
    md_path = Path(path)
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file does not exist: {md_path}")
    if md_path.suffix.lower() not in {".md", ".markdown"}:
        raise ValueError(f"Expected a Markdown file: {md_path}")

    metadata, body = split_front_matter(md_path.read_text(encoding="utf-8"))
    sections = split_sections(body)
    warnings: list[str] = []
    if not sections:
        warnings.append("empty_document")

    pages: list[PdfPage] = []
    for index, section in enumerate(sections, 1):
        pages.append(
            PdfPage(
                page_number=index,
                width=_WIDTH,
                height=_HEIGHT,
                text=section,
                char_count=len(section),
                blocks=[
                    PdfTextBlock(
                        block_number=0,
                        block_type=0,
                        bbox=(0.0, _BLOCK_Y0, _WIDTH, _BLOCK_Y1),
                        text=section,
                    )
                ],
                image_count=0,
                warnings=[],
            )
        )

    return ParsedPdfDocument(
        source_path=source_path if source_path is not None else md_path.name,
        file_name=md_path.name,
        page_count=len(pages),
        metadata={
            **metadata,
            "format": "markdown",
            "section_split_level": _split_level(body.splitlines()),
            "section_count": len(pages),
        },
        pages=pages,
        warnings=warnings,
    )
