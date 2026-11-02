"""Page-level OCR planning and execution for scanned or mixed PDFs.

OCR is deliberately explicit: a missing tool or language raises instead of
silently returning empty text.  Every OCR asset records the tool, languages,
DPI and that manual review is still required; OCR output never claims to be
verified evidence by itself.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from accelerator_rag.corpus.parsed_document import (
    ParsedBlock,
    ParsedDocument,
    SourcePosition,
    make_block_id,
)
from accelerator_rag.domain.position import BlockType, PositionKind


@dataclass(frozen=True)
class OCRToolStatus:
    available: bool
    executable: str
    version: str
    languages: tuple[str, ...]
    reason: str = ""


class OCRUnavailable(RuntimeError):
    """OCR cannot run in this environment; the message names the missing piece."""


@dataclass(frozen=True)
class PageOCRPlan:
    page_number: int
    char_count: int
    image_count: int
    recommended: bool
    reason: str


def detect_ocr_tool() -> OCRToolStatus:
    """Detect tesseract without installing, downloading or guessing."""

    executable = shutil.which("tesseract")
    if executable is None:
        return OCRToolStatus(
            False, "", "", (), "tesseract executable not found on PATH"
        )
    try:
        version = subprocess.run(
            [executable, "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout.splitlines()
        version_text = version[0].strip() if version else "unknown"
        languages_output = subprocess.run(
            [executable, "--list-langs"],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout.splitlines()
        languages = tuple(
            sorted(
                line.strip()
                for line in languages_output
                if line.strip() and "List of available languages" not in line
            )
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return OCRToolStatus(
            False, executable, "", (), f"tesseract detection failed: {exc}"
        )
    return OCRToolStatus(True, executable, version_text, languages)


def plan_pdf_ocr(path: str | Path, *, min_chars: int = 50) -> list[PageOCRPlan]:
    """Classify every page; only pages with an image and little text are OCR'd."""

    import pymupdf

    if type(min_chars) is not int or min_chars < 1:
        raise ValueError("min_chars must be a positive integer")
    plans = []
    with pymupdf.open(path) as pdf:
        for page_number, page in enumerate(pdf, 1):
            text = page.get_text("text").strip()
            images = len(page.get_images(full=True))
            if not text and images:
                reason, recommended = "no_text_layer", True
            elif not text and not images:
                reason, recommended = "blank_page", False
            elif len(text) < min_chars and images:
                reason, recommended = "sparse_text", True
            elif len(text) < min_chars:
                reason, recommended = "short_text_no_image", False
            else:
                reason, recommended = "has_text_layer", False
            plans.append(
                PageOCRPlan(
                    page_number,
                    len(text),
                    images,
                    recommended,
                    reason,
                )
            )
    return plans


