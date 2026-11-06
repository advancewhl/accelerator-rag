"""Schema v2 chunking: typed blocks to canonical evidence with explicit positions.

The frozen ``pdf-chunks-v3`` / ``md-chunks-v1`` algorithms remain untouched for
legacy identities.  New revisions use this module, whose IDs include the
revision, asset, position kind and processing contract.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re

from accelerator_rag.corpus.parsed_document import (
    ParsedBlock,
    ParsedDocument,
    TableData,
)
from accelerator_rag.corpus.schema_v2 import RevisionRecord
from accelerator_rag.domain.knowledge import KnowledgeChunk
from accelerator_rag.domain.position import BlockType, PositionKind


V2_CHUNKING_ALGORITHM = "kb2-chunks-v2"
_MAX_SECTION_PATH_CHARS = 300


@dataclass(frozen=True)
class V2ChunkingConfig:
    """No overlap. Headings up to this level start a new evidence group."""

    max_chars: int = 1200
    min_chars: int = 300
    max_heading_level: int = 2

    def __post_init__(self) -> None:
        if (
            type(self.max_chars) is not int
            or type(self.min_chars) is not int
            or not 0 < self.min_chars <= self.max_chars // 2
            or type(self.max_heading_level) is not int
            or not 1 <= self.max_heading_level <= 6
        ):
            raise ValueError(
                "chunk sizes must satisfy 0 < min_chars <= max_chars / 2 "
                "and max_heading_level must be 1–6"
            )


class ChunkingV2Error(ValueError):
    """A parsed document cannot be converted without losing its identity."""


def _split_text(text: str, config: V2ChunkingConfig) -> list[str]:
    pieces = []
    while len(text) > config.max_chars:
        limit = config.max_chars
        if len(text) - limit < config.min_chars:
            limit = len(text) - config.min_chars
        cut = limit
        for pattern in (r"\n\n", r"[.!?。！？]\s*", r"\s+"):
            boundaries = [
                match.end()
                for match in re.finditer(pattern, text[:limit])
                if match.end() >= config.min_chars
            ]
            if boundaries:
                cut = boundaries[-1]
                break
        pieces.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        pieces.append(text)
    return [piece for piece in pieces if piece]


def block_evidence_profile(
    block: ParsedBlock, parsed: ParsedDocument
) -> dict[str, str]:
    """The parse-time character of one block, without inventing missing facts."""

    metadata = dict(block.metadata)
    role = block.block_type
    if (
        block.block_type == BlockType.PARAGRAPH.value
        and metadata.get("container") == "textbox"
    ):
        role = "textbox"
    elif block.block_type == BlockType.NOTE.value or metadata.get("source") == "notes":
        role = "note"
    elif metadata.get("source") == "image_ocr":
        role = "image_ocr"
    if metadata.get("ocr"):
        extraction = "ocr"
    elif parsed.source_format == "doc" or "libreoffice" in parsed.conversion_profile.casefold():
        extraction = "converted"
    elif parsed.source_format == "pdf":
        extraction = "text_layer"
    else:
        extraction = "native"
    review = (
        "required"
        if metadata.get("manual_review_required") == "true"
        else ""
    )
    return {
        "content_role": role,
        "extraction_method": extraction,
        "review_status": review,
        "formula_status": metadata.get("latex_status", ""),
    }


def _common_profile(
    blocks: tuple[ParsedBlock, ...], parsed: ParsedDocument
) -> dict[str, str]:
    """Keep a single character when all blocks agree; name a mixed parent."""

    profiles = [block_evidence_profile(block, parsed) for block in blocks]
    result = {}
    for key in (
        "content_role",
        "extraction_method",
        "review_status",
        "formula_status",
    ):
        values = {profile[key] for profile in profiles if profile[key]}
        if len(values) == 1:
            result[key] = next(iter(values))
        elif values:
            result[key] = "mixed"
        else:
            result[key] = ""
    return result


def _locator_text(locator: tuple[tuple[str, str], ...]) -> str:
    """Serialize the parser locator without losing table/sheet coordinates."""

    return ";".join(
        f"{str(key).strip()}={str(value).strip()}" for key, value in locator
    )


def _compact_section_path(path: str) -> str:
    if len(path) <= _MAX_SECTION_PATH_CHARS:
        return path
    segments = path.split(" > ")
    while len(segments) > 1 and len(" > ".join(segments)) > _MAX_SECTION_PATH_CHARS:
        segments.pop(0)
    return " > ".join(segments)


def section_path_map(blocks: tuple[ParsedBlock, ...]) -> dict[str, str]:
    """Heading breadcrumb for every block; readers reuse the chunking rule."""

    stack: list[tuple[int, str]] = []
    paths: dict[str, str] = {}
    last_slide: int | None = None
    for block in blocks:
        if block.position.kind == PositionKind.SLIDE.value:
            if last_slide is not None and block.position.start != last_slide:
                # A slide title must not leak into the next slide's evidence.
                stack = []
            last_slide = block.position.start
        if (
            block.block_type == BlockType.HEADING.value
            and block.heading_level
        ):
            while stack and stack[-1][0] >= block.heading_level:
                stack.pop()
            stack.append((block.heading_level, block.text.strip()))
        paths[block.block_id] = _compact_section_path(
            " > ".join(text for _, text in stack if text)
        )
    return paths


def _section_paths(
    blocks: tuple[ParsedBlock, ...], revision: RevisionRecord
) -> dict[str, tuple[str, str]]:
    """Map every block to its heading breadcrumb and a stable section ID."""

    paths: dict[str, tuple[str, str]] = {}
    for block_id, path in section_path_map(blocks).items():
        section_id = ""
        if path:
            digest = sha256(
                f"{revision.revision_id}\x1f{path}".encode()
            ).hexdigest()[:16]
            section_id = f"s-{digest}"
        paths[block_id] = (path, section_id)
    return paths


def _groups(
    blocks: tuple[ParsedBlock, ...], max_heading_level: int
) -> list[list[ParsedBlock]]:
    groups: list[list[ParsedBlock]] = []
    current: list[ParsedBlock] = []
    for block in blocks:
        # Speaker notes are page evidence, not slide-body prose.  Keeping them
        # in a separate parent preserves the body/notes identity in retrieval.
        if block.block_type == BlockType.NOTE.value:
            if current and any(
                item.block_type != BlockType.NOTE.value for item in current
            ):
                groups.append(current)
                current = []
            if (
                current
                and block.position.kind == PositionKind.SLIDE.value
                and current[-1].position.kind == PositionKind.SLIDE.value
                and block.position.start != current[-1].position.start
            ):
                # Notes-only consecutive slides must not merge into one chunk.
                groups.append(current)
                current = []
            current.append(block)
            continue
        if current and all(
            item.block_type == BlockType.NOTE.value for item in current
        ):
            groups.append(current)
            current = []
        if (
            current
            and block.position.kind == PositionKind.SLIDE.value
            and current[-1].position.kind == PositionKind.SLIDE.value
            and block.position.start != current[-1].position.start
        ):
            # A slide is the primary evidence boundary; never merge two slides
            # just because their combined text fits the parent budget.
            groups.append(current)
            current = []
        if block.block_type == BlockType.TABLE.value:
            # A heading immediately before a table belongs to that table record;
            # otherwise a heading-only chunk would carry no evidence.
            if current and all(
                item.block_type
                in {BlockType.HEADING.value, BlockType.CAPTION.value}
                for item in current
            ):
                groups.append(current + [block])
                current = []
            else:
                if current:
                    groups.append(current)
                    current = []
                groups.append([block])
            continue
        if (
            block.block_type == BlockType.HEADING.value
            and block.heading_level <= max_heading_level
            and current
        ):
            groups.append(current)
            current = [block]
            continue
        current.append(block)
    if current:
        groups.append(current)
    return groups


def _pieces(
    blocks: list[ParsedBlock], config: V2ChunkingConfig
) -> list[tuple[str, tuple[ParsedBlock, ...]]]:
    pieces: list[tuple[str, tuple[ParsedBlock, ...]]] = []
    current: list[ParsedBlock] = []
    current_chars = 0

    def flush() -> None:
        nonlocal current, current_chars
        if not current:
            return
        text = "\n\n".join(
            block.effective_text.strip() for block in current if block.effective_text
        ).strip()
        if text:
            pieces.append((text, tuple(current)))
        current = []
        current_chars = 0

    for block in blocks:
        text = block.effective_text.strip()
        if not text:
            # Keep an anchor for pictures that accompany text; the image does
            # not contribute characters, but its block ID must survive.
            if block.block_type == BlockType.IMAGE.value:
                current.append(block)
            continue
        if len(text) > config.max_chars:
            # A long OCR paragraph may be split away from its preceding image;
            # attach the image anchor to the first split piece as well.
            carried = tuple(
                item
                for item in current
                if item.block_type == BlockType.IMAGE.value
            )
            flush()
            for index, piece in enumerate(_split_text(text, config)):
                sources = (block,)
                if index == 0 and carried:
                    sources = carried + sources
                pieces.append((piece, sources))
            continue
        if current and current_chars + len(text) + 2 > config.max_chars:
            flush()
        current.append(block)
        current_chars += len(text) + 2
    flush()
    return pieces


def _table_pieces(
    block: ParsedBlock, config: V2ChunkingConfig
) -> list[tuple[str, TableData, int, int]]:
    """Return (text, table, first_data_row, last_data_row), rows 1-based.

    Header rows are 1..header_rows and are repeated in every piece; the data
    ranges let the caller build an exact ``Sheet!A1:K1;A2:K40`` locator instead
    of reusing the whole-sheet label for every split.
    """

    table = block.table
    if table is None:
        return [
            (piece, TableData(rows=((piece,),), header_rows=0), 0, 0)
            for piece in _split_text(block.effective_text, config)
        ]
    header = table.rows[: table.header_rows]
    data = table.rows[table.header_rows :]
    if not data:
        return [(table.text, table, 0, 0)]
    pieces: list[tuple[str, TableData, int, int]] = []
    batch: list[tuple[str, ...]] = []
    for offset, row in enumerate(data):
        candidate = TableData(
            rows=header + tuple(batch) + (row,),
            header_rows=table.header_rows,
            caption=table.caption,
        )
        if batch and len(candidate.text) > config.max_chars:
            current = TableData(
                rows=header + tuple(batch),
                header_rows=table.header_rows,
                caption=table.caption,
            )
            first = table.header_rows + 1 + offset - len(batch)
            last = table.header_rows + offset
            pieces.append((current.text, current, first, last))
            batch = [row]
        else:
            batch.append(row)
    if batch:
        current = TableData(
            rows=header + tuple(batch),
            header_rows=table.header_rows,
            caption=table.caption,
        )
        first = table.header_rows + 1 + len(data) - len(batch)
        last = table.header_rows + len(data)
        pieces.append((current.text, current, first, last))
    return pieces


_RANGE_LABEL = re.compile(
    r"^(?P<sheet>.*)!(?P<start_col>[A-Za-z]+)(?P<start_row>\d+)"
    r":(?P<end_col>[A-Za-z]+)(?P<end_row>\d+)$"
)


def _physical_label(
    base_label: str, table: TableData, header_rows: int, first: int, last: int
) -> str | None:
    """Label from the table's own physical row numbers (segmented sheets)."""

    numbers = table.row_numbers
    letters = table.column_letters
    if not numbers or not letters or "!" not in base_label:
        return None
    sheet = base_label.rsplit("!", 1)[0]
    start_col, end_col = letters[0], letters[-1]
    parts = []
    if header_rows:
        parts.append(
            f"{start_col}{numbers[0]}:{end_col}{numbers[header_rows - 1]}"
        )
    if first:
        parts.append(
            f"{start_col}{numbers[first - 1]}:{end_col}{numbers[last - 1]}"
        )
    if not parts:
        return None
    return f"{sheet}!" + ";".join(parts)


