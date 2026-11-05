"""DOCX sources parsed into the format-neutral ``ParsedDocument`` contract.

Body order is authoritative: paragraphs and tables are visited through
``document.element.body`` so a table keeps its place between the paragraphs that
introduce and follow it.  Body content controls (``w:sdt``) are flattened in
place so their paragraphs and tables are not lost.  Text boxes
(``w:txbxContent``) are extracted as separate paragraph blocks because Word
does not expose their text through ``paragraph.text``.  Headers and footers
live in other document parts and never enter the body stream.

Generated tables of contents are not evidence.  They are detected from TOC
styles, ``TOC \\o`` fields, dot/tab page leaders, and a ``目录`` / ``Contents``
title followed by numbered entries, then skipped with ``toc_block_count`` in
the document metadata.  A real body heading named ``目录`` is kept when the
surrounding paragraphs do not look like a generated TOC.

Headings are recognized first from paragraph styles (``Heading 1`` /
``标题 1``, ``Title`` / ``标题``) or an outline level.  Real Word documents
often omit heading styles, so two conservative fallbacks apply to style-less
body paragraphs:

* a short numbered paragraph (``1``, ``1.2``, ``1.2.3`` ...) that does not read
  like a sentence;
* a short paragraph whose majority of text runs are bold with a font size
  clearly larger than the document body size.

List-styled or numbered list paragraphs are never promoted by the fallbacks.
The document metadata records ``heading_style_count``,
``heading_heuristic_count`` and ``heading_detection=conservative`` so a build
report can explain what happened.

Common OMML structures are converted to LaTeX (``latex_status=latex``) while
unsupported or damaged expressions keep their extracted text and
``latex_status=unresolved``.  If an OMML expression has no extractable text the
block is still emitted with an explicit placeholder and a warning.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from accelerator_rag.corpus.omml import omml_paragraph_latex
from accelerator_rag.corpus.parsed_document import (
    ParsedBlock,
    ParsedDocument,
    SourcePosition,
    TableData,
    _block_id,
)
from accelerator_rag.corpus.schema_v2 import SourceFormat
from accelerator_rag.domain.position import BlockType, PositionKind


_HEADING_STYLE = re.compile(r"^(?:heading|标题)\s*([1-6])$", re.IGNORECASE)
_TITLE_STYLE = re.compile(r"^(?:title|标题)$", re.IGNORECASE)
_CAPTION_STYLE = re.compile(r"^(?:caption|题注|图注|表注)$", re.IGNORECASE)
_CAPTION_TEXT = re.compile(r"^(?:表|table|图|figure)\s*\d", re.IGNORECASE)
_LIST_STYLE = re.compile(r"^(?:list|列表)", re.IGNORECASE)
_TOC_STYLE = re.compile(
    r"^(?:toc|目录|table of contents)", re.IGNORECASE
)
_TOC_TITLE_TEXTS = frozenset({"目录", "contents", "tableofcontents"})
_TOC_FIELD = re.compile(r"\bTOC\b", re.IGNORECASE)
_TOC_DOT_LEADER = re.compile(r"(?:\.{3,}|…{2,}|·{3,})\s*\d+\s*$")
_TOC_TAB_PAGE = re.compile(r"\t\s*\d+\s*$")
_NUMBERED_HEADING = re.compile(
    r"^\s*(?P<number>\d+(?:\.\d+){0,4})"
    r"(?:[\s、]|[.．](?!\d))\s*(?P<rest>\S.*)$"
)
# "6.4.6风险与控制" has no space between the number and the title.  Requiring
# at least three components keeps short body phrases such as "1.5倍速" out.
_NUMBERED_HEADING_TIGHT = re.compile(
    r"^\s*(?P<number>\d+(?:\.\d+){2,4})(?P<rest>[^\d\s、.．].*)$"
)
_DATE_IN_TEXT = re.compile(
    r"(?:19|20)\d{2}\s*(?:年|[-/])|\d{4}-\d{1,2}"
)
_NON_HEADING_ENDINGS = ("。", ".", "．", "；", ";", "，", ",", "：", ":", "、")
_NON_HEADING_INNER = ("；", ";", "：", ":", "\t")
_FORMULA_PLACEHOLDER = "[formula]"
_HEADING_MAX_CHARS = 80
_BODY_FONT_SIZE_PT = 10.5


def _safe_source_path(path: Path, source_path: str | None) -> str:
    """Return a ``data/l0_raw`` relative identifier for the parsed file."""

    if source_path is not None:
        return source_path
    parts = path.parts
    for index in range(1, len(parts)):
        if parts[index - 1] == "data" and parts[index] == "l0_raw":
            return PurePosixPath(*parts[index - 1 :]).as_posix()
    return f"data/l0_raw/{path.name}"


def _style_name(paragraph: Paragraph) -> str:
    style = paragraph.style
    if style is None or not style.name:
        return ""
    return style.name.strip()


def _outline_level(paragraph: Paragraph) -> int:
    p_pr = paragraph._p.pPr
    if p_pr is None:
        return 0
    outline = p_pr.find(qn("w:outlineLvl"))
    if outline is None:
        return 0
    value = outline.get(qn("w:val"))
    try:
        level = int(value) + 1
    except (TypeError, ValueError):
        return 0
    return level if 1 <= level <= 6 else 0


def _named_heading_level(paragraph: Paragraph) -> int:
    style_name = _style_name(paragraph)
    match = _HEADING_STYLE.match(style_name)
    if match:
        return int(match.group(1))
    if _TITLE_STYLE.match(style_name):
        return 1
    return 0


def _is_list_item(paragraph: Paragraph) -> bool:
    if _LIST_STYLE.match(_style_name(paragraph)):
        return True
    p_pr = paragraph._p.pPr
    return p_pr is not None and p_pr.find(qn("w:numPr")) is not None


def _has_omml(paragraph: Paragraph) -> bool:
    return any(
        element.tag in {qn("m:oMath"), qn("m:oMathPara")}
        for element in paragraph._p.iter()
    )


def _omml_text(paragraph: Paragraph) -> str:
    parts = [
        element.text
        for element in paragraph._p.iter()
        if element.tag == qn("m:t") and element.text
    ]
    return "".join(parts).strip()


def _formula_text(paragraph: Paragraph) -> tuple[str, bool]:
    """Return (text, extracted) without inventing a formula representation."""

    math_text = _omml_text(paragraph)
    plain_text = paragraph.text.strip()
    if math_text and plain_text and plain_text not in math_text:
        return f"{math_text}\n{plain_text}", True
    if math_text:
        return math_text, True
    if plain_text:
        return plain_text, True
    return _FORMULA_PLACEHOLDER, False


def _effective_run_size(run, paragraph: Paragraph) -> float | None:
    size = run.font.size
    if size is None:
        style = paragraph.style
        if style is not None and style.font is not None:
            size = style.font.size
    if size is None:
        return None
    return round(float(size.pt) * 2) / 2


def _body_font_size(
    entries: list[tuple[str, Paragraph | Table]],
    toc_indices: set[int],
) -> float:
    sizes: Counter[float] = Counter()
    for body_index, (kind, item) in enumerate(entries, 1):
        if kind != "p" or body_index in toc_indices:
            continue
        paragraph = item
        if (
            _named_heading_level(paragraph)
            or _outline_level(paragraph)
            or _has_omml(paragraph)
        ):
            continue
        for run in paragraph.runs:
            if not run.text.strip() or run.bold is True:
                # Bold runs are usually headings/emphasis; they must not raise
                # the body-size baseline used by the bold-size fallback.
                continue
            size = _effective_run_size(run, paragraph)
            if size is not None:
                sizes[size] += 1
    if not sizes:
        return _BODY_FONT_SIZE_PT
    return sizes.most_common(1)[0][0]


def _majority_run_style(paragraph: Paragraph) -> tuple[bool, float | None]:
    runs = [run for run in paragraph.runs if run.text.strip()]
    if not runs:
        return False, None
    bold_count = sum(1 for run in runs if run.bold is True)
    sizes = [
        size
        for run in runs
        if (size := _effective_run_size(run, paragraph)) is not None
    ]
    majority_size = Counter(sizes).most_common(1)[0][0] if sizes else None
    return bold_count * 2 > len(runs), majority_size


def _numbered_heading_level(text: str) -> int:
    """Conservative numbered-heading fallback.

    List items often share the same ``1.`` prefix, so dates, tabs, semicolons,
    colons and list punctuation disqualify a candidate.  Uncertainty keeps the
    paragraph as body text instead of inventing document structure.
    """

    if len(text) > _HEADING_MAX_CHARS or "。" in text:
        return 0
    if text.endswith(_NON_HEADING_ENDINGS):
        return 0
    if any(marker in text for marker in _NON_HEADING_INNER):
        return 0
    if _DATE_IN_TEXT.search(text):
        return 0
    match = _NUMBERED_HEADING.match(text)
    if match is None:
        match = _NUMBERED_HEADING_TIGHT.match(text)
        if match is None:
            return 0
        if len(match.group("rest").strip()) < 2:
            return 0
    rest = match.group("rest").strip()
    if not rest:
        return 0
    return min(match.group("number").count(".") + 1, 6)


def _has_explicit_page_break(paragraph: Paragraph) -> bool:
    return any(
        element.tag == qn("w:br")
        and element.get(qn("w:type")) == "page"
        for element in paragraph._p.iter()
    )


def _has_toc_field(paragraph: Paragraph) -> bool:
    for element in paragraph._p.iter():
        if element.tag == qn("w:fldSimple"):
            if _TOC_FIELD.search(element.get(qn("w:instr")) or ""):
                return True
        elif element.tag == qn("w:instrText"):
            if _TOC_FIELD.search(element.text or ""):
                return True
    return False


def _is_toc_title_text(text: str) -> bool:
    return re.sub(r"\s+", "", text).lower() in _TOC_TITLE_TEXTS


def _has_toc_leader(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) > 200:
        return False
    dot = _TOC_DOT_LEADER.search(stripped)
    if dot is not None and dot.start() >= 2:
        return True
    tab = _TOC_TAB_PAGE.search(text)
    if tab is not None:
        return len(text[: tab.start()].strip()) >= 2
    return False


def _is_toc_paragraph(paragraph: Paragraph, text: str) -> bool:
    """A paragraph that is itself a generated TOC heading or entry."""

    if _TOC_STYLE.match(_style_name(paragraph)):
        return True
    if _has_toc_field(paragraph):
        return True
    return _has_toc_leader(text)


def _looks_like_toc_entry(paragraph: Paragraph, text: str) -> bool:
    return _is_toc_paragraph(paragraph, text) or _numbered_heading_level(text) > 0


def _toc_entry_span(entries: list[tuple[str, Paragraph | Table]], start: int) -> list[int]:
    """Collect body indices of numbered entries after a ``目录`` title."""

    span: list[int] = []
    seen_entry = False
    index = start
    while index < len(entries):
        kind, item = entries[index]
        if kind != "p" or _has_explicit_page_break(item):
            break
        text = item.text.strip()
        if not text:
            # Blank lines before the first entry are harmless; after the
            # entries they usually separate the TOC from the body.
            if seen_entry:
                break
            index += 1
            continue
        if _named_heading_level(item) or _outline_level(item):
            break
        if not _looks_like_toc_entry(item, text):
            break
        span.append(index + 1)
        seen_entry = True
        index += 1
        if len(span) >= 200:
            break
    return span


def _detect_toc(entries: list[tuple[str, Paragraph | Table]]) -> set[int]:
    """Find generated TOC paragraphs without deleting look-alike body text."""

    toc_indices: set[int] = set()
    for body_index, (kind, item) in enumerate(entries, 1):
        if kind != "p":
            continue
        paragraph = item
        text = paragraph.text.strip()
        if _is_toc_paragraph(paragraph, text):
            toc_indices.add(body_index)
        if not text or not _is_toc_title_text(text):
            continue
        span = _toc_entry_span(entries, body_index)
        if len(span) >= 2:
            toc_indices.add(body_index)
            toc_indices.update(span)
    return toc_indices


def _bold_size_heading_level(
    paragraph: Paragraph, body_size: float
) -> tuple[int, float | None]:
    text = paragraph.text.strip()
    if len(text) > _HEADING_MAX_CHARS or "。" in text:
        return 0, None
    if text.endswith(_NON_HEADING_ENDINGS):
        return 0, None
    bold, size = _majority_run_style(paragraph)
    if not bold or size is None:
        return 0, None
    if size < body_size + 2.0 or size < body_size * 1.2:
        return 0, None
    ratio = size / body_size
    level = 1 if ratio >= 1.5 else 2 if ratio >= 1.3 else 3
    return level, size


def _cell_text(cell) -> str:
    return " ".join(cell.text.split())


def _table_data(table: Table) -> TableData | None:
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


def _position(ordinal: int, locator: tuple[tuple[str, str], ...]) -> SourcePosition:
    return SourcePosition(
        kind=PositionKind.PARAGRAPH.value,
        start=ordinal,
        end=ordinal,
        label=f"paragraph-{ordinal}",
        locator=locator,
    )


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
    caption: str = "",
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
        caption=caption,
        metadata=metadata,
    )


def _attach_image_captions(blocks: list[ParsedBlock]) -> list[ParsedBlock]:
    """Attach a following caption block when the image had no preceding one."""

    values = list(blocks)
    for index, block in enumerate(values):
        if block.block_type != BlockType.IMAGE.value or block.caption:
            continue
        for candidate in values[index + 1 : index + 2]:
            if candidate.block_type != BlockType.CAPTION.value:
                continue
            metadata = block.metadata
            if not any(key == "image_caption" for key, _ in metadata):
                metadata += (("image_caption", candidate.text),)
            metadata += (("caption_source", "following"),)
            values[index] = replace(block, caption=candidate.text, metadata=metadata)
            break
    return values


def _textbox_elements(element) -> list:
    return [
        child for child in element.iter() if child.tag == qn("w:txbxContent")
    ]


def _body_elements(body):
    """Yield body paragraphs/tables in order, flattening content controls."""

    for child in body.iterchildren():
        if child.tag == qn("w:sdt"):
            content = child.find(qn("w:sdtContent"))
            if content is not None:
                yield from _body_elements(content)
        elif child.tag in {qn("w:p"), qn("w:tbl")}:
            yield child


def parse_docx(
    path: str | Path,
    *,
    revision_id: str,
    asset_id: str | None = None,
    title: str | None = None,
    parser_profile: str = "python-docx-v1",
    source_path: str | None = None,
    source_format: str = SourceFormat.DOCX.value,
    media_dir: str | Path | None = None,
    media_prefix: str = "",
    media_max_bytes: int = 256 * 1024 * 1024,
    media_min_bytes: int = 4096,
) -> ParsedDocument:
    """Parse one DOCX file into typed, ordered blocks.

    ``media_dir`` materializes embedded images beside the parsed snapshot;
    without it the IMAGE blocks still carry hashes and relationship IDs.
    """

    docx_path = Path(path)
    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX file does not exist: {docx_path}")
    if docx_path.suffix.lower() != ".docx":
        raise ValueError(f"Expected a DOCX file: {docx_path}")

    resolved_asset = asset_id or f"asset-{revision_id}-original"
    resolved_source = _safe_source_path(docx_path, source_path)
    document = Document(str(docx_path))

    entries: list[tuple[str, Paragraph | Table]] = []
    for child in _body_elements(document.element.body):
        if child.tag == qn("w:p"):
            entries.append(("p", Paragraph(child, document)))
        elif child.tag == qn("w:tbl"):
            entries.append(("tbl", Table(child, document)))

    toc_indices = _detect_toc(entries)
    body_size = _body_font_size(entries, toc_indices)
    blocks: list[ParsedBlock] = []
    warnings: list[str] = []
    first_heading = ""
    last_caption = ""
    table_index = 0
    style_heading_count = 0
    outline_heading_count = 0
    heuristic_heading_count = 0
    textbox_count = 0
    textbox_paragraph_count = 0
    image_count = 0
    media_written = 0
    media_names: dict[str, str] = {}
    media_root = Path(media_dir) if media_dir is not None else None

    def emit_images(element, body_index: int, caption: str) -> None:
        nonlocal image_count, media_written
        for blip in element.iter(qn("a:blip")):
            rid = blip.get(qn("r:embed")) or blip.get(qn("r:link"))
            if not rid:
                continue
            part = document.part.related_parts.get(rid)
            if part is None:
                warnings.append(f"image_relationship_missing:{body_index}")
                continue
            try:
                blob = part.blob
            except (AttributeError, KeyError, OSError, ValueError) as exc:
                warnings.append(
                    f"image_unreadable:{body_index}:{type(exc).__name__}"
                )
                continue
            digest = sha256(blob).hexdigest()
            extension = PurePosixPath(str(part.partname)).suffix.lower()
            media_path = ""
            media_status = "not_materialized"
            if media_root is not None:
                if digest in media_names:
                    media_status = "duplicate"
                    media_path = (
                        f"{media_prefix}/{media_names[digest]}"
                        if media_prefix
                        else media_names[digest]
                    )
                elif len(blob) < media_min_bytes:
                    media_status = "below_size_floor"
                elif media_written + len(blob) > media_max_bytes:
                    media_status = "budget_exceeded"
                else:
                    media_root.mkdir(parents=True, exist_ok=True)
                    name = f"{digest[:16]}{extension}"
                    (media_root / name).write_bytes(blob)
                    media_names[digest] = name
                    media_written += len(blob)
                    media_status = "materialized"
                    media_path = (
                        f"{media_prefix}/{name}" if media_prefix else name
                    )
            image_count += 1
            metadata = [
                ("kind", "image"),
                ("media_rid", rid),
                ("media_sha256", digest),
                ("media_bytes", str(len(blob))),
                ("media_type", str(part.content_type)),
                ("media_ext", extension.lstrip(".")),
                ("media_status", media_status),
            ]
            if media_path:
                metadata.append(("media_path", media_path))
            if caption:
                metadata.append(("image_caption", caption))
            locator = (
                ("image", str(image_count)),
                ("relationship", rid),
            )
            blocks.append(
                _make_block(
                    revision_id=revision_id,
                    asset_id=resolved_asset,
                    ordinal=len(blocks),
                    block_type=BlockType.IMAGE.value,
                    text="",
                    position=_position(body_index, locator),
                    caption=caption,
                    metadata=tuple(metadata),
                )
            )

    def emit_textboxes(element, body_index: int, anchor: str) -> None:
        nonlocal textbox_count, textbox_paragraph_count
        for box_index, textbox in enumerate(_textbox_elements(element), 1):
            textbox_count += 1
            for paragraph_element in textbox.iter(qn("w:p")):
                box_paragraph = Paragraph(paragraph_element, document)
                text = box_paragraph.text.strip()
                if not text:
                    continue
                style_name = _style_name(box_paragraph)
                locator: list[tuple[str, str]] = [
                    ("textbox", str(box_index)),
                    ("container", anchor),
                ]
                if style_name:
                    locator.append(("style", style_name))
                blocks.append(
                    _make_block(
                        revision_id=revision_id,
                        asset_id=resolved_asset,
                        ordinal=len(blocks),
                        block_type=BlockType.PARAGRAPH.value,
                        text=text,
                        position=_position(body_index, tuple(locator)),
                        metadata=(("container", "textbox"),),
                    )
                )
                textbox_paragraph_count += 1

    for body_index, (kind, item) in enumerate(entries, 1):
        if kind == "p":
            paragraph = item
            if body_index in toc_indices:
                last_caption = ""
                emit_textboxes(paragraph._p, body_index, "paragraph")
                continue
            style_name = _style_name(paragraph)
            locator: list[tuple[str, str]] = []
            if style_name:
                locator.append(("style", style_name))
            emit_images(paragraph._p, body_index, last_caption)

            if _has_omml(paragraph):
                last_caption = ""
                latex, converted = omml_paragraph_latex(paragraph._p)
                if converted:
                    text = latex
                    metadata: list[tuple[str, str]] = [
                        ("formula_source", "omml"),
                        ("latex_status", "latex"),
                        ("latex_source", "omml"),
                    ]
                    extracted = True
                else:
                    text, extracted = _formula_text(paragraph)
                    metadata = [
                        ("formula_source", "omml"),
                        ("latex_status", "unresolved"),
                    ]
                if not extracted:
                    warnings.append(
                        f"formula_text_unavailable:paragraph-{body_index}"
                    )
                if not extracted:
                    metadata.append(("formula_text_status", "unavailable"))
                position = _position(body_index, tuple(locator) + (("omml", "true"),))
                blocks.append(
                    _make_block(
                        revision_id=revision_id,
                        asset_id=resolved_asset,
                        ordinal=len(blocks),
                        block_type=BlockType.FORMULA.value,
                        text=text,
                        position=position,
                        metadata=tuple(metadata),
                    )
                )
                emit_textboxes(paragraph._p, body_index, "paragraph")
                continue

            text = paragraph.text.strip()
            if text:
                named_level = _named_heading_level(paragraph)
                outline_level = (
                    _outline_level(paragraph) if not named_level else 0
                )
                if named_level or outline_level:
                    last_caption = ""
                    first_heading = first_heading or text
                    if named_level:
                        style_heading_count += 1
                        heading_source = "style"
                    else:
                        outline_heading_count += 1
                        heading_source = "outline"
                    blocks.append(
                        _make_block(
                            revision_id=revision_id,
                            asset_id=resolved_asset,
                            ordinal=len(blocks),
                            block_type=BlockType.HEADING.value,
                            text=text,
                            position=_position(body_index, tuple(locator)),
                            heading_level=named_level or outline_level,
                            metadata=(("heading_source", heading_source),),
                        )
                    )
                    emit_textboxes(paragraph._p, body_index, "paragraph")
                    continue

                previous_is_table = (
                    body_index > 1 and entries[body_index - 2][0] == "tbl"
                )
                next_is_table = (
                    body_index < len(entries) and entries[body_index][0] == "tbl"
                )
                caption_style = bool(_CAPTION_STYLE.match(style_name))
                caption_text = bool(_CAPTION_TEXT.match(text)) and (
                    previous_is_table or next_is_table
                )
                if caption_style or caption_text:
                    # A caption immediately after a table describes that table,
                    # not the next picture.  Do not let it leak into image OCR.
                    last_caption = (
                        "" if previous_is_table and not next_is_table else text
                    )
                    blocks.append(
                        _make_block(
                            revision_id=revision_id,
                            asset_id=resolved_asset,
                            ordinal=len(blocks),
                            block_type=BlockType.CAPTION.value,
                            text=text,
                            position=_position(body_index, tuple(locator)),
                        )
                    )
                    emit_textboxes(paragraph._p, body_index, "paragraph")
                    continue

                list_item = _is_list_item(paragraph)
                if not list_item and not _TOC_STYLE.match(style_name):
                    level = _numbered_heading_level(text)
                    rule = "numbering"
                    if not level:
                        level, font_size = _bold_size_heading_level(
                            paragraph, body_size
                        )
                        rule = "bold-size"
                        if level and font_size is not None:
                            locator.append(("font_size_pt", f"{font_size:g}"))
                    if level:
                        last_caption = ""
                        first_heading = first_heading or text
                        heuristic_heading_count += 1
                        blocks.append(
                            _make_block(
                                revision_id=revision_id,
                                asset_id=resolved_asset,
                                ordinal=len(blocks),
                                block_type=BlockType.HEADING.value,
                                text=text,
                                position=_position(body_index, tuple(locator)),
                                heading_level=level,
                                metadata=(
                                    ("heading_source", "heuristic"),
                                    ("heading_rule", rule),
                                ),
                            )
                        )
                        emit_textboxes(paragraph._p, body_index, "paragraph")
                        continue

                last_caption = ""
                block_type = (
                    BlockType.LIST_ITEM.value
                    if list_item
                    else BlockType.PARAGRAPH.value
                )
                blocks.append(
                    _make_block(
                        revision_id=revision_id,
                        asset_id=resolved_asset,
                        ordinal=len(blocks),
                        block_type=block_type,
                        text=text,
                        position=_position(body_index, tuple(locator)),
                    )
                )
            emit_textboxes(paragraph._p, body_index, "paragraph")
        else:
            table = item
            table_index += 1
            emit_images(table._tbl, body_index, last_caption)
            table_data = _table_data(table)
            if table_data is None:
                warnings.append(f"empty_table:paragraph-{body_index}")
                last_caption = ""
                emit_textboxes(table._tbl, body_index, "table")
                continue
            caption = last_caption
            last_caption = ""
            if caption:
                table_data = TableData(
                    rows=table_data.rows,
                    header_rows=table_data.header_rows,
                    caption=caption,
                    units=table_data.units,
                )
            locator = (
                ("table", str(table_index)),
                ("rows", str(len(table_data.rows))),
                ("columns", str(len(table_data.rows[0]))),
                ("header_rows", str(table_data.header_rows)),
            )
            blocks.append(
                _make_block(
                    revision_id=revision_id,
                    asset_id=resolved_asset,
                    ordinal=len(blocks),
                    block_type=BlockType.TABLE.value,
                    text=table_data.text,
                    position=_position(body_index, locator),
                    table=table_data,
                    caption=caption,
                )
            )
            emit_textboxes(table._tbl, body_index, "table")

    if not blocks and "empty_document" not in warnings:
        warnings.append("empty_document")
    blocks = _attach_image_captions(blocks)

    core_title = str(document.core_properties.title or "").strip()
    resolved_title = title or core_title or first_heading or docx_path.stem

    metadata_pairs = (
        ("heading_detection", "conservative"),
        ("heading_style_count", str(style_heading_count)),
        ("heading_outline_count", str(outline_heading_count)),
        ("heading_heuristic_count", str(heuristic_heading_count)),
        (
            "heading_count",
            str(
                style_heading_count
                + outline_heading_count
                + heuristic_heading_count
            ),
        ),
        ("textbox_count", str(textbox_count)),
        ("textbox_paragraph_count", str(textbox_paragraph_count)),
        ("image_count", str(image_count)),
        ("toc_detection", "conservative"),
        ("toc_block_count", str(len(toc_indices))),
        ("body_font_size_pt", f"{body_size:g}"),
    )

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
