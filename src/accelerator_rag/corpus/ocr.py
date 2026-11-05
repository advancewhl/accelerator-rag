"""Page-level OCR planning and execution for scanned or mixed PDFs.

OCR is deliberately explicit: a missing tool or language raises instead of
silently returning empty text.  Every OCR asset records the tool, languages,
DPI and that manual review is still required; OCR output never claims to be
verified evidence by itself.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import csv
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import tempfile

from accelerator_rag.corpus.parsed_document import (
    ParsedBlock,
    ParsedDocument,
    SourcePosition,
    TableData,
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
    image_area_ratio: float = 0.0
    mixed_candidate: bool = False


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
            ratio = _image_area_ratio(page)
            mixed = False
            if not text and images:
                reason, recommended = "no_text_layer", True
            elif not text and not images:
                reason, recommended = "blank_page", False
            elif len(text) < min_chars and images:
                reason, recommended = "sparse_text", True
            elif len(text) < min_chars:
                reason, recommended = "short_text_no_image", False
            elif ratio >= 0.15:
                # Text layer is usable, but a large raster region may still
                # contain the real parameter table or diagram.
                reason, recommended = "mixed_text_and_image", False
                mixed = True
            else:
                reason, recommended = "has_text_layer", False
            plans.append(
                PageOCRPlan(
                    page_number,
                    len(text),
                    images,
                    recommended,
                    reason,
                    ratio,
                    mixed,
                )
            )
    return plans


def _image_rects(page) -> list:
    """Unique image placements; get_images may repeat one xref per placement."""

    rects = []
    seen_rects = set()
    for item in page.get_images(full=True):
        xref = item[0]
        try:
            candidates = page.get_image_rects(xref)
        except (RuntimeError, ValueError, TypeError):
            continue
        for rect in candidates:
            clip = rect & page.rect
            key = (
                round(clip.x0),
                round(clip.y0),
                round(clip.x1),
                round(clip.y1),
            )
            if key in seen_rects:
                continue
            seen_rects.add(key)
            if clip.width > 0 and clip.height > 0:
                rects.append(clip)
    return rects


def _merge_rects(rects: list) -> list:
    """Merge overlapping image placements so one logo is not counted twice."""

    merged = list(rects)
    changed = True
    while changed:
        changed = False
        for first in range(len(merged)):
            for second in range(first + 1, len(merged)):
                a, b = merged[first], merged[second]
                if (
                    max(a.x0, b.x0) < min(a.x1, b.x1)
                    and max(a.y0, b.y0) < min(a.y1, b.y1)
                ):
                    merged[first] = type(a)(
                        min(a.x0, b.x0),
                        min(a.y0, b.y0),
                        max(a.x1, b.x1),
                        max(a.y1, b.y1),
                    )
                    merged.pop(second)
                    changed = True
                    break
            if changed:
                break
    return merged


def _image_area_ratio(page) -> float:
    page_area = abs(page.rect.width * page.rect.height)
    if not page_area:
        return 0.0
    area = sum(
        max(0.0, rect.width) * max(0.0, rect.height)
        for rect in _merge_rects(_image_rects(page))
    )
    return min(1.0, area / page_area)


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


def _ocr_page_words(
    png_path: Path,
    *,
    executable: str,
    languages: tuple[str, ...],
    psm: int,
    timeout: int,
) -> list[dict]:
    """Run tesseract TSV so word coordinates can rebuild table rows."""

    output_base = png_path.with_suffix("")
    command = [
        executable,
        str(png_path),
        str(output_base),
        "-l",
        "+".join(languages),
        "--psm",
        str(psm),
        "tsv",
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        return []
    tsv_path = output_base.with_suffix(".tsv")
    if not tsv_path.is_file():
        return []
    words = []
    with tsv_path.open(encoding="utf-8", errors="replace", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t", quoting=csv.QUOTE_NONE):
            text = (row.get("text") or "").strip()
            if not text:
                continue
            try:
                confidence = float(row.get("conf") or -1)
                left = int(row.get("left") or 0)
                top = int(row.get("top") or 0)
                width = int(row.get("width") or 0)
                height = int(row.get("height") or 0)
                line = int(row.get("line_num") or 0)
                block = int(row.get("block_num") or 0)
                paragraph = int(row.get("par_num") or 0)
            except ValueError:
                continue
            words.append(
                {
                    "text": text,
                    "conf": confidence,
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height,
                    "line": (block, paragraph, line),
                }
            )
    return words


def _words_text(words: list[dict]) -> str:
    lines: dict[tuple[int, int, int], list[dict]] = {}
    for word in words:
        lines.setdefault(word["line"], []).append(word)
    values = []
    for key in sorted(lines):
        ordered = sorted(lines[key], key=lambda item: item["left"])
        values.append(" ".join(item["text"] for item in ordered))
    return "\n".join(values).strip()


def _cluster_centers(values: list[float], tolerance: float) -> list[float]:
    centers = []
    for value in sorted(values):
        if not centers or value - centers[-1] > tolerance:
            centers.append(value)
        else:
            centers[-1] = (centers[-1] + value) / 2
    return centers


def _line_cells(line: list[dict], tolerance: float) -> list[dict]:
    """Split one OCR line into cell spans at large horizontal gaps."""

    cells = []
    current = []
    previous_right = None
    for word in sorted(line, key=lambda item: item["left"]):
        left = word["left"]
        if (
            current
            and previous_right is not None
            and left - previous_right > tolerance * 1.5
        ):
            cells.append(
                {
                    "text": " ".join(item["text"] for item in current),
                    "left": current[0]["left"],
                    "right": max(
                        item["left"] + item["width"] for item in current
                    ),
                }
            )
            current = []
        current.append(word)
        previous_right = max(
            previous_right or 0, word["left"] + word["width"]
        )
    if current:
        cells.append(
            {
                "text": " ".join(item["text"] for item in current),
                "left": current[0]["left"],
                "right": max(item["left"] + item["width"] for item in current),
            }
        )
    for cell in cells:
        cell["center"] = (cell["left"] + cell["right"]) / 2
    return cells


def reconstruct_ocr_table(
    words: list[dict], *, min_rows: int = 3, min_columns: int = 2
) -> TableData | None:
    """Conservative row/column recovery; returns None when the layout is prose.

    Lines are split into cells at large word gaps (not by global word-center
    clustering, which splits multi-word cells and drops empty cells).  Rows
    with fewer cells are aligned to the median column anchors so blank cells
    stay blank instead of deleting the row.
    """

    reliable = [word for word in words if word["conf"] >= 30]
    if len(reliable) < min_rows * min_columns:
        return None
    lines: dict[tuple[int, int, int], list[dict]] = {}
    for word in reliable:
        lines.setdefault(word["line"], []).append(word)
    ordered_lines = [lines[key] for key in sorted(lines)]
    if len(ordered_lines) < min_rows:
        return None
    heights = [word["height"] for word in ordered_lines[0] if word["height"] > 0]
    if not heights:
        heights = [word["height"] for word in reliable if word["height"] > 0]
    tolerance = (
        max(10.0, statistics.median(heights) * 1.2) if heights else 10.0
    )
    cell_lines = [_line_cells(line, tolerance) for line in ordered_lines]
    counts = [len(cells) for cells in cell_lines if 2 <= len(cells) <= 12]
    if not counts:
        return None
    column_count = statistics.mode(counts)
    if not min_columns <= column_count <= 12:
        return None
    anchor_lines = [cells for cells in cell_lines if len(cells) == column_count]
    if len(anchor_lines) < 2:
        return None
    anchors = [
        statistics.median(cells[index]["center"] for cells in anchor_lines)
        for index in range(column_count)
    ]
    rows = []
    for cells in cell_lines:
        if len(cells) < 2:
            # A single-cell line is prose or a title, not a table row.
            continue
        if len(cells) == column_count:
            rows.append(tuple(cell["text"].strip() for cell in cells))
            continue
        row = [""] * column_count
        for cell in cells:
            index = min(
                range(column_count),
                key=lambda item: abs(anchors[item] - cell["center"]),
            )
            row[index] = (row[index] + " " + cell["text"]).strip()
        rows.append(tuple(row))
    if len(rows) < min_rows:
        return None
    nonempty = sum(bool(cell.strip()) for row in rows for cell in row)
    if nonempty / (len(rows) * column_count) < 0.30:
        return None
    letters = []
    for index in range(1, column_count + 1):
        value = index
        text = ""
        while value:
            value, remainder = divmod(value - 1, 26)
            text = chr(65 + remainder) + text
        letters.append(text)
    return TableData(
        rows=tuple(rows),
        header_rows=1,
        column_letters=tuple(letters),
        merged_ranges=(),
    )


def ocr_image_file(
    path: str | Path,
    *,
    languages: tuple[str, ...] = ("chi_sim", "eng"),
    psm: int = 6,
    timeout: int = 60,
) -> str:
    """OCR one image file; used for extracted DOCX/PPTX pictures."""

    image_path = Path(path)
    if not image_path.is_file():
        raise FileNotFoundError(f"image does not exist: {image_path}")
    if type(psm) is not int or not 0 <= psm <= 13:
        raise ValueError("psm must be between 0 and 13")
    status = detect_ocr_tool()
    if not status.available:
        raise OCRUnavailable(status.reason or "OCR tool unavailable")
    missing = sorted(set(languages) - set(status.languages))
    if missing:
        raise OCRUnavailable(
            "requested OCR languages are not installed: "
            + ", ".join(missing)
        )
    with tempfile.TemporaryDirectory(prefix="kb2-image-ocr-") as tmp:
        # Tesseract writes a sibling .txt; keep it out of the release media dir.
        copy = Path(tmp) / image_path.name
        shutil.copy2(image_path, copy)
        return _ocr_page(
            copy,
            executable=status.executable,
            languages=languages,
            psm=psm,
            timeout=timeout,
        )


def _large_image_rects(page) -> list:
    """Distinct, merged image regions worth OCR on a mixed page."""

    page_area = abs(page.rect.width * page.rect.height) or 1.0
    rects = [
        rect
        for rect in _merge_rects(_image_rects(page))
        if 0.03
        <= rect.width * rect.height / page_area
        <= 0.95
    ]
    return sorted(rects, key=lambda item: (item.y0, item.x0))


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
        jobs = []
        with pymupdf.open(pdf_path) as pdf:
            for page_number in selected:
                page = pdf[page_number - 1]
                plan = by_page[page_number]
                if plan.mixed_candidate:
                    regions = _large_image_rects(page)
                    if not regions:
                        # Do not turn a mixed page into a duplicate whole-page
                        # OCR just because no image region passed the filter.
                        warnings.append(f"mixed_page_no_region:{page_number}")
                        continue
                    for index, rect in enumerate(regions, 1):
                        png_path = (
                            tmp_path
                            / f"page-{page_number:04d}-region-{index:02d}.png"
                        )
                        page.get_pixmap(clip=rect, dpi=dpi).save(png_path)
                        jobs.append((page_number, png_path, rect, index))
                    continue
                png_path = tmp_path / f"page-{page_number:04d}.png"
                page.get_pixmap(dpi=dpi).save(png_path)
                jobs.append((page_number, png_path, None, 0))

        def run(job):
            page_number, png_path, rect, index = job
            try:
                words = _ocr_page_words(
                    png_path,
                    executable=status.executable,
                    languages=languages,
                    psm=psm,
                    timeout=timeout,
                )
                text = _words_text(words)
                if not text:
                    text = _ocr_page(
                        png_path,
                        executable=status.executable,
                        languages=languages,
                        psm=psm,
                        timeout=timeout,
                    )
                return page_number, rect, index, text, words, ""
            except (
                OSError,
                RuntimeError,
                ValueError,
                subprocess.SubprocessError,
            ) as exc:
                return (
                    page_number,
                    rect,
                    index,
                    "",
                    [],
                    f"{type(exc).__name__}: {str(exc)[:300]}",
                )

        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(run, jobs))
        for page_number, rect, index, text, words, error in results:
            if error:
                region = f":region-{index}" if rect is not None else ""
                warnings.append(
                    f"ocr_failed:{page_number}{region}:{error}"
                )
                continue
            if not text:
                warnings.append(f"empty_ocr_page:{page_number}")
                continue
            try:
                table = reconstruct_ocr_table(words) if words else None
            except (ArithmeticError, ValueError, KeyError) as exc:
                table = None
                warnings.append(
                    f"ocr_table_failed:{page_number}:{type(exc).__name__}"
                )
            locator = [("ocr_dpi", str(dpi)), ("ocr_psm", str(psm))]
            if rect is not None:
                locator.extend(
                    [
                        ("ocr_region", "true"),
                        ("ocr_region_index", str(index)),
                        (
                            "ocr_bbox",
                            f"{rect.x0:.1f},{rect.y0:.1f},"
                            f"{rect.x1:.1f},{rect.y1:.1f}",
                        ),
                    ]
                )
            label = (
                f"page-{page_number}"
                if rect is None
                else f"page-{page_number}-region-{index}"
            )
            position = SourcePosition(
                kind=PositionKind.PDF_PAGE.value,
                start=page_number,
                end=page_number,
                label=label,
                locator=tuple(locator),
            )
            metadata = [
                ("ocr", "tesseract"),
                ("ocr_languages", "+".join(languages)),
                ("manual_review_required", "true"),
            ]
            if words:
                metadata.append(
                    (
                        "ocr_confidence",
                        f"{statistics.mean(w['conf'] for w in words):.1f}",
                    )
                )
            if rect is not None:
                metadata.append(("ocr_region", "true"))
            # The full OCR text is always preserved; a reconstructed table is
            # additional evidence, never a replacement for the page text.
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
                    metadata=tuple(metadata) + (("ocr_text", "true"),),
                )
            )
            if table is not None:
                table_metadata = tuple(metadata) + (("ocr_table", "true"),)
                if words:
                    scale = 72 / dpi
                    offset_x = rect.x0 if rect is not None else 0.0
                    offset_y = rect.y0 if rect is not None else 0.0
                    table_metadata += (
                        (
                            "ocr_table_bbox",
                            f"{offset_x + min(w['left'] for w in words) * scale:.1f},"
                            f"{offset_y + min(w['top'] for w in words) * scale:.1f},"
                            f"{offset_x + max(w['left'] + w['width'] for w in words) * scale:.1f},"
                            f"{offset_y + max(w['top'] + w['height'] for w in words) * scale:.1f}",
                        ),
                    )
                blocks.append(
                    ParsedBlock(
                        block_id=make_block_id(
                            revision_id,
                            asset_id,
                            len(blocks),
                            BlockType.TABLE.value,
                            position,
                            table.text,
                        ),
                        block_type=BlockType.TABLE.value,
                        text=table.text,
                        position=position,
                        table=table,
                        metadata=table_metadata,
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
            [
                plan.page_number,
                plan.char_count,
                plan.image_count,
                plan.reason,
                round(plan.image_area_ratio, 4),
                plan.mixed_candidate,
            ]
            for plan in plans
        ],
        sort_keys=True,
    )
    return sha256(payload.encode()).hexdigest()
