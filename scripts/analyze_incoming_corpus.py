#!/usr/bin/env python3
"""Inventory an untrusted incoming document batch.

Reads only; writes a JSON report to stdout.  The target directory is passed as
an argument and is treated purely as data (no imports, no execution from it).

Usage:
    python scripts/analyze_incoming_corpus.py <root> > inventory.json
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import zipfile
from pathlib import Path

CJK = re.compile(r"[一-鿿]")
WORDLIKE = re.compile(r"[A-Za-z0-9_\-./]+")

DOCX_EXT = {".docx"}
PPTX_EXT = {".pptx"}
XLSX_EXT = {".xlsx"}
PDF_EXT = {".pdf"}
LEGACY_DOC_EXT = {".doc", ".ppt", ".xls"}


def sha256(path: Path, limit: int = 64 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        remaining = limit
        while remaining > 0:
            block = fh.read(min(1 << 20, remaining))
            if not block:
                break
            h.update(block)
            remaining -= len(block)
    return h.hexdigest()


def text_stats(text: str) -> dict:
    text = text or ""
    cjk = len(CJK.findall(text))
    latin_words = len(WORDLIKE.findall(text))
    return {
        "chars": len(text),
        "cjk_chars": cjk,
        "latin_words": latin_words,
        "approx_tokens": int(cjk * 0.7 + latin_words * 1.3),
        "head": re.sub(r"\s+", " ", text[:400]).strip(),
    }


def docx_text(path: Path) -> dict:
    import docx  # type: ignore

    d = docx.Document(str(path))
    parts = [p.text for p in d.paragraphs]
    for table in d.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    text = "\n".join(parts)
    return {"text": text, "paragraphs": len(d.paragraphs), "tables": len(d.tables)}


def pptx_text(path: Path) -> dict:
    from pptx import Presentation  # type: ignore

    prs = Presentation(str(path))
    parts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False):
                parts.append(shape.text_frame.text)
    return {"text": "\n".join(parts), "slides": len(prs.slides)}


def xlsx_text(path: Path) -> dict:
    import openpyxl  # type: ignore

    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    parts = []
    for ws in wb.worksheets:
        parts.append(ws.title)
        for row in ws.iter_rows(values_only=True):
            parts.extend(str(c) for c in row if c is not None)
    return {"text": "\n".join(parts), "sheets": len(wb.worksheets)}


def pdf_text(path: Path) -> dict:
    import pymupdf  # type: ignore  # noqa: F401

    import fitz  # type: ignore

    doc = fitz.open(str(path))
    pages = doc.page_count
    per_page = []
    parts = []
    for page in doc:
        t = page.get_text()
        per_page.append(len(t))
        parts.append(t)
    doc.close()
    empty = sum(1 for n in per_page if n < 20)
    return {
        "text": "\n".join(parts),
        "pages": pages,
        "pages_without_text": empty,
        "chars_per_page": round(sum(per_page) / pages, 1) if pages else 0,
    }


def archive_members(path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(path) as zf:
            return zf.namelist()
    except Exception:
        return []


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    records = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        ext = path.suffix.lower()
        rec = {
            "path": rel,
            "name": path.name,
            "ext": ext,
            "bytes": path.stat().st_size,
            "sha256_64m": sha256(path),
        }
        t0 = time.time()
        try:
            if ext in DOCX_EXT:
                info = docx_text(path)
                rec.update(kind="docx", paragraphs=info["paragraphs"], tables=info["tables"])
            elif ext in PPTX_EXT:
                info = pptx_text(path)
                rec.update(kind="pptx", slides=info["slides"])
            elif ext in XLSX_EXT:
                info = xlsx_text(path)
                rec.update(kind="xlsx", sheets=info["sheets"])
            elif ext in PDF_EXT:
                info = pdf_text(path)
                rec.update(
                    kind="pdf",
                    pages=info["pages"],
                    pages_without_text=info["pages_without_text"],
                    chars_per_page=info["chars_per_page"],
                )
            elif ext in LEGACY_DOC_EXT:
                rec.update(kind="legacy", note="not parsed in this pass")
                info = {"text": ""}
            elif ext == ".zip":
                members = archive_members(path)
                rec.update(kind="zip", members=len(members), member_sample=members[:10])
                info = {"text": ""}
            elif ext == ".rar":
                rec.update(kind="rar", note="needs unrar")
                info = {"text": ""}
            else:
                rec.update(kind="other")
                info = {"text": ""}
            rec.update(text_stats(info.get("text", "")))
        except Exception as exc:  # keep going; record why
            rec.update(kind="error", error=f"{type(exc).__name__}: {exc}")
            rec.update(text_stats(""))
        rec["seconds"] = round(time.time() - t0, 2)
        records.append(rec)
        print(f"[{len(records):3d}] {rel}  ({rec.get('chars', 0)} chars, {rec['seconds']}s)",
              file=sys.stderr)

    json.dump(records, sys.stdout, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
