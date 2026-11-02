"""Format-neutral intermediate representation for parsing and citation.

The frozen PDF pipeline still emits ``ParsedPdfDocument``.  Schema v2 builds use
``ParsedDocument``: typed blocks plus an explicit position kind, so a Markdown
section or a PPTX slide is never presented as a PDF page.  Adapters in this
module let the existing PDF and Markdown parsers feed the new representation
without changing their chunk identities.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
from typing import Any

from accelerator_rag.corpus.schema_v2 import SourceFormat, source_format_for_path
from accelerator_rag.domain.position import BlockType, PositionKind


_SOURCE_ROOT_PARTS = ("data", "l0_raw")
_IDENTITY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_TABLE_SEPARATOR = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)


def _nonempty(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} 不能为空")
    if value != value.strip():
        raise ValueError(f"{name} 不能包含首尾空白")


def _safe_source_path(value: str) -> None:
    _nonempty(value, "source_path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != value
        or "\\" in value
        or path.parts[:2] != _SOURCE_ROOT_PARTS
    ):
        raise ValueError("source_path 必须是 data/l0_raw 下的安全相对路径")


def _enum_value(value: Any, enum_type, name: str) -> None:
    if value not in {item.value for item in enum_type}:
        raise ValueError(
            f"不支持的 {name}: {value}; 允许值: "
            + ", ".join(sorted(item.value for item in enum_type))
        )


def _pairs(value: Any, name: str) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    if not isinstance(value, (tuple, list)):
        raise ValueError(f"{name} 必须是键值对数组")
    pairs = []
    for item in value:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError(f"{name} 的每个元素必须是 [key, value]")
        key, text = item
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{name} 的 key 不能为空")
        pairs.append((key, str(text)))
    return tuple(pairs)


def _block_id(
    revision_id: str,
    asset_id: str,
    ordinal: int,
    block_type: str,
    position: "SourcePosition",
    text: str,
) -> str:
    identity = json.dumps(
        [
            revision_id,
            asset_id,
            ordinal,
            block_type,
            position.kind,
            position.start,
            position.end,
            position.label,
            list(position.locator),
            text,
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{revision_id}:b:{sha256(identity.encode()).hexdigest()}"


@dataclass(frozen=True)
class SourcePosition:
    """Explicit locator; ``page_start`` is not reused for non-paginated formats."""

    kind: str
    start: int
    end: int
    label: str = ""
    locator: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _enum_value(self.kind, PositionKind, "position.kind")
        if type(self.start) is not int or type(self.end) is not int:
            raise ValueError("position start/end 必须是整数")
        if not 1 <= self.start <= self.end:
            raise ValueError("position 必须满足 1 <= start <= end")
        if not isinstance(self.label, str) or self.label != self.label.strip():
            raise ValueError("position.label 必须是无首尾空白的字符串")
        object.__setattr__(self, "locator", _pairs(self.locator, "position.locator"))

    @property
    def locator_dict(self) -> dict[str, str]:
        return dict(self.locator)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "start": self.start,
            "end": self.end,
            "label": self.label,
            "locator": [list(item) for item in self.locator],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "SourcePosition":
        if not isinstance(data, dict):
            raise ValueError("SourcePosition 必须是 JSON 对象")
        return cls(
            kind=data["kind"],
            start=data["start"],
            end=data["end"],
            label=data.get("label", ""),
            locator=tuple(
                tuple(item) for item in data.get("locator", ())
            ),
        )


@dataclass(frozen=True)
class TableData:
    """Table content kept as rows; headers stay attached to every data slice."""

    rows: tuple[tuple[str, ...], ...]
    header_rows: int = 1
    caption: str = ""
    units: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.rows:
            raise ValueError("table 不能没有行")
        for row in self.rows:
            if not row:
                raise ValueError("table 行不能为空")
            for cell in row:
                if not isinstance(cell, str):
                    raise ValueError("table 单元格必须是字符串")
        if type(self.header_rows) is not int or not 0 <= self.header_rows <= len(
            self.rows
        ):
            raise ValueError("header_rows 超出表格行数")
        if not isinstance(self.caption, str) or self.caption != self.caption.strip():
            raise ValueError("table.caption 必须是无首尾空白的字符串")
        if any(not isinstance(unit, str) for unit in self.units):
            raise ValueError("table.units 必须是字符串数组")

    @property
    def text(self) -> str:
        lines = []
        if self.caption:
            lines.append(self.caption)
        nonempty_seen = 0
        for index, row in enumerate(self.rows):
            if not any(cell.strip() for cell in row):
                continue
            lines.append(" | ".join(cell.strip() for cell in row))
            nonempty_seen += 1
            if nonempty_seen == self.header_rows:
                lines.append(" | ".join("---" for _ in row))
        return "\n".join(lines)

    def data_rows(self) -> tuple[tuple[str, ...], ...]:
        return tuple(self.rows[self.header_rows :])

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": [list(row) for row in self.rows],
            "header_rows": self.header_rows,
            "caption": self.caption,
            "units": list(self.units),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "TableData":
        if not isinstance(data, dict):
            raise ValueError("TableData 必须是 JSON 对象")
        return cls(
            rows=tuple(tuple(row) for row in data["rows"]),
            header_rows=data.get("header_rows", 1),
            caption=data.get("caption", ""),
            units=tuple(data.get("units", ())),
        )


@dataclass(frozen=True)
class ParsedBlock:
    """One typed block with a stable ID and an explicit source position."""

    block_id: str
    block_type: str
    text: str
    position: SourcePosition
    heading_level: int = 0
    table: TableData | None = None
    caption: str = ""
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _nonempty(self.block_id, "block_id")
        _enum_value(self.block_type, BlockType, "block_type")
        if not isinstance(self.text, str):
            raise ValueError("block.text 必须是字符串")
        if not self.text.strip() and self.table is None:
            if self.block_type != BlockType.IMAGE.value:
                raise ValueError("block.text 不能为空")
        if not isinstance(self.position, SourcePosition):
            raise ValueError("block.position 必须是 SourcePosition")
        if type(self.heading_level) is not int or not 0 <= self.heading_level <= 6:
            raise ValueError("heading_level 必须在 0–6")
        if self.block_type == BlockType.HEADING.value and self.heading_level == 0:
            raise ValueError("heading block 必须给出 heading_level")
        if self.table is not None and not isinstance(self.table, TableData):
            raise ValueError("block.table 必须是 TableData")
        if not isinstance(self.caption, str):
            raise ValueError("block.caption 必须是字符串")
        object.__setattr__(self, "metadata", _pairs(self.metadata, "block.metadata"))

    @property
    def effective_text(self) -> str:
        if self.text.strip():
            return self.text
        return self.table.text if self.table is not None else ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "block_type": self.block_type,
            "text": self.text,
            "position": self.position.to_dict(),
            "heading_level": self.heading_level,
            "table": self.table.to_dict() if self.table is not None else None,
            "caption": self.caption,
            "metadata": [list(item) for item in self.metadata],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ParsedBlock":
        if not isinstance(data, dict):
            raise ValueError("ParsedBlock 必须是 JSON 对象")
        table = data.get("table")
        return cls(
            block_id=data["block_id"],
            block_type=data["block_type"],
            text=data.get("text", ""),
            position=SourcePosition.from_dict(data["position"]),
            heading_level=data.get("heading_level", 0),
            table=TableData.from_dict(table) if table is not None else None,
            caption=data.get("caption", ""),
            metadata=tuple(tuple(item) for item in data.get("metadata", ())),
        )


@dataclass(frozen=True)
class ParsedDocument:
    """Normalized content for one immutable revision/asset."""

    revision_id: str
    asset_id: str
    source_path: str
    source_format: str
    title: str
    blocks: tuple[ParsedBlock, ...]
    warnings: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()
    parser_profile: str = "unknown"
    conversion_profile: str = ""
    ocr_profile: str = ""

    def __post_init__(self) -> None:
        for name in ("revision_id", "asset_id"):
            _nonempty(getattr(self, name), name)
            if not _IDENTITY_PATTERN.fullmatch(getattr(self, name)):
                raise ValueError(f"{name} 必须是小写 slug")
        _safe_source_path(self.source_path)
        _enum_value(self.source_format, SourceFormat, "source_format")
        expected = source_format_for_path(self.source_path)
        if expected is not SourceFormat.OTHER and expected.value != self.source_format:
            raise ValueError(
                f"source_path 扩展名要求 source_format={expected.value}"
            )
        _nonempty(self.title, "title")
        _nonempty(self.parser_profile, "parser_profile")
        for name in ("conversion_profile", "ocr_profile"):
            value = getattr(self, name)
            if not isinstance(value, str) or value != value.strip():
                raise ValueError(f"{name} 必须是无首尾空白的字符串")
        if not isinstance(self.blocks, tuple) or any(
            not isinstance(block, ParsedBlock) for block in self.blocks
        ):
            raise ValueError("blocks 必须是 ParsedBlock 元组")
        if not self.blocks and not self.warnings:
            raise ValueError("空文档必须带有 warnings，不能静默通过")
        if len({block.block_id for block in self.blocks}) != len(self.blocks):
            raise ValueError("block_id 不能重复")
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(
            self, "metadata", _pairs(self.metadata, "document.metadata")
        )

    @property
    def text(self) -> str:
        return "\n\n".join(
            block.effective_text for block in self.blocks if block.effective_text
        )

    @property
    def position_kinds(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(block.position.kind for block in self.blocks))

    def blocks_of(self, block_type: str) -> tuple[ParsedBlock, ...]:
        return tuple(
            block for block in self.blocks if block.block_type == block_type
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "asset_id": self.asset_id,
            "source_path": self.source_path,
            "source_format": self.source_format,
            "title": self.title,
            "blocks": [block.to_dict() for block in self.blocks],
            "warnings": list(self.warnings),
            "metadata": [list(item) for item in self.metadata],
            "parser_profile": self.parser_profile,
            "conversion_profile": self.conversion_profile,
            "ocr_profile": self.ocr_profile,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ParsedDocument":
        if not isinstance(data, dict):
            raise ValueError("ParsedDocument 必须是 JSON 对象")
        return cls(
            revision_id=data["revision_id"],
            asset_id=data["asset_id"],
            source_path=data["source_path"],
            source_format=data["source_format"],
            title=data["title"],
            blocks=tuple(
                ParsedBlock.from_dict(item) for item in data.get("blocks", ())
            ),
            warnings=tuple(data.get("warnings", ())),
            metadata=tuple(tuple(item) for item in data.get("metadata", ())),
            parser_profile=data.get("parser_profile", "unknown"),
            conversion_profile=data.get("conversion_profile", ""),
            ocr_profile=data.get("ocr_profile", ""),
        )


def _metadata_pairs(metadata: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    pairs = []
    for key in sorted(metadata):
        value = metadata[key]
        if isinstance(value, (str, int, float, bool)):
            pairs.append((str(key), str(value)))
    return tuple(pairs)


def _page_blocks(page) -> list:
    blocks = list(page.blocks)
    if blocks:
        return blocks
    if not page.text.strip():
        return []
    from accelerator_rag.corpus.pdf_parser import PdfTextBlock

    return [
        PdfTextBlock(
            block_number=0,
            block_type=0,
            bbox=(0.0, 0.0, page.width, page.height),
            text=page.text,
        )
    ]


def from_parsed_pdf(
    parsed,
    *,
    revision_id: str,
    asset_id: str | None = None,
    source_format: str = SourceFormat.PDF.value,
    title: str | None = None,
    parser_profile: str = "pymupdf-blocks-v1",
) -> ParsedDocument:
    """Adapt the frozen PDF parser output into typed blocks."""

    resolved_asset = asset_id or f"asset-{revision_id}-original"
    resolved_title = (
        title
        or str(parsed.metadata.get("title", "")).strip()
        or parsed.file_name
    )
    blocks: list[ParsedBlock] = []
    for page in parsed.pages:
        for pdf_block in _page_blocks(page):
            text = pdf_block.text.strip()
            if not text:
                continue
            position = SourcePosition(
                kind=PositionKind.PDF_PAGE.value,
                start=page.page_number,
                end=page.page_number,
                label=f"page-{page.page_number}",
                locator=(
                    (
                        "bbox",
                        ",".join(f"{value:.1f}" for value in pdf_block.bbox),
                    ),
                    ("block", str(pdf_block.block_number)),
                ),
            )
            ordinal = len(blocks)
            blocks.append(
                ParsedBlock(
                    block_id=_block_id(
                        revision_id,
                        resolved_asset,
                        ordinal,
                        BlockType.PARAGRAPH.value,
                        position,
                        text,
                    ),
                    block_type=BlockType.PARAGRAPH.value,
                    text=text,
                    position=position,
                )
            )
    return ParsedDocument(
        revision_id=revision_id,
        asset_id=resolved_asset,
        source_path=parsed.source_path,
        source_format=source_format,
        title=resolved_title,
        blocks=tuple(blocks),
        warnings=tuple(parsed.warnings),
        metadata=_metadata_pairs(parsed.metadata),
        parser_profile=parser_profile,
    )


def _table_rows(lines: list[str]) -> tuple[tuple[str, ...], ...]:
    rows = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            stripped = stripped[1:]
        if stripped.endswith("|"):
            stripped = stripped[:-1]
        rows.append(tuple(cell.strip() for cell in stripped.split("|")))
    return tuple(rows)


def _split_markdown_blocks(
    text: str,
    *,
    revision_id: str,
    asset_id: str,
    section: int,
) -> tuple[list[ParsedBlock], str]:
    lines = text.splitlines()
    blocks: list[ParsedBlock] = []
    title = ""
    buffer: list[str] = []

    def position() -> SourcePosition:
        return SourcePosition(
            kind=PositionKind.SECTION.value,
            start=section,
            end=section,
            label=f"section-{section}",
            locator=(("section", str(section)),),
        )

    def emit(block_type: str, value: str, level: int = 0) -> None:
        value = value.strip()
        if not value:
            return
        ordinal = len(blocks)
        pos = position()
        blocks.append(
            ParsedBlock(
                block_id=_block_id(
                    revision_id, asset_id, ordinal, block_type, pos, value
                ),
                block_type=block_type,
                text=value,
                position=pos,
                heading_level=level,
            )
        )

    def flush() -> None:
        if buffer:
            emit(BlockType.PARAGRAPH.value, "\n".join(buffer))
            buffer.clear()

    index = 0
    while index < len(lines):
        line = lines[index]
        heading = _HEADING.match(line.lstrip())
        if heading:
            flush()
            level = len(heading.group(1))
            heading_text = heading.group(2).strip()
            if not title:
                title = heading_text
            emit(BlockType.HEADING.value, heading_text, level)
            index += 1
            continue
        fence = _FENCE.match(line)
        if fence:
            flush()
            fence_lines = [line]
            marker = fence.group(1)
            index += 1
            while index < len(lines):
                fence_lines.append(lines[index])
                if lines[index].strip().startswith(marker):
                    index += 1
                    break
                index += 1
            emit(BlockType.CODE.value, "\n".join(fence_lines))
            continue
        if "|" in line and index + 1 < len(lines):
            if _TABLE_SEPARATOR.match(lines[index + 1]):
                flush()
                table_lines = [line, lines[index + 1]]
                index += 2
                while index < len(lines) and "|" in lines[index]:
                    if not lines[index].strip():
                        break
                    table_lines.append(lines[index])
                    index += 1
                rows = _table_rows(table_lines)
                data_rows = (rows[0],) + rows[2:]
                ordinal = len(blocks)
                pos = position()
                table = TableData(rows=data_rows, header_rows=1)
                blocks.append(
                    ParsedBlock(
                        block_id=_block_id(
                            revision_id,
                            asset_id,
                            ordinal,
                            BlockType.TABLE.value,
                            pos,
                            table.text,
                        ),
                        block_type=BlockType.TABLE.value,
                        text=table.text,
                        position=pos,
                        table=table,
                    )
                )
                continue
        if line.strip():
            buffer.append(line)
        elif buffer:
            flush()
        index += 1
    flush()
    return blocks, title


def from_markdown_parsed(
    parsed,
    *,
    revision_id: str,
    asset_id: str | None = None,
    title: str | None = None,
    parser_profile: str = "markdown-sections-v2",
) -> ParsedDocument:
    """Adapt section-shaped Markdown output into heading/paragraph/table blocks."""

    resolved_asset = asset_id or f"asset-{revision_id}-original"
    blocks: list[ParsedBlock] = []
    document_title = ""
    for page in parsed.pages:
        section = page.page_number
        text = page.text.strip()
        if not text:
            continue
        front_matter = ""
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                front_matter = text[: end + 4].strip()
                text = text[end + 4 :].lstrip("\n")
        if front_matter:
            position = SourcePosition(
                kind=PositionKind.SECTION.value,
                start=section,
                end=section,
                label=f"section-{section}-front-matter",
                locator=(("section", str(section)), ("part", "front-matter")),
            )
            ordinal = len(blocks)
            blocks.append(
                ParsedBlock(
                    block_id=_block_id(
                        revision_id,
                        resolved_asset,
                        ordinal,
                        BlockType.NOTE.value,
                        position,
                        front_matter,
                    ),
                    block_type=BlockType.NOTE.value,
                    text=front_matter,
                    position=position,
                )
            )
        section_blocks, section_title = _split_markdown_blocks(
            text,
            revision_id=revision_id,
            asset_id=resolved_asset,
            section=section,
        )
        document_title = document_title or section_title
        blocks.extend(section_blocks)
    return ParsedDocument(
        revision_id=revision_id,
        asset_id=resolved_asset,
        source_path=parsed.source_path,
        source_format=SourceFormat.MD.value,
        title=title
        or document_title
        or str(parsed.metadata.get("title", "")).strip()
        or parsed.file_name,
        blocks=tuple(blocks),
        warnings=tuple(parsed.warnings),
        metadata=_metadata_pairs(parsed.metadata),
        parser_profile=parser_profile,
    )


def document_text(document: ParsedDocument) -> str:
    """Readable plain text for audits; never used as the retrieval payload."""

    return document.text


# Public alias for adapters that need the same stable block identity.
make_block_id = _block_id
