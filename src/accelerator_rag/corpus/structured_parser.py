"""Spreadsheet sources parsed into ``TABLE`` blocks with cell-range positions.

XLSX cells are read twice: once for formula expressions and once for cached
values, so the build record keeps both without executing macros or resolving
external links.  CSV files are decoded with ``utf-8-sig`` first and ``gb18030``
as the fallback.  ODS is deliberately unsupported in this environment: odfpy is
not installed, and the adapter refuses rather than pretending to parse.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
import importlib.util
import io
from pathlib import Path, PurePosixPath

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

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
    return str(value).strip()


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


def parse_xlsx(
    path: str | Path,
    *,
    revision_id: str,
    asset_id: str | None = None,
    title: str | None = None,
    parser_profile: str = "openpyxl-cells-v1",
    source_path: str | None = None,
    header: bool = True,
) -> ParsedDocument:
    """Parse every worksheet into one ``TABLE`` block of cell text."""

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
                width = max(len(row) for row in rows)

                caption = ""
                first_nonempty = sum(1 for cell in rows[0] if cell)
                second_nonempty = (
                    sum(1 for cell in rows[1] if cell) if len(rows) > 1 else 0
                )
                if first_nonempty <= 1:
                    if second_nonempty >= 2:
                        # A merged title row above a real column-name row.
                        caption = next(cell for cell in rows[0] if cell)
                        rows = rows[1:]
                        row_numbers = row_numbers[1:]
                    else:
                        warnings.append(
                            f"title_row_without_header:{worksheet.title}"
                        )

                table_rows = _padded(rows, width)
                header_rows = 1 if header else 0
                table = TableData(
                    rows=table_rows,
                    header_rows=header_rows,
                    caption=caption,
                    row_numbers=tuple(row_numbers),
                    column_letters=tuple(
                        get_column_letter(index)
                        for index in range(1, width + 1)
                    ),
                    merged_ranges=merged_by_sheet.get(worksheet.title, ()),
                )
                status = _formula_status(formula_count, cached_count)
                position = _cell_range_position(
                    worksheet.title,
                    first_row=row_numbers[0],
                    last_row=row_numbers[-1],
                    width=width,
                    locator=(
                        ("sheet", worksheet.title),
                        (
                            "range",
                            f"A{row_numbers[0]}:"
                            f"{get_column_letter(width)}{row_numbers[-1]}",
                        ),
                        ("rows", str(len(table_rows))),
                        ("columns", str(width)),
                        ("header_rows", str(header_rows)),
                        ("formula_status", status),
                    ),
                )
                metadata = [
                    ("sheet", worksheet.title),
                    ("formula_status", status),
                    ("formula_count", str(formula_count)),
                ]
                if caption:
                    metadata.append(("caption", caption))
                    metadata.append(("title_row", "1"))
                if formula_notes:
                    metadata.append(
                        ("formula_cells", "; ".join(formula_notes))
                    )
                blocks.append(
                    _make_table_block(
                        revision_id=revision_id,
                        asset_id=resolved_asset,
                        ordinal=len(blocks),
                        table=table,
                        position=position,
                        metadata=tuple(metadata),
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
        source_format=SourceFormat.XLSX.value,
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
