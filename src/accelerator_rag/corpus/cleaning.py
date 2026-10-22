"""Retrieval-only cleanup. Raw parser blocks and their coordinates stay intact."""

from collections import Counter
import re

from accelerator_rag.corpus.pdf_parser import (
    ParsedPdfDocument,
    PdfPage,
    PdfTextBlock,
    _looks_two_column,
)

# Conservative page zones, expressed as fractions of physical page dimensions.
TOP_MARGIN = 0.065
BOTTOM_MARGIN = 0.93
SIDE_MARGIN = 0.10
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:[-.:][A-Za-z0-9_]+)*")
PUBLICATION_PATTERN = re.compile(r"\b(?:ISBN|ISSN)\s*:?\s*\d", re.I)
RIGHTS_PATTERN = re.compile(r"copyright|©|\blicen[cs]e\b|\ball rights reserved\b", re.I)
PAGE_NUMBER_PATTERN = re.compile(r"^\d+$", re.M)
RUNNING_CODE_PATTERN = re.compile(r"^[A-Z]{1,8}\d{1,8}$", re.M)
_ABSTRACT = re.compile(r"^(?:abstract|摘要)(?:\s|[:：]|$)", re.I)
_REFERENCES = re.compile(r"^(?:references|bibliography|参考文献)\s*$", re.I)
_REFERENCE_ENTRY = re.compile(r"^\s*(?:\[\d+\]|\d+\.)\s+")


def normalize_text(text: str, *, vocabulary: frozenset[str] = frozenset()) -> str:
    """Repair wrapped words only with lexical evidence from this document.

    Ambiguous compounds retain their hyphen. An intact hyphenated occurrence
    takes precedence over an intact concatenated occurrence. Ordinary inline
    technical hyphens never match the wrapping rule.
    """
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")

    def repair(match: re.Match[str]) -> str:
        head, tail = match.groups()
        combined = head + tail
        compound = head + "-" + tail
        if (
            tail[0].islower()
            and combined.casefold().rstrip(".:") in vocabulary
            and compound.casefold().rstrip(".:") not in vocabulary
        ):
            return combined
        return compound

    text = re.sub(r"([A-Za-z0-9_.:]+)-[ \t]*\n\s*([A-Za-z0-9_.:]+)", repair, text)
    text = re.sub(r"[^\S\n]+", " ", text)
    paragraphs = re.split(r"\n\s*\n", text)
    return "\n\n".join(" ".join(p.split()) for p in paragraphs if p.strip())


def _edge(block: PdfTextBlock, page: PdfPage) -> bool:
    x0, y0, x1, y1 = block.bbox
    vertical_side = (
        x1 <= page.width * SIDE_MARGIN or x0 >= page.width * (1 - SIDE_MARGIN)
    ) and y1 - y0 > 3 * (x1 - x0)
    return (
        y1 <= page.height * TOP_MARGIN
        or y0 >= page.height * BOTTOM_MARGIN
        or vertical_side
    )


def _signature(text: str) -> str:
    # Page numbers and running publication identifiers may change between pages.
    return re.sub(r"\d+", "#", " ".join(text.casefold().split()))


def _running_signature(text: str) -> str:
    text = " ".join(text.casefold().split())
    return "#" if text.isdecimal() else text


def _body_blocks(
    page: PdfPage, repeated_edges: set[str], running: set[tuple[str, int]]
) -> list[PdfTextBlock]:
    blocks = []
    for block in page.blocks:
        if block.block_type != 0 or not block.text.strip():
            continue
        if (
            _running_signature(block.text),
            round(block.bbox[1] / page.height * 100),
        ) in running:
            continue
        if _edge(block, page):
            text = block.text.strip()
            if (
                _signature(text) in repeated_edges
                or PUBLICATION_PATTERN.search(text)
                or RIGHTS_PATTERN.search(text)
                or PAGE_NUMBER_PATTERN.fullmatch(text)
                or RUNNING_CODE_PATTERN.fullmatch(text)
            ):
                continue
        # Author footnotes separated by a rule, rather than ordinary body emails.
        if (
            block.bbox[1] >= page.height * 0.85
            and re.search(r"[_─—-]{8,}", block.text)
            and "@" in block.text
        ):
            continue
        blocks.append(block)
    return order_body_blocks(blocks, page.width)