def _ocr_page(
    png_path: Path,
    *,
    executable: str,
    languages: tuple[str, ...],
    psm: int,
    timeout: int,
) -> str:
    output_base = png_path.with_suffix("")
    command = [
        executable,
        str(png_path),
        str(output_base),
        "-l",
        "+".join(languages),
        "--psm",
        str(psm),
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise OCRUnavailable(
            "tesseract failed with exit "
            f"{completed.returncode}: {completed.stderr.strip()[:500]}"
        )
    text_path = output_base.with_suffix(".txt")
    if not text_path.is_file():
        raise OCRUnavailable(f"tesseract produced no text file: {text_path}")
    return text_path.read_text(encoding="utf-8", errors="replace").strip()


def ocr_pdf_pages(
    path: str | Path,
    *,
    revision_id: str,
    asset_id: str,
    source_path: str,
    title: str,
    pages: list[int] | None = None,
    languages: tuple[str, ...] = ("chi_sim", "eng"),
    dpi: int = 300,
    psm: int = 6,
    timeout: int = 120,
    min_chars: int = 50,
    workers: int = 4,
) -> ParsedDocument:
    """OCR selected pages into a PDF-page-positioned ParsedDocument.

    The caller must still review critical numbers, units and comparison signs
    against the original page.  This function does not repair or infer them.
    """

    import pymupdf

    status = detect_ocr_tool()
    if not status.available:
        raise OCRUnavailable(status.reason or "OCR tool unavailable")
    missing_languages = sorted(set(languages) - set(status.languages))
    if missing_languages:
        raise OCRUnavailable(
            "requested OCR languages are not installed: "
            + ", ".join(missing_languages)
            + "; available: "
            + ", ".join(status.languages)
        )
    if type(dpi) is not int or not 100 <= dpi <= 600:
        raise ValueError("dpi must be between 100 and 600")
    if type(psm) is not int or not 0 <= psm <= 13:
        raise ValueError("psm must be between 0 and 13")
    if type(workers) is not int or not 1 <= workers <= 32:
        raise ValueError("workers must be between 1 and 32")
    pdf_path = Path(path)
    plans = plan_pdf_ocr(pdf_path, min_chars=min_chars)
    by_page = {plan.page_number: plan for plan in plans}
    selected = (
        sorted(set(pages))
        if pages is not None
        else [plan.page_number for plan in plans if plan.recommended]
    )
    if not selected:
        raise ValueError("no pages selected or recommended for OCR")
    unknown = [page for page in selected if page not in by_page]
    if unknown:
        raise ValueError(f"pages outside the PDF: {unknown}")

    blocks: list[ParsedBlock] = []
    warnings: list[str] = []
    with tempfile.TemporaryDirectory(prefix="kb2-ocr-") as tmp:
        tmp_path = Path(tmp)
        jobs: list[tuple[int, Path]] = []
        with pymupdf.open(pdf_path) as pdf:
            for page_number in selected:
                page = pdf[page_number - 1]
                png_path = tmp_path / f"page-{page_number:04d}.png"
                pixmap = page.get_pixmap(dpi=dpi)
                pixmap.save(png_path)
                jobs.append((page_number, png_path))

        def run(job: tuple[int, Path]) -> tuple[int, str]:
            page_number, png_path = job
            return page_number, _ocr_page(
                png_path,
                executable=status.executable,
                languages=languages,
                psm=psm,
                timeout=timeout,
            )

        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(run, jobs))
        for page_number, text in results:
            if not text:
                warnings.append(f"empty_ocr_page:{page_number}")
                continue
            position = SourcePosition(
                kind=PositionKind.PDF_PAGE.value,
                start=page_number,
                end=page_number,
                label=f"page-{page_number}",
                locator=(("ocr_dpi", str(dpi)), ("ocr_psm", str(psm))),
            )
            ordinal = len(blocks)
            blocks.append(
                ParsedBlock(
                    block_id=make_block_id(
                        revision_id,
                        asset_id,
                        ordinal,
                        BlockType.PARAGRAPH.value,
                        position,
                        text,
                    ),
                    block_type=BlockType.PARAGRAPH.value,
                    text=text,
                    position=position,
                    metadata=(
                        ("ocr", "tesseract"),
                        ("ocr_languages", "+".join(languages)),
                        ("manual_review_required", "true"),
                    ),
                )
            )
    if not blocks:
        warnings.append("ocr_produced_no_text")
    profile = (
        f"{status.version}; languages={','.join(languages)}; dpi={dpi}; psm={psm}"
    )
    return ParsedDocument(
        revision_id=revision_id,
        asset_id=asset_id,
        source_path=source_path,
        source_format="pdf",
        title=title,
        blocks=tuple(blocks),
        warnings=tuple(warnings),
        metadata=(
            ("ocr_tool", status.executable),
            ("ocr_languages", "+".join(languages)),
            ("ocr_dpi", str(dpi)),
            ("ocr_psm", str(psm)),
            ("ocr_page_count", str(len(selected))),
            ("manual_review_required", "true"),
        ),
        parser_profile="tesseract-pdf-v1",
        ocr_profile=profile,
    )


def ocr_plan_digest(plans: list[PageOCRPlan]) -> str:
    payload = json.dumps(
        [
            [plan.page_number, plan.char_count, plan.image_count, plan.reason]
            for plan in plans
        ],
        sort_keys=True,
    )
    return sha256(payload.encode()).hexdigest()
