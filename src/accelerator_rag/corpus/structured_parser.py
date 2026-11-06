"""Spreadsheet sources parsed into ``TABLE`` blocks with cell-range positions.

XLSX cells are read twice: once for formula expressions and once for cached
values, so the build record keeps both without executing macros or resolving
external links.  CSV files are decoded with ``utf-8-sig`` first and ``gb18030``
as the fallback.  ODS is deliberately unsupported in this environment: odfpy is
not installed, and the adapter refuses rather than pretending to parse.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from datetime import date, datetime
import importlib.util
import io
from pathlib import Path, PurePosixPath
import re

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter

from accelerator_rag.corpus.parsed_document import (
    ParsedBlock,
    ParsedDocument,
    SourcePosition,
    TableData,
    _block_id,
)
from accelerator_rag.corpus.schema_v2 import SourceFormat
from accelerator_rag.domain.position import BlockType, PositionKind


_CSV_ENCODINGS = ("utf-8-sig", "gb18030")


class UnsupportedStructuredFormat(ValueError):
    """A structured format cannot be parsed in this environment."""


def _safe_source_path(path: Path, source_path: str | None) -> str:
    if source_path is not None:
        return source_path
    parts = path.parts
    for index in range(1, len(parts)):
        if parts[index - 1] == "data" and parts[index] == "l0_raw":
            return PurePosixPath(*parts[index - 1 :]).as_posix()
    return f"data/l0_raw/{path.name}"


def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    # A line break inside a cell would split the row in pipe-table text.
    return " ".join(str(value).split())


def _formula_status(formula_count: int, cached_count: int) -> str:
    if formula_count == 0:
        return "none"
    if cached_count == formula_count:
        return "cached"
    if cached_count == 0:
        return "uncached"
    return "partially_cached"


def _padded(rows: list[tuple[str, ...]], width: int) -> tuple[tuple[str, ...], ...]:
    return tuple(row + ("",) * (width - len(row)) for row in rows)


def _make_table_block(
    *,
    revision_id: str,
    asset_id: str,
    ordinal: int,
    table: TableData,
    position: SourcePosition,
    metadata: tuple[tuple[str, str], ...],
) -> ParsedBlock:
    return ParsedBlock(
        block_id=_block_id(
            revision_id,
            asset_id,
            ordinal,
            BlockType.TABLE.value,
            position,
            table.text,
        ),
        block_type=BlockType.TABLE.value,
        text=table.text,
        position=position,
        table=table,
        metadata=metadata,
    )


def _cell_range_position(
    label_prefix: str,
    *,
    first_row: int,
    last_row: int,
    width: int,
    locator: tuple[tuple[str, str], ...],
) -> SourcePosition:
    range_text = f"A{first_row}:{get_column_letter(width)}{last_row}"
    return SourcePosition(
        kind=PositionKind.CELL_RANGE.value,
        start=first_row,
        end=last_row,
        label=f"{label_prefix}!{range_text}",
        locator=locator,
    )


_MERGE_RANGE = re.compile(r"^([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?$")
_NUMERIC_CELL = re.compile(r"^\d+(\.\d+)?$")


def _merge_boxes(merged: tuple[str, ...]) -> list[tuple[int, int, int, int]]:
    """Return (min_row, min_col, max_row, max_col), all 1-based, physical."""

    boxes = []
    for item in merged:
        match = _MERGE_RANGE.match(item.strip().upper())
        if match is None:
            continue
        min_col = column_index_from_string(match.group(1))
        min_row = int(match.group(2))
        max_col = column_index_from_string(match.group(3) or match.group(1))
        max_row = int(match.group(4) or match.group(2))
        boxes.append((min_row, min_col, max_row, max_col))
    return boxes


@dataclass(frozen=True)
class _Segment:
    header_rows: tuple[tuple[str, ...], ...]
    header_numbers: tuple[int, ...]
    data_rows: tuple[tuple[str, ...], ...]
    data_numbers: tuple[int, ...]
    group: str = ""
    header_span: tuple[int, int] | None = None


def _is_group_row(row: tuple[str, ...], number: int, boxes, width: int) -> bool:
    """A lone label that names the rows below it (cabinet/switch heading)."""

    filled = [(index, cell) for index, cell in enumerate(row) if cell]
    if len(filled) != 1 or width < 3:
        return False
    index, cell = filled[0]
    if _NUMERIC_CELL.match(cell):
        return False
    for min_row, min_col, max_row, max_col in boxes:
        if min_row == number and min_col == index + 1 and max_col > min_col:
            return max_row == min_row
    return index == 0


def _sheet_segments(
    rows: list[tuple[str, ...]],
    row_numbers: list[int],
    *,
    width: int,
    merged: tuple[str, ...],
    header: bool,
):
    """Split one sheet into header-bound row segments.

    Engineering spreadsheets put a merged title above the column names, use a
    second header row for sub-columns, insert one-cell group rows such as
    ``FEL2-CN01柜（DEVSW001）`` and repeat the header block further down.  A
    plain sheet (one header, none of the above) still yields exactly one
    segment with the original rows, so its block and chunk identity is
    unchanged.  Vertically merged data cells inherit the top-left value so a
    row keeps its device even when the source shows it only once.
    """

    warnings: list[str] = []
    padded = [tuple(row) + ("",) * (width - len(row)) for row in rows]
    numbers = list(row_numbers)
    boxes = _merge_boxes(merged)
    caption = ""
    if len(padded) > 0 and sum(1 for c in padded[0] if c) <= 1:
        second = sum(1 for c in padded[1] if c) if len(padded) > 1 else 0
        if second >= 2:
            caption = next(cell for cell in padded[0] if cell)
            padded, numbers = padded[1:], numbers[1:]
        else:
            warnings.append("title_row_without_header")
    if not header:
        return (
            [_Segment((), (), tuple(padded), tuple(numbers))],
            caption,
            warnings,
            0,
        )

    index_of = {number: i for i, number in enumerate(numbers)}
    grid = [list(row) for row in padded]

    def fill(box, *, rows_only: bool) -> int:
        min_row, min_col, max_row, max_col = box
        if min_row not in index_of or min_col > width:
            return 0
        value = grid[index_of[min_row]][min_col - 1]
        if not value:
            return 0
        count = 0
        for number in range(min_row, max_row + 1):
            if number not in index_of:
                continue
            for column in range(min_col, min(max_col, width) + 1):
                if rows_only and number == min_row:
                    continue
                if not grid[index_of[number]][column - 1]:
                    grid[index_of[number]][column - 1] = value
                    count += 1
        return count

    # Header extent: the column-name row plus sub-header rows that a merge
    # from the header row reaches, or that only label columns left blank.
    header_count = 1
    first_header = numbers[0]
    while header_count < min(3, len(grid)):
        number = numbers[header_count]
        row = grid[header_count]
        if not any(row) or _is_group_row(tuple(row), number, boxes, width):
            break
        reached = any(
            min_row == first_header and max_row >= number
            for min_row, _c, max_row, _d in boxes
        )
        top = grid[0]
        covered = {
            column
            for min_row, min_col, max_row, max_col in boxes
            if min_row <= first_header <= max_row and max_col > min_col
            for column in range(min_col + 1, max_col + 1)
        }
        labels_blank_columns = all(
            not cell or not top[i] or (i + 1) in covered
            for i, cell in enumerate(row)
        )
        numeric = any(_NUMERIC_CELL.match(cell) for cell in row if cell)
        if (reached or labels_blank_columns) and not numeric and (
            sum(1 for c in row if c) < sum(1 for c in top if c)
        ):
            header_count += 1
            continue
        break

    header_numbers = set(numbers[:header_count])
    filled = 0
    for box in boxes:
        if box[0] in header_numbers:
            filled += fill(box, rows_only=False)
    header_key = tuple(cell for cell in grid[0])
    header_range = (numbers[0], numbers[header_count - 1])
    # Several physical header rows compile into one column-name row so every
    # chunk and row record carries a single, readable label per column.
    compiled = []
    for column in range(width):
        values: list[str] = []
        for i in range(header_count):
            value = " ".join(grid[i][column].split())
            if value and value not in values:
                values.append(value)
        compiled.append(" / ".join(values))
    header_block = (tuple(compiled),)
    header_nums = (numbers[0],)

    data_fill = 0
    for box in boxes:
        min_row, _min_col, max_row, _max_col = box
        if min_row in header_numbers or max_row == min_row:
            continue
        data_fill += fill(box, rows_only=True)

    segments: list[_Segment] = []
    current_header, current_header_nums = header_block, header_nums
    group = ""
    data: list[tuple[str, ...]] = []
    data_nums: list[int] = []

    def flush():
        while data and not any(data[-1]):
            data.pop()
            data_nums.pop()
        if data:
            segments.append(
                _Segment(
                    current_header,
                    current_header_nums,
                    tuple(data),
                    tuple(data_nums),
                    group,
                )
            )
        data.clear()
        data_nums.clear()

    for i in range(header_count, len(grid)):
        row = tuple(grid[i])
        number = numbers[i]
        if not any(row) and not data:
            continue
        if row == header_key:
            flush()
            current_header, current_header_nums = (row,), (number,)
            group = ""
            continue
        if _is_group_row(tuple(padded[i]), number, boxes, width):
            label = next(cell for cell in padded[i] if cell)
            if data:
                flush()
                group = label
            else:
                group = f"{group} / {label}" if group else label
            continue
        data.append(row)
        data_nums.append(number)
    flush()
    if not segments:
        segments.append(
            _Segment(header_block, header_nums, (), (), group)
        )
    if header_range[1] != header_range[0]:
        segments = [
            replace(segment, header_span=header_range)
            if segment.header_numbers == header_nums
            else segment
            for segment in segments
        ]
    return segments, caption, warnings, filled + data_fill


def _segment_block(
    segment: _Segment,
    *,
    revision_id: str,
    asset_id: str,
    ordinal: int,
    sheet: str,
    caption: str,
    width: int,
    merged: tuple[str, ...],
    status: str,
    formula_count: int,
    formula_notes: list[str],
    fill_count: int,
    segmented: bool,
) -> ParsedBlock:
    rows = _padded(
        list(segment.header_rows) + list(segment.data_rows), width
    )
    row_numbers = segment.header_numbers + segment.data_numbers
    last_col = get_column_letter(width)
    table_caption = " · ".join(item for item in (caption, segment.group) if item)
    contiguous = all(
        b == a + 1 for a, b in zip(row_numbers, row_numbers[1:])
    )
    if contiguous or not segment.header_numbers or not segment.data_numbers:
        range_text = f"A{row_numbers[0]}:{last_col}{row_numbers[-1]}"
    else:
        range_text = (
            f"A{segment.header_numbers[0]}:{last_col}{segment.header_numbers[-1]};"
            f"A{segment.data_numbers[0]}:{last_col}{segment.data_numbers[-1]}"
        )
    table = TableData(
        rows=rows,
        header_rows=len(segment.header_rows),
        caption=table_caption,
        row_numbers=tuple(row_numbers),
        column_letters=tuple(
            get_column_letter(index) for index in range(1, width + 1)
        ),
        merged_ranges=merged,
    )
    locator = [
        ("sheet", sheet),
        ("range", range_text),
        ("rows", str(len(rows))),
        ("columns", str(width)),
        ("header_rows", str(len(segment.header_rows))),
        ("formula_status", status),
    ]
    if segment.group:
        locator.append(("group", segment.group))
    if segment.header_span is not None:
        locator.append(
            (
                "header_range",
                f"A{segment.header_span[0]}:{last_col}{segment.header_span[1]}",
            )
        )
    position = SourcePosition(
        kind=PositionKind.CELL_RANGE.value,
        start=row_numbers[0],
        end=row_numbers[-1],
        label=f"{sheet}!{range_text}",
        locator=tuple(locator),
    )
    metadata = [
        ("sheet", sheet),
        ("formula_status", status),
        ("formula_count", str(formula_count)),
    ]
    if caption:
        metadata.append(("caption", caption))
        metadata.append(("title_row", "1"))
    if segment.group:
        metadata.append(("group", segment.group))
    if segmented:
        metadata.append(("segmented", "1"))
    if fill_count:
        metadata.append(("merged_cells_filled", str(fill_count)))
    if formula_notes:
        metadata.append(("formula_cells", "; ".join(formula_notes)))
    return _make_table_block(
        revision_id=revision_id,
        asset_id=asset_id,
        ordinal=ordinal,
        table=table,
        position=position,
        metadata=tuple(metadata),
    )


def parse_xlsx(
    path: str | Path,
    *,
    revision_id: str,
    asset_id: str | None = None,
    title: str | None = None,
    parser_profile: str = "openpyxl-cells-v1",
    source_path: str | None = None,
    header: bool = True,
    source_format: str = SourceFormat.XLSX.value,
) -> ParsedDocument:
    """Parse every worksheet into header-bound ``TABLE`` blocks of cell text."""

    xlsx_path = Path(path)
    if not xlsx_path.exists():
        raise FileNotFoundError(f"XLSX file does not exist: {xlsx_path}")
    if xlsx_path.suffix.lower() != ".xlsx":
        raise ValueError(f"Expected an XLSX file: {xlsx_path}")

    resolved_asset = asset_id or f"asset-{revision_id}-original"
    resolved_source = _safe_source_path(xlsx_path, source_path)

    try:
        formula_book = load_workbook(
            filename=xlsx_path,
            read_only=True,
            data_only=False,
            keep_links=False,
            keep_vba=False,
        )
    except Exception as exc:
        raise ValueError(f"Cannot read XLSX workbook {xlsx_path}: {exc}") from exc

    blocks: list[ParsedBlock] = []
    warnings: list[str] = []
    try:
        try:
            value_book = load_workbook(
                filename=xlsx_path,
                read_only=True,
                data_only=True,
                keep_links=False,
                keep_vba=False,
            )
        except Exception as exc:
            raise ValueError(
                f"Cannot read cached XLSX values from {xlsx_path}: {exc}"
            ) from exc

        # Read-only worksheets do not expose merged ranges.  A second, normal
        # workbook is loaded only to record declared merges; values still come
        # from the cached-value workbook above.
        merged_by_sheet: dict[str, tuple[str, ...]] = {}
        structure_book = None
        try:
            structure_book = load_workbook(
                filename=xlsx_path,
                read_only=False,
                data_only=False,
                keep_links=False,
                keep_vba=False,
            )
            merged_by_sheet = {
                worksheet.title: tuple(
                    str(item) for item in worksheet.merged_cells.ranges
                )
                for worksheet in structure_book.worksheets
            }
        except Exception as exc:  # pragma: no cover - defensive
            warnings.append(f"merged_ranges_unavailable:{type(exc).__name__}")
        finally:
            if structure_book is not None:
                structure_book.close()

        try:
            for worksheet in formula_book.worksheets:
                value_sheet = value_book[worksheet.title]
                rows: list[tuple[str, ...]] = []
                row_numbers: list[int] = []
                formula_notes: list[str] = []
                formula_count = 0
                cached_count = 0
                width = 0
                first_content: int | None = None
                last_content: int | None = None

                row_pairs = zip(
                    worksheet.iter_rows(), value_sheet.iter_rows()
                )
                for row_index, (formula_row, value_row) in enumerate(
                    row_pairs, 1
                ):
                    texts: list[str] = []
                    has_content = False
                    for column_index, (formula_cell, value_cell) in enumerate(
                        zip(formula_row, value_row), 1
                    ):
                        raw = formula_cell.value
                        is_formula = (
                            getattr(formula_cell, "data_type", None) == "f"
                            or (
                                isinstance(raw, str)
                                and raw.startswith("=")
                                and len(raw) > 1
                            )
                        )
                        if is_formula:
                            formula_count += 1
                            formula = raw if isinstance(raw, str) else str(raw)
                            cached = value_cell.value
                            coordinate = (
                                f"{get_column_letter(column_index)}{row_index}"
                            )
                            note = f"{coordinate}: {formula}"
                            if cached is not None:
                                cached_count += 1
                                note += f" cached={_cell_text(cached)}"
                            formula_notes.append(note)
                            text = (
                                _cell_text(cached)
                                if cached is not None
                                else formula
                            )
                        else:
                            text = _cell_text(raw)
                        if text:
                            has_content = True
                        texts.append(text)
                    # Keep interior blank rows so a sheet range remains
                    # contiguous; leading/trailing blanks are trimmed below.
                    if has_content:
                        if first_content is None:
                            first_content = len(rows)
                        last_content = len(rows)
                    width = max(width, len(texts))
                    rows.append(tuple(texts))
                    row_numbers.append(row_index)

                if first_content is None or last_content is None:
                    warnings.append(f"empty_sheet:{worksheet.title}")
                    continue
                rows = rows[first_content : last_content + 1]
                row_numbers = row_numbers[first_content : last_content + 1]
                # Formatted-but-empty trailing columns (a .xls conversion can
                # report 255) are not part of the table.
                width = max(
                    (
                        max(
                            (i + 1 for i, cell in enumerate(row) if cell),
                            default=0,
                        )
                        for row in rows
                    ),
                    default=1,
                ) or 1
                rows = [row[:width] for row in rows]
                status = _formula_status(formula_count, cached_count)
                merged = merged_by_sheet.get(worksheet.title, ())
                segments, caption, layout_warnings, fill_count = (
                    _sheet_segments(
                        rows,
                        row_numbers,
                        width=width,
                        merged=merged,
                        header=header,
                    )
                )
                warnings.extend(
                    f"{item}:{worksheet.title}" for item in layout_warnings
                )
                for segment in segments:
                    blocks.append(
                        _segment_block(
                            segment,
                            revision_id=revision_id,
                            asset_id=resolved_asset,
                            ordinal=len(blocks),
                            sheet=worksheet.title,
                            caption=caption,
                            width=width,
                            merged=merged,
                            status=status,
                            formula_count=formula_count,
                            formula_notes=formula_notes,
                            fill_count=fill_count,
                            segmented=len(segments) > 1
                            or bool(segment.group),
                        )
                    )

            if not blocks:
                warnings.append("empty_document")

            workbook_title = str(formula_book.properties.title or "").strip()
            resolved_title = title or xlsx_path.stem
            metadata_pairs = [
                ("sheet_count", str(len(formula_book.worksheets))),
                ("table_count", str(len(blocks))),
            ]
            if workbook_title:
                metadata_pairs.append(("workbook_title", workbook_title))
        finally:
            value_book.close()
    finally:
        formula_book.close()

    return ParsedDocument(
        revision_id=revision_id,
        asset_id=resolved_asset,
        source_path=resolved_source,
        source_format=source_format,
        title=resolved_title,
        blocks=tuple(blocks),
        warnings=tuple(warnings),
        metadata=metadata_pairs,
        parser_profile=parser_profile,
    )


def parse_csv(
    path: str | Path,
    *,
    revision_id: str,
    asset_id: str | None = None,
    title: str | None = None,
    parser_profile: str = "csv-module-v1",
    source_path: str | None = None,
    header: bool = True,
    delimiter: str = ",",
    encoding: str | None = None,
) -> ParsedDocument:
    """Parse a CSV file into one ``TABLE`` block with logical row positions."""

    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file does not exist: {csv_path}")
    if csv_path.suffix.lower() != ".csv":
        raise ValueError(f"Expected a CSV file: {csv_path}")
    if not delimiter or len(delimiter) != 1:
        raise ValueError("delimiter must be exactly one character")

    resolved_asset = asset_id or f"asset-{revision_id}-original"
    resolved_source = _safe_source_path(csv_path, source_path)

    raw = csv_path.read_bytes()
    if encoding is None:
        candidates = _CSV_ENCODINGS
    else:
        candidates = (encoding,)
    decoded: str | None = None
    used_encoding = ""
    for candidate in candidates:
        try:
            decoded = raw.decode(candidate)
            used_encoding = candidate
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        raise ValueError(
            "CSV encoding could not be determined; tried "
            + ", ".join(candidates)
        )
    decoded = decoded.replace("\x00", "")

    records: list[tuple[str, ...]] = []
    row_numbers: list[int] = []
    logical_row = 0
    for record in csv.reader(io.StringIO(decoded, newline=""), delimiter=delimiter):
        logical_row += 1
        if not any(cell.strip() for cell in record):
            continue
        records.append(tuple(cell.strip() for cell in record))
        row_numbers.append(logical_row)

    if not records:
        return ParsedDocument(
            revision_id=revision_id,
            asset_id=resolved_asset,
            source_path=resolved_source,
            source_format=SourceFormat.CSV.value,
            title=title or csv_path.stem,
            blocks=(),
            warnings=("empty_document",),
            metadata=(
                ("encoding", used_encoding),
                ("delimiter", delimiter),
            ),
            parser_profile=parser_profile,
        )

    width = max(len(record) for record in records)
    table_rows = _padded(records, width)
    header_rows = 1 if header else 0
    table = TableData(rows=table_rows, header_rows=header_rows)
    range_text = (
        f"A{row_numbers[0]}:{get_column_letter(width)}{row_numbers[-1]}"
    )
    position = SourcePosition(
        kind=PositionKind.CELL_RANGE.value,
        start=row_numbers[0],
        end=row_numbers[-1],
        label=f"{csv_path.name}!{range_text}",
        locator=(
            ("file", csv_path.name),
            ("range", range_text),
            ("rows", str(len(table_rows))),
            ("columns", str(width)),
            ("header_rows", str(header_rows)),
            ("encoding", used_encoding),
            ("delimiter", delimiter),
        ),
    )
    block = _make_table_block(
        revision_id=revision_id,
        asset_id=resolved_asset,
        ordinal=0,
        table=table,
        position=position,
        metadata=(
            ("encoding", used_encoding),
            ("delimiter", delimiter),
        ),
    )

    return ParsedDocument(
        revision_id=revision_id,
        asset_id=resolved_asset,
        source_path=resolved_source,
        source_format=SourceFormat.CSV.value,
        title=title or csv_path.stem,
        blocks=(block,),
        warnings=(),
        metadata=(
            ("encoding", used_encoding),
            ("delimiter", delimiter),
            ("row_count", str(len(table_rows))),
            ("column_count", str(width)),
        ),
        parser_profile=parser_profile,
    )


def parse_ods(
    path: str | Path,
    *,
    revision_id: str,
    asset_id: str | None = None,
    title: str | None = None,
    parser_profile: str = "odfpy-cells-v1",
    source_path: str | None = None,
) -> ParsedDocument:
    """Refuse ODS until an odfpy adapter is installed and verified."""

    ods_path = Path(path)
    if not ods_path.exists():
        raise FileNotFoundError(f"ODS file does not exist: {ods_path}")
    if ods_path.suffix.lower() != ".ods":
        raise ValueError(f"Expected an ODS file: {ods_path}")

    if importlib.util.find_spec("odf") is None:
        raise UnsupportedStructuredFormat(
            "ODS parsing requires the odfpy package (module 'odf'), which is "
            "not installed; install odfpy before enabling ODS ingestion"
        )
    raise UnsupportedStructuredFormat(
        "ODS parsing is not implemented in this build even though odfpy is "
        "installed; no data was read"
    )
