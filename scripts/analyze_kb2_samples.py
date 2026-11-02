#!/usr/bin/env python3
"""Measure representative KB2 inputs without producing retrieval evidence.

This survey answers K2 planning questions: does the format open, how long does
it take, how many structured blocks/tables/slides exist, and which pages carry
no text layer.  It never writes to the corpus, registry, index or release.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import time


def _seconds(start: float) -> float:
    return round(time.perf_counter() - start, 3)


def _peak_mb() -> float:
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


def analyze_docx(path: Path) -> dict:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    started = time.perf_counter()
    document = Document(path)
    paragraphs = tables = headings = formulas = 0
    chars = 0
    for element in document.element.body.iterchildren():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(element, document)
            text = paragraph.text.strip()
            paragraphs += 1
            chars += len(text)
            style = (paragraph.style.name or "").casefold()
            if style.startswith("heading") or style.startswith("标题"):
                headings += 1
            if "m:oMath" in element.xml:
                formulas += 1
        elif tag == "tbl":
            table = Table(element, document)
            tables += 1
            for row in table.rows:
                for cell in row.cells:
                    chars += len(cell.text)
    return {
        "format": "docx",
        "status": "ok",
        "seconds": _seconds(started),
        "peak_rss_mb": _peak_mb(),
        "paragraphs": paragraphs,
        "tables": tables,
        "headings": headings,
        "formula_paragraphs": formulas,
        "inline_shapes": len(document.inline_shapes),
        "sections": len(document.sections),
        "chars": chars,
        "core_title": (document.core_properties.title or "")[:200],
    }


def analyze_pptx(path: Path) -> dict:
    from pptx import Presentation

    started = time.perf_counter()
    presentation = Presentation(path)
    slides = len(presentation.slides)
    shapes = tables = notes = text_chars = 0
    for slide in presentation.slides:
        for shape in slide.shapes:
            shapes += 1
            if getattr(shape, "has_text_frame", False):
                text_chars += len(shape.text_frame.text)
            if getattr(shape, "has_table", False):
                tables += 1
                for row in shape.table.rows:
                    for cell in row.cells:
                        text_chars += len(cell.text)
        if slide.has_notes_slide:
            text = slide.notes_slide.notes_text_frame.text
            if text.strip():
                notes += 1
                text_chars += len(text)
    return {
        "format": "pptx",
        "status": "ok",
        "seconds": _seconds(started),
        "peak_rss_mb": _peak_mb(),
        "slides": slides,
        "shapes": shapes,
        "tables": tables,
        "notes_slides": notes,
        "chars": text_chars,
    }


def analyze_xlsx(path: Path) -> dict:
    from openpyxl import load_workbook

    started = time.perf_counter()
    workbook = load_workbook(path, read_only=True, data_only=False)
    sheets = []
    total_cells = formulas = 0
    for sheet in workbook.worksheets:
        rows = columns = nonempty = formula_count = 0
        for row in sheet.iter_rows(values_only=True):
            rows += 1
            columns = max(columns, len(row))
            for value in row:
                if value is None or value == "":
                    continue
                nonempty += 1
                if isinstance(value, str) and value.startswith("="):
                    formula_count += 1
        sheets.append(
            {
                "name": sheet.title,
                "rows": rows,
                "columns": columns,
                "nonempty_cells": nonempty,
                "formula_cells": formula_count,
                "max_row": sheet.max_row,
                "max_column": sheet.max_column,
            }
        )
        total_cells += nonempty
        formulas += formula_count
    workbook.close()
    return {
        "format": "xlsx",
        "status": "ok",
        "seconds": _seconds(started),
        "peak_rss_mb": _peak_mb(),
        "sheets": sheets,
        "nonempty_cells": total_cells,
        "formula_cells": formulas,
    }


def analyze_pdf(path: Path) -> dict:
    import pymupdf

    started = time.perf_counter()
    with pymupdf.open(path) as pdf:
        pages = len(pdf)
        empty = 0
        chars = 0
        images = 0
        for page in pdf:
            text = page.get_text("text").strip()
            chars += len(text)
            if not text:
                empty += 1
            images += len(page.get_images(full=True))
    return {
        "format": "pdf",
        "status": "ok",
        "seconds": _seconds(started),
        "peak_rss_mb": _peak_mb(),
        "pages": pages,
        "pages_without_text": empty,
        "chars": chars,
        "images": images,
    }


ANALYZERS = {
    ".docx": analyze_docx,
    ".pptx": analyze_pptx,
    ".xlsx": analyze_xlsx,
    ".pdf": analyze_pdf,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = []
    for raw in args.paths:
        path = Path(raw)
        result = {"path": str(path), "size_bytes": path.stat().st_size}
        analyzer = ANALYZERS.get(path.suffix.lower())
        if analyzer is None:
            result.update(status="unsupported", format=path.suffix.lower())
        else:
            try:
                result.update(analyzer(path))
            except Exception as exc:  # survey reports failures, never hides them
                result.update(
                    status="failed",
                    error_type=type(exc).__name__,
                    error=str(exc)[:500],
                )
        results.append(result)
    payload = {
        "kind": "kb2-format-sample-survey",
        "results": results,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