def clean_page_texts(parsed: ParsedPdfDocument) -> list[tuple[int, str]]:
    """Clean page-local evidence with document-level repetition and vocabulary.

    A first-page abstract provides a conservative boundary for academic title /
    author front matter. Explicit final reference lists are excluded only when
    followed by multiple numbered entries. No publisher or file-name rules.
    """
    frequencies: Counter[str] = Counter()
    for page in parsed.pages:
        frequencies.update({_signature(b.text) for b in page.blocks if _edge(b, page)})
    repeated_edges = {key for key, count in frequencies.items() if count >= 2}
    # Many-page repetition at stable positions, including inset book margins.
    # Exact text signatures avoid conflating changing section titles. Digits are
    # masked only for isolated printed page numbers. Require both margin band
    # and >= 6 pages / 10% of document to protect occasional chapter headings.
    positions: dict[tuple[str, int], set[int]] = {}
    for page in parsed.pages:
        for b in page.blocks:
            y = b.bbox[1] / page.height
            if (
                b.block_type == 0
                and len(b.text.strip()) <= 110
                and (y < 0.18 or y > 0.82)
            ):
                key = (_running_signature(b.text), round(y * 100))
                positions.setdefault(key, set()).add(page.page_number)
    running = {
        key
        for key, pages in positions.items()
        if len(pages) >= max(6, len(parsed.pages) * 0.1)
    }
    vocabulary = frozenset(
        word.casefold()
        for page in parsed.pages
        for block in page.blocks
        for word in _WORD.findall(block.text)
    )
    result = []
    for index, page in enumerate(parsed.pages):
        blocks = _body_blocks(page, repeated_edges, running)
        if index == 0:
            for offset, block in enumerate(blocks):
                if (
                    _ABSTRACT.match(block.text.strip())
                    and block.bbox[1] < page.height * 0.35
                    and all(len(b.text) < 500 for b in blocks[:offset])
                ):
                    blocks = blocks[offset:]
                    break
        if index == len(parsed.pages) - 1:
            for offset, block in enumerate(blocks):
                if (
                    _REFERENCES.fullmatch(block.text.strip())
                    and sum(
                        bool(_REFERENCE_ENTRY.match(b.text))
                        for b in blocks[offset + 1 :]
                    )
                    >= 2
                ):
                    blocks = blocks[:offset]
                    break
        # Keep raw line endings until after joining: adjacent blocks can split
        # a word at a column boundary (e.g. hun- / dreds).
        text = normalize_text(
            "\n\n".join(b.text.strip() for b in blocks), vocabulary=vocabulary
        )
        result.append((page.page_number, text))
    return result


def order_body_blocks(
    blocks: list[PdfTextBlock],
    page_width: float,
) -> list[PdfTextBlock]:
    """Basic two-column order with spanning blocks as vertical separators.

    This is a geometric heuristic, not general layout reconstruction. Retain
    marginal text at the end rather than inserting it into a body paragraph.
    """
    if not _looks_two_column(blocks, page_width):
        return blocks
    midpoint = page_width / 2
    margins = [
        b
        for b in blocks
        if (b.bbox[2] < page_width * 0.1 or b.bbox[0] > page_width * 0.9)
        and b.bbox[3] - b.bbox[1] > (b.bbox[2] - b.bbox[0]) * 3
    ]
    body = [b for b in blocks if b not in margins]
    spans = sorted(
        [b for b in body if b.bbox[0] < midpoint < b.bbox[2]], key=lambda b: b.bbox[1]
    )
    remaining = [b for b in body if b not in spans]
    ordered = []
    for span in spans:
        band = [b for b in remaining if b.bbox[1] < span.bbox[1]]
        ordered.extend(sorted(band, key=lambda b: (b.bbox[0] >= midpoint, b.bbox[1])))
        remaining = [b for b in remaining if b not in band]
        ordered.append(span)
    ordered.extend(sorted(remaining, key=lambda b: (b.bbox[0] >= midpoint, b.bbox[1])))
    return ordered + margins