def _table_chunk_label(
    base_label: str,
    header_rows: int,
    first: int,
    last: int,
    *,
    table: TableData | None = None,
) -> str:
    """Build a physical cell range; block.position.start is the table's row 1.

    A sheet may have a title row at A1 and column names at A2; the parser sets
    the table block start to 2, so every emitted label must offset by that row
    instead of assuming the header is physical row 1.
    """

    if table is not None:
        physical = _physical_label(base_label, table, header_rows, first, last)
        if physical is not None:
            return physical
    match = _RANGE_LABEL.match(base_label)
    if match is None:
        return base_label
    start_col = match.group("start_col").upper()
    end_col = match.group("end_col").upper()
    base_start = int(match.group("start_row"))
    header = ""
    if header_rows:
        header = f"{start_col}{base_start}:{end_col}{base_start + header_rows - 1}"
    if not first:
        return f"{match.group('sheet')}!{header}" if header else base_label
    data = (
        f"{start_col}{base_start + first - 1}:"
        f"{end_col}{base_start + last - 1}"
    )
    if header:
        return f"{match.group('sheet')}!{header};{data}"
    return f"{match.group('sheet')}!{data}"


def _chunk_id(
    revision: RevisionRecord,
    parsed: ParsedDocument,
    position_kind: str,
    position_start: int,
    position_end: int,
    ordinal: int,
    text: str,
    config: V2ChunkingConfig,
) -> str:
    identity = json.dumps(
        [
            V2_CHUNKING_ALGORITHM,
            asdict(config),
            revision.revision_id,
            parsed.asset_id,
            position_kind,
            position_start,
            position_end,
            ordinal,
            text,
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{revision.revision_id}:{sha256(identity.encode()).hexdigest()}"


def _make_chunk(
    *,
    revision: RevisionRecord,
    parsed: ParsedDocument,
    config: V2ChunkingConfig,
    text: str,
    position_kind: str,
    position_start: int,
    position_end: int,
    position_label: str,
    source_blocks: tuple[ParsedBlock, ...],
    section_path: str,
    section_id: str,
    position_locator: str,
    content_role: str = "",
    ordinal: int,
) -> KnowledgeChunk:
    text = text.strip()
    if not text:
        raise ChunkingV2Error("cannot create an empty evidence chunk")
    profile = _common_profile(source_blocks, parsed)
    if content_role:
        profile["content_role"] = content_role
    return KnowledgeChunk(
        chunk_id=_chunk_id(
            revision,
            parsed,
            position_kind,
            position_start,
            position_end,
            ordinal,
            text,
            config,
        ),
        document_id=revision.revision_id,
        document_title=revision.title,
        text=text,
        source_path=revision.source_path,
        document_version=revision.revision_label,
        language=revision.language,
        category=revision.category,
        topic=revision.topic,
        page_start=position_start,
        page_end=position_end,
        family_id=revision.family_id,
        revision_label=revision.revision_label,
        asset_id=parsed.asset_id,
        document_kind=revision.document_kind,
        evidence_role=revision.evidence_role,
        usage_status=revision.usage_status,
        approval_status=revision.approval_status,
        scope=";".join(revision.scope),
        position_kind=position_kind,
        position_label=position_label,
        access_scope=revision.access_scope,
        source_block_ids=",".join(block.block_id for block in source_blocks),
        content_role=profile["content_role"],
        extraction_method=profile["extraction_method"],
        review_status=profile["review_status"],
        formula_status=profile["formula_status"],
        section_path=section_path,
        section_id=section_id,
        position_locator=position_locator,
        media_block_ids=",".join(
            block.block_id
            for block in source_blocks
            if block.block_type == BlockType.IMAGE.value
        ),
        tags=";".join(revision.tags),
        document_ordinal=ordinal,
    )


def chunk_parsed_document(
    parsed: ParsedDocument,
    revision: RevisionRecord,
    config: V2ChunkingConfig = V2ChunkingConfig(),
) -> list[KnowledgeChunk]:
    """Build canonical evidence without crossing revision or position identity."""

    if parsed.revision_id != revision.revision_id:
        raise ChunkingV2Error("parsed revision_id does not match the registry")
    if parsed.source_path != revision.source_path:
        raise ChunkingV2Error("parsed source_path does not match the registry")
    if not parsed.blocks:
        raise ChunkingV2Error("parsed document has no blocks to chunk")

    chunks: list[KnowledgeChunk] = []
    table_ordinal = 0
    paths = _section_paths(parsed.blocks, revision)
    for group in _groups(parsed.blocks, config.max_heading_level):
        if group[-1].block_type == BlockType.TABLE.value:
            table_ordinal += 1
            block = group[-1]
            table_caption = (
                block.table.caption.strip() if block.table is not None else ""
            )
            prefix = "\n\n".join(
                item.effective_text.strip()
                for item in group[:-1]
                if item.effective_text.strip()
                and not (
                    table_caption
                    and item.block_type == BlockType.CAPTION.value
                    and item.effective_text.strip() == table_caption
                )
            ).strip()
            base_label = block.position.label or f"table-{table_ordinal}"
            header_rows = block.table.header_rows if block.table is not None else 0
            spreadsheet = (
                block.position.kind == PositionKind.CELL_RANGE.value
            )
            for text, _table, first_row, last_row in _table_pieces(block, config):
                if prefix:
                    text = f"{prefix}\n\n{text}"
                position_kind = (
                    PositionKind.CELL_RANGE.value
                    if spreadsheet
                    else block.position.kind
                )
                section_path, section_id = paths[group[0].block_id]
                chunks.append(
                    _make_chunk(
                        revision=revision,
                        parsed=parsed,
                        config=config,
                        text=text,
                        position_kind=position_kind,
                        position_start=(
                            table_ordinal if spreadsheet else block.position.start
                        ),
                        position_end=(
                            table_ordinal if spreadsheet else block.position.end
                        ),
                        position_label=(
                            _table_chunk_label(
                                base_label,
                                header_rows,
                                first_row,
                                last_row,
                                table=block.table,
                            )
                            if spreadsheet
                            else base_label
                        ),
                        source_blocks=tuple(group),
                        section_path=section_path,
                        section_id=section_id,
                        position_locator=_locator_text(block.position.locator),
                        content_role=BlockType.TABLE.value,
                        ordinal=len(chunks),
                    )
                )
            continue
        kinds = {block.position.kind for block in group}
        if len(kinds) > 1:
            raise ChunkingV2Error(
                "a chunk group cannot mix position kinds: "
                + ", ".join(sorted(kinds))
            )
        for text, source_blocks in _pieces(group, config):
            first, last = source_blocks[0], source_blocks[-1]
            if first.position.kind != last.position.kind:
                raise ChunkingV2Error(
                    "a chunk cannot cross position kinds; split the block group"
                )
            section_path, section_id = paths[source_blocks[0].block_id]
            chunks.append(
                _make_chunk(
                    revision=revision,
                    parsed=parsed,
                    config=config,
                    text=text,
                    position_kind=first.position.kind,
                    position_start=first.position.start,
                    position_end=last.position.end,
                    position_label=first.position.label,
                    source_blocks=source_blocks,
                    section_path=section_path,
                    section_id=section_id,
                    position_locator=_locator_text(first.position.locator),
                    ordinal=len(chunks),
                )
            )
    covered = {
        block_id
        for chunk in chunks
        for block_id in chunk.source_block_id_list
    }
    orphans = [
        block
        for block in parsed.blocks
        if block.block_type == BlockType.IMAGE.value
        and block.block_id not in covered
    ]
    for image in orphans:
        section_path, section_id = paths[image.block_id]
        chunks.append(
            _make_chunk(
                revision=revision,
                parsed=parsed,
                config=config,
                text=image.caption.strip() or "[图片]",
                position_kind=image.position.kind,
                position_start=image.position.start,
                position_end=image.position.end,
                position_label=image.position.label,
                source_blocks=(image,),
                section_path=section_path,
                section_id=section_id,
                position_locator=_locator_text(image.position.locator),
                content_role=BlockType.IMAGE.value,
                ordinal=len(chunks),
            )
        )
    if not chunks:
        image = next(
            (
                block
                for block in parsed.blocks
                if block.block_type == BlockType.IMAGE.value
            ),
            None,
        )
        if image is not None:
            # A picture-only document/page must still have an evidence anchor;
            # it is short and has no identifier, so the index policy decides
            # whether its placeholder text is searchable.
            section_path, section_id = paths[image.block_id]
            chunks.append(
                _make_chunk(
                    revision=revision,
                    parsed=parsed,
                    config=config,
                    text=image.caption.strip() or "[图片]",
                    position_kind=image.position.kind,
                    position_start=image.position.start,
                    position_end=image.position.end,
                    position_label=image.position.label,
                    source_blocks=(image,),
                    section_path=section_path,
                    section_id=section_id,
                    position_locator=_locator_text(image.position.locator),
                    content_role=BlockType.IMAGE.value,
                    ordinal=0,
                )
            )
    if not chunks:
        raise ChunkingV2Error("parsed document produced no evidence chunks")
    if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
        raise ChunkingV2Error("duplicate chunk IDs")
    return chunks


def chunking_v2_statistics(chunks: list[KnowledgeChunk]) -> dict:
    """Small build-report summary; no quality claim is implied."""

    if not chunks:
        return {"chunk_count": 0}
    lengths = [len(chunk.text) for chunk in chunks]
    return {
        "algorithm": V2_CHUNKING_ALGORITHM,
        "chunk_count": len(chunks),
        "document_count": len({chunk.document_id for chunk in chunks}),
        "total_chars": sum(lengths),
        "min_chars": min(lengths),
        "max_chars": max(lengths),
        "chunks_under_20_chars": sum(length < 20 for length in lengths),
        "chunks_under_50_chars": sum(length < 50 for length in lengths),
        "by_position_kind": {
            kind: sum(chunk.effective_position_kind == kind for chunk in chunks)
            for kind in sorted({chunk.effective_position_kind for chunk in chunks})
        },
        "by_usage_status": {
            status: sum(chunk.usage_status == status for chunk in chunks)
            for status in sorted({chunk.usage_status for chunk in chunks})
        },
        "by_content_role": {
            role: sum(chunk.content_role == role for chunk in chunks)
            for role in sorted({chunk.content_role for chunk in chunks})
            if role
        },
        "by_extraction_method": {
            method: sum(chunk.extraction_method == method for chunk in chunks)
            for method in sorted({chunk.extraction_method for chunk in chunks})
            if method
        },
        "chunks_requiring_review": sum(
            chunk.review_status == "required" for chunk in chunks
        ),
        "chunks_with_unresolved_formula": sum(
            chunk.formula_status == "unresolved" for chunk in chunks
        ),
    }
