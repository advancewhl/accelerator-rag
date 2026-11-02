"""PPTX sources parsed into the format-neutral ``ParsedDocument`` contract.

Slides are the position axis: every block records the 1-based slide number.
Title placeholders become headings, text frames become paragraphs, tables keep
their header row and pictures become empty-text ``IMAGE`` blocks.  Group shapes
are traversed recursively.  Speaker notes are emitted as ``NOTE`` blocks with
``source=notes`` and are never merged into the slide body.

Some decks contain shapes whose type python-pptx cannot recognize
(``NotImplementedError: Shape instance of unrecognized shape type``).  Shape
handling is defensive: unknown shapes are recorded as warnings and, when they
still expose a text frame, their text is kept as a paragraph.  Charts and other
graphic frames that cannot be represented as text are skipped with a warning
instead of failing the whole deck.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.oxml.ns import qn as pptx_qn

from accelerator_rag.corpus.parsed_document import (
    ParsedBlock,
    ParsedDocument,
    SourcePosition,
    TableData,
    _block_id,
)
from accelerator_rag.corpus.schema_v2 import SourceFormat
from accelerator_rag.domain.position import BlockType, PositionKind


_TITLE_PLACEHOLDERS = {
    PP_PLACEHOLDER.TITLE,
    PP_PLACEHOLDER.CENTER_TITLE,
    PP_PLACEHOLDER.VERTICAL_TITLE,
}
_SHAPE_ERRORS = (
    NotImplementedError,
    KeyError,
    ValueError,
    AttributeError,
    TypeError,
)


def _safe_source_path(path: Path, source_path: str | None) -> str:
    if source_path is not None:
        return source_path
    parts = path.parts
    for index in range(1, len(parts)):
        if parts[index - 1] == "data" and parts[index] == "l0_raw":
            return PurePosixPath(*parts[index - 1 :]).as_posix()
    return f"data/l0_raw/{path.name}"


def _frame_text(frame) -> str:
    paragraphs = [paragraph.text.strip() for paragraph in frame.paragraphs]
    return "\n".join(text for text in paragraphs if text)


def _safe_attr(shape, name: str):
    try:
        return getattr(shape, name)
    except _SHAPE_ERRORS:
        return None


def _shape_identity(shape) -> tuple[str, str]:
    shape_id = _safe_attr(shape, "shape_id")
    name = _safe_attr(shape, "name")
    element = getattr(shape, "_element", None)
    if element is not None and (shape_id is None or name is None):
        for child in element.iter(pptx_qn("p:cNvPr")):
            if shape_id is None:
                shape_id = child.get("id")
            if name is None:
                name = child.get("name")
            break
    return (
        str(shape_id if shape_id is not None else "unknown"),
        str(name if name is not None else "unknown"),
    )


def _shape_warning(
    kind: str, slide_number: int, shape, exc: Exception | None = None
) -> str:
    shape_id, name = _shape_identity(shape)
    message = f"{kind}:slide-{slide_number}:id={shape_id}:name={name}"
    if exc is not None:
        message += f":{type(exc).__name__}"
    return message


def _safe_shape_type(shape) -> tuple[object | None, Exception | None]:
    try:
        return shape.shape_type, None
    except _SHAPE_ERRORS as exc:
        return None, exc


def _is_group_shape(shape) -> bool:
    shape_type, _ = _safe_shape_type(shape)
    if shape_type == MSO_SHAPE_TYPE.GROUP:
        return True
    element = getattr(shape, "_element", None)
    return element is not None and element.tag == pptx_qn("p:grpSp")


def _iter_shapes(shapes, warnings: list[str], slide_number: int):
    for shape in shapes:
        if _is_group_shape(shape):
            try:
                children = shape.shapes
            except _SHAPE_ERRORS as exc:
                warnings.append(
                    _shape_warning(
                        "group_unreadable", slide_number, shape, exc
                    )
                )
                continue
            try:
                yield from _iter_shapes(children, warnings, slide_number)
            except _SHAPE_ERRORS as exc:
                warnings.append(
                    _shape_warning(
                        "group_traversal_failed",
                        slide_number,
                        shape,
                        exc,
                    )
                )
        else:
            yield shape


def _has_text_frame(shape) -> bool:
    try:
        return bool(shape.has_text_frame)
    except _SHAPE_ERRORS:
        element = getattr(shape, "_element", None)
        if element is None:
            return False
        return any(
            child.tag == pptx_qn("p:txBody") for child in element.iter()
        )


def _shape_text(shape) -> str:
    if not _has_text_frame(shape):
        return ""
    try:
        return _frame_text(shape.text_frame)
    except _SHAPE_ERRORS:
        return ""


def _is_title_placeholder(shape) -> bool:
    try:
        if not shape.is_placeholder:
            return False
    except _SHAPE_ERRORS:
        return False
    try:
        return shape.placeholder_format.type in _TITLE_PLACEHOLDERS
    except _SHAPE_ERRORS:
        return False


def _is_table_shape(shape, shape_type) -> bool:
    if shape_type == MSO_SHAPE_TYPE.TABLE:
        return True
    try:
        return bool(shape.has_table)
    except _SHAPE_ERRORS:
        return False


def _is_picture_shape(shape, shape_type) -> bool:
    if shape_type == MSO_SHAPE_TYPE.PICTURE:
        return True
    element = getattr(shape, "_element", None)
    return element is not None and element.tag == pptx_qn("p:pic")


def _is_graphic_frame(shape, shape_type) -> bool:
    # python-pptx has no GRAPHIC_FRAME member in MSO_SHAPE_TYPE; a graphic
    # frame reports CHART, TABLE, DIAGRAM, MEDIA and so on.  The XML tag is
    # the stable test and also works when shape_type is unrecognized.
    element = getattr(shape, "_element", None)
    return element is not None and element.tag == pptx_qn("p:graphicFrame")


def _has_chart(shape) -> bool:
    try:
        return bool(shape.has_chart)
    except _SHAPE_ERRORS:
        return False


def _graphic_frame_text(shape) -> str:
    element = getattr(shape, "_element", None)
    if element is None:
        return ""
    texts = [
        child.text.strip()
        for child in element.iter(pptx_qn("a:t"))
        if child.text and child.text.strip()
    ]
    return "\n".join(texts)


def _cell_text(cell) -> str:
    return " ".join(cell.text.split())


def _table_data(table) -> TableData | None:
    rows: list[tuple[str, ...]] = []
    width = 0
    for row in table.rows:
        cells = tuple(_cell_text(cell) for cell in row.cells)
        width = max(width, len(cells))
        rows.append(cells)
    if width == 0:
        return None
    padded = tuple(row + ("",) * (width - len(row)) for row in rows)
    if not any(cell for row in padded for cell in row):
        return None
    header_rows = 1 if any(cell for cell in padded[0]) else 0
    return TableData(rows=padded, header_rows=header_rows)


def _position(slide_number: int, locator: tuple[tuple[str, str], ...]):
    return SourcePosition(
        kind=PositionKind.SLIDE.value,
        start=slide_number,
        end=slide_number,
        label=f"slide-{slide_number}",
        locator=locator,
    )


def _shape_locator(shape) -> tuple[tuple[str, str], ...]:
    shape_id, name = _shape_identity(shape)
    return (("shape_id", shape_id), ("shape_name", name))


def _make_block(
    *,
    revision_id: str,
    asset_id: str,
    ordinal: int,
    block_type: str,
    text: str,
    position: SourcePosition,
    heading_level: int = 0,
    table: TableData | None = None,
    metadata: tuple[tuple[str, str], ...] = (),
) -> ParsedBlock:
    return ParsedBlock(
        block_id=_block_id(
            revision_id, asset_id, ordinal, block_type, position, text
        ),
        block_type=block_type,
        text=text,
        position=position,
        heading_level=heading_level,
        table=table,
        metadata=metadata,
    )


def parse_pptx(
    path: str | Path,
    *,
    revision_id: str,
    asset_id: str | None = None,
    title: str | None = None,
    parser_profile: str = "python-pptx-v1",
    source_path: str | None = None,
) -> ParsedDocument:
    """Parse one PPTX deck into slide-positioned typed blocks."""

    pptx_path = Path(path)
    if not pptx_path.exists():
        raise FileNotFoundError(f"PPTX file does not exist: {pptx_path}")
    if pptx_path.suffix.lower() != ".pptx":
        raise ValueError(f"Expected a PPTX file: {pptx_path}")

    resolved_asset = asset_id or f"asset-{revision_id}-original"
    resolved_source = _safe_source_path(pptx_path, source_path)
    presentation = Presentation(str(pptx_path))

    blocks: list[ParsedBlock] = []
    warnings: list[str] = []
    first_slide_title = ""
    table_count = 0
    image_count = 0
    note_count = 0
    unhandled_unknown_count = 0

    for slide_number, slide in enumerate(presentation.slides, 1):
        slide_shapes = list(
            _iter_shapes(slide.shapes, warnings, slide_number)
        )

        for shape in slide_shapes:
            shape_type, shape_error = _safe_shape_type(shape)
            try:
                locator = _shape_locator(shape)
            except _SHAPE_ERRORS:
                locator = ()
            if shape_type is None:
                warnings.append(
                    _shape_warning(
                        "unrecognized_shape_type",
                        slide_number,
                        shape,
                        shape_error,
                    )
                )
            block_count_before = len(blocks)
            try:
                if _is_table_shape(shape, shape_type):
                    table_count += 1
                    table_data = _table_data(shape.table)
                    if table_data is None:
                        warnings.append(
                            f"empty_table:slide-{slide_number}:"
                            f"{_shape_identity(shape)[1]}"
                        )
                        continue
                    position = _position(
                        slide_number,
                        locator
                        + (
                            ("table", str(table_count)),
                            ("rows", str(len(table_data.rows))),
                            ("columns", str(len(table_data.rows[0]))),
                        ),
                    )
                    blocks.append(
                        _make_block(
                            revision_id=revision_id,
                            asset_id=resolved_asset,
                            ordinal=len(blocks),
                            block_type=BlockType.TABLE.value,
                            text=table_data.text,
                            position=position,
                            table=table_data,
                            metadata=(("kind", "table"),),
                        )
                    )
                    continue

                if _is_picture_shape(shape, shape_type):
                    image_count += 1
                    image_format = ""
                    try:
                        image_format = shape.image.ext
                    except _SHAPE_ERRORS:
                        image_format = ""
                    metadata = [("kind", "image")]
                    if image_format:
                        metadata.append(
                            ("image_format", str(image_format))
                        )
                    blocks.append(
                        _make_block(
                            revision_id=revision_id,
                            asset_id=resolved_asset,
                            ordinal=len(blocks),
                            block_type=BlockType.IMAGE.value,
                            text="",
                            position=_position(slide_number, locator),
                            metadata=tuple(metadata),
                        )
                    )
                    continue

                if _is_graphic_frame(shape, shape_type):
                    if _has_chart(shape):
                        if shape_type is not None:
                            warnings.append(
                                _shape_warning(
                                    "chart_not_extracted",
                                    slide_number,
                                    shape,
                                )
                            )
                        continue
                    text = _graphic_frame_text(shape)
                    if text:
                        blocks.append(
                            _make_block(
                                revision_id=revision_id,
                                asset_id=resolved_asset,
                                ordinal=len(blocks),
                                block_type=BlockType.PARAGRAPH.value,
                                text=text,
                                position=_position(slide_number, locator),
                                metadata=(("kind", "graphic_frame"),),
                            )
                        )
                    elif shape_type is not None:
                        warnings.append(
                            _shape_warning(
                                "graphic_frame_not_extracted",
                                slide_number,
                                shape,
                            )
                        )
                    continue

                text = _shape_text(shape)
                if not text:
                    continue
                if _is_title_placeholder(shape):
                    first_slide_title = first_slide_title or text
                    blocks.append(
                        _make_block(
                            revision_id=revision_id,
                            asset_id=resolved_asset,
                            ordinal=len(blocks),
                            block_type=BlockType.HEADING.value,
                            text=text,
                            position=_position(slide_number, locator),
                            heading_level=1,
                            metadata=(("heading_source", "placeholder"),),
                        )
                    )
                else:
                    blocks.append(
                        _make_block(
                            revision_id=revision_id,
                            asset_id=resolved_asset,
                            ordinal=len(blocks),
                            block_type=BlockType.PARAGRAPH.value,
                            text=text,
                            position=_position(slide_number, locator),
                        )
                    )
            except _SHAPE_ERRORS as exc:
                warnings.append(
                    _shape_warning(
                        "shape_processing_failed",
                        slide_number,
                        shape,
                        exc,
                    )
                )
            finally:
                if (
                    shape_type is None
                    and len(blocks) == block_count_before
                ):
                    unhandled_unknown_count += 1

        if slide.has_notes_slide:
            try:
                notes_frame = slide.notes_slide.notes_text_frame
                notes_text = (
                    _frame_text(notes_frame)
                    if notes_frame is not None
                    else ""
                )
            except _SHAPE_ERRORS as exc:
                warnings.append(
                    f"notes_unreadable:slide-{slide_number}:"
                    f"{type(exc).__name__}"
                )
                notes_text = ""
            if notes_text:
                note_count += 1
                blocks.append(
                    _make_block(
                        revision_id=revision_id,
                        asset_id=resolved_asset,
                        ordinal=len(blocks),
                        block_type=BlockType.NOTE.value,
                        text=notes_text,
                        position=_position(
                            slide_number,
                            (
                                ("source", "notes"),
                                ("slide", str(slide_number)),
                            ),
                        ),
                        metadata=(("source", "notes"),),
                    )
                )

    if not blocks:
        warnings.append("empty_document")

    core_title = str(presentation.core_properties.title or "").strip()
    resolved_title = title or core_title or first_slide_title or pptx_path.stem

    unsupported_shape_count = sum(
        warning.startswith("unrecognized_shape_type")
        for warning in warnings
    )
    chart_count = sum(
        warning.startswith("chart_not_extracted") for warning in warnings
    )
    metadata_pairs = (
        ("slide_count", str(len(presentation.slides))),
        ("table_count", str(table_count)),
        ("image_count", str(image_count)),
        ("note_count", str(note_count)),
        ("unsupported_shape_count", str(unsupported_shape_count)),
        (
            "unhandled_unknown_shape_count",
            str(unhandled_unknown_count),
        ),
        ("chart_count", str(chart_count)),
    )

    return ParsedDocument(
        revision_id=revision_id,
        asset_id=resolved_asset,
        source_path=resolved_source,
        source_format=SourceFormat.PPTX.value,
        title=resolved_title,
        blocks=tuple(blocks),
        warnings=tuple(warnings),
        metadata=metadata_pairs,
        parser_profile=parser_profile,
    )
