"""Read-only access to the frozen rc.3 snapshot, scoped to dev/val families.

The phase-2 boundary is fixed: questions come only from the ``dev`` and ``val``
splits, and facts are built only for the document families those questions
name.  ``sealed-test`` is never opened.  Nothing here writes to the corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import fields as dataclass_fields
import json
from pathlib import Path
from typing import Iterable, Iterator

from accelerator_rag.corpus.parsed_document import ParsedDocument
from accelerator_rag.corpus.table_records import (
    GROUP_COLUMN,
    TableRecord,
    build_table_records,
)
from accelerator_rag.domain.knowledge import KnowledgeChunk

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "tmp" / "research-rc3"
QUESTIONS = ROOT / "data" / "evaluation" / "research-benchmark-300-v1"
ALLOWED_SPLITS = ("dev", "val")

_CHUNK_FIELDS = {item.name for item in dataclass_fields(KnowledgeChunk)}

BLOCK_LOCATOR_KINDS = {
    "paragraph": "paragraph",
    "list_item": "paragraph",
    "heading": "paragraph",
    "formula": "paragraph",
    "code": "paragraph",
    "note": "footnote",
    "caption": "figure_caption",
    "table": "table_row",
}


def split_family_ids(splits: Iterable[str] = ALLOWED_SPLITS) -> tuple[str, ...]:
    """Families named by the dev/val question files, in stable order."""

    selected = tuple(splits)
    for split in selected:
        if split not in ALLOWED_SPLITS:
            raise ValueError(f"split not allowed in phase 2: {split}")
    families: set[str] = set()
    for split in selected:
        path = QUESTIONS / split / "questions.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload["items"]:
            families.update(item["family_ids"])
    return tuple(sorted(families))


def split_questions(splits: Iterable[str] = ALLOWED_SPLITS) -> list[dict]:
    """The allowed questions themselves, for prototype anchoring only."""

    selected = tuple(splits)
    for split in selected:
        if split not in ALLOWED_SPLITS:
            raise ValueError(f"split not allowed in phase 2: {split}")
    items: list[dict] = []
    for split in selected:
        path = QUESTIONS / split / "questions.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        items.extend(payload["items"])
    return items


@dataclass
class CorpusScope:
    splits: tuple[str, ...]
    family_ids: tuple[str, ...]
    families: dict[str, dict]
    revisions: dict[str, dict]
    chunks_by_revision: dict[str, tuple[KnowledgeChunk, ...]] = field(
        default_factory=dict
    )
    parsed_by_revision: dict[str, ParsedDocument] = field(default_factory=dict)
    records_by_revision: dict[str, tuple[TableRecord, ...]] = field(
        default_factory=dict
    )

    def chunk_text(self) -> dict[str, str]:
        return {
            chunk.chunk_id: chunk.text
            for chunks in self.chunks_by_revision.values()
            for chunk in chunks
        }

    def chunks(self) -> Iterator[KnowledgeChunk]:
        for revision_id in sorted(self.chunks_by_revision):
            yield from self.chunks_by_revision[revision_id]

    def records(self) -> Iterator[TableRecord]:
        for revision_id in sorted(self.records_by_revision):
            yield from self.records_by_revision[revision_id]

    def revision_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.revisions))

    def chunk_index(self, revision_id: str) -> dict[str, KnowledgeChunk]:
        return {
            chunk.chunk_id: chunk
            for chunk in self.chunks_by_revision.get(revision_id, ())
        }

    def block_to_chunk(self, revision_id: str) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for chunk in self.chunks_by_revision.get(revision_id, ()):
            for block_id in chunk.source_block_id_list:
                mapping.setdefault(block_id, chunk.chunk_id)
        return mapping

    def record_at(self, revision_id: str, block_id: str, row: int):
        for record in self.records_by_revision.get(revision_id, ()):
            if record.table_block_id == block_id and record.row_number == row:
                return record
        return None


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_knowledge_chunk(payload: dict) -> KnowledgeChunk:
    return KnowledgeChunk(
        **{key: value for key, value in payload.items() if key in _CHUNK_FIELDS}
    )


def load_scope(
    splits: Iterable[str] = ALLOWED_SPLITS,
    family_ids: Iterable[str] | None = None,
    revision_ids: Iterable[str] | None = None,
    *,
    with_parsed: bool = True,
) -> CorpusScope:
    """Load the allowed families from the local rc.3 copy.

    ``family_ids`` defaults to the dev/val families; ``revision_ids`` narrows
    further, which tests use to stay small.
    """

    selected = tuple(splits)
    for split in selected:
        if split not in ALLOWED_SPLITS:
            raise ValueError(f"split not allowed in phase 2: {split}")
    if not BASE.exists():
        raise FileNotFoundError(f"rc.3 local copy is missing: {BASE}")

    inventories = BASE / "inventory"
    families_all = _read_json(inventories / "families.json")
    revisions_all = _read_json(inventories / "revisions.json")

    wanted = (
        tuple(sorted(set(family_ids)))
        if family_ids is not None
        else split_family_ids(selected)
    )
    missing = [family_id for family_id in wanted if family_id not in families_all]
    if missing:
        raise KeyError(f"unknown family ids: {missing}")
    allowed = set(split_family_ids(selected))
    outside = [family_id for family_id in wanted if family_id not in allowed]
    if outside:
        raise ValueError(
            f"family ids outside the dev/val scope: {outside}"
        )

    revisions = {
        revision_id: revisions_all[revision_id]
        for family_id in wanted
        for revision_id in families_all[family_id]["revision_ids"]
        if revision_id in revisions_all
    }
    if revision_ids is not None:
        keep = set(revision_ids)
        revisions = {
            revision_id: meta
            for revision_id, meta in revisions.items()
            if revision_id in keep
        }

    scope = CorpusScope(
        splits=selected,
        family_ids=wanted,
        families={family_id: families_all[family_id] for family_id in wanted},
        revisions=revisions,
    )
    for revision_id in sorted(revisions):
        chunk_path = BASE / "chunks" / f"{revision_id}.json"
        if not chunk_path.exists():
            raise FileNotFoundError(f"chunk file missing: {chunk_path}")
        payload = _read_json(chunk_path)
        chunks = tuple(load_knowledge_chunk(item) for item in payload["chunks"])
        scope.chunks_by_revision[revision_id] = chunks
        if with_parsed:
            parsed_path = BASE / "parsed" / f"{revision_id}.json"
            if not parsed_path.exists():
                raise FileNotFoundError(f"parsed file missing: {parsed_path}")
            parsed = ParsedDocument.from_dict(_read_json(parsed_path))
            scope.parsed_by_revision[revision_id] = parsed
            scope.records_by_revision[revision_id] = build_table_records(
                parsed, chunks
            )
        else:
            scope.records_by_revision[revision_id] = ()
    return scope


def block_locator_kind(block_type: str) -> str | None:
    """Map a parsed block type to its §4.1 locator kind; images are excluded."""

    return BLOCK_LOCATOR_KINDS.get(block_type)


# A test outline states the plan, a test report states results and an
# acceptance review states the conclusion.  The revision metadata's
# ``evidence_role`` collapses the latter two, so every fact layer resolves the
# role through this one table and never through the revision metadata alone.
DOCUMENT_SOURCE_ROLES = {
    "test_plan": "test_plan",
    "test_report": "test_result",
    "review_opinion": "acceptance_conclusion",
    "acceptance_report": "acceptance_conclusion",
}


def revision_source_role(scope: CorpusScope, revision_id: str) -> str:
    meta = scope.revisions.get(revision_id, {})
    document_kind = meta.get("document_kind", "") or ""
    if document_kind in DOCUMENT_SOURCE_ROLES:
        return DOCUMENT_SOURCE_ROLES[document_kind]
    return meta.get("evidence_role", "") or ""


def _is_separator(line: str) -> bool:
    text = line.strip().strip("|").strip()
    if "|" not in text:
        return False
    return all(
        part.strip().startswith(("-", ":")) and set(part.strip()) <= set("-: ")
        for part in text.split("|")
    )


def _split_markdown_row(line: str) -> tuple[str, ...]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    return tuple(part.strip() for part in text.split("|"))


@dataclass(frozen=True)
class MarkdownRow:
    row_number: int
    cells: tuple[str, ...]
    line: str


@dataclass(frozen=True)
class MarkdownTable:
    """A markdown table embedded in a paragraph/slide/page chunk."""

    chunk_id: str
    revision_id: str
    block_id: str
    table_index: int
    header: tuple[str, ...]
    header_line: str
    header_label: str
    rows: tuple[MarkdownRow, ...]
    label_prefix: str


def markdown_tables(
    chunk: KnowledgeChunk, revision_id: str | None = None
) -> tuple[MarkdownTable, ...]:
    """Parse the markdown tables a docx/pdf/slide chunk carries.

    Word and PDF tables arrive as markdown inside a paragraph or page chunk,
    so they never reach ``TableRecord``.  Each parsed row keeps the verbatim
    source line for citation; ``block_id`` is the chunk's first contributing
    block, falling back to the chunk id when the snapshot does not name one.
    """

    lines = chunk.text.splitlines()
    block_id = (
        chunk.source_block_id_list[0] if chunk.source_block_id_list else chunk.chunk_id
    )
    tables: list[MarkdownTable] = []
    index = 0
    table_index = 0
    while index < len(lines):
        if index + 1 >= len(lines) or not _is_separator(lines[index + 1]):
            index += 1
            continue
        header_line = lines[index].strip()
        if "|" not in header_line:
            index += 1
            continue
        header = _split_markdown_row(header_line)
        rows: list[MarkdownRow] = []
        cursor = index + 2
        row_number = 0
        while cursor < len(lines) and "|" in lines[cursor].strip():
            line = lines[cursor].strip()
            if not line:
                break
            if cursor + 1 < len(lines) and _is_separator(lines[cursor + 1]):
                break
            row_number += 1
            rows.append(
                MarkdownRow(
                    row_number=row_number,
                    cells=_split_markdown_row(line),
                    line=line,
                )
            )
            cursor += 1
        if rows:
            table_index += 1
            prefix = f"{chunk.position_label}#t{table_index}"
            tables.append(
                MarkdownTable(
                    chunk_id=chunk.chunk_id,
                    revision_id=revision_id or chunk.document_id,
                    block_id=block_id,
                    table_index=table_index,
                    header=header,
                    header_line=header_line,
                    header_label=f"{prefix}h",
                    rows=tuple(rows),
                    label_prefix=prefix,
                )
            )
        index = max(cursor, index + 2)
    return tuple(tables)


def verbatim_row_line(record: TableRecord, chunk_text: str) -> str | None:
    """The exact markdown line that carries ``record`` in its parent chunk.

    ``TableRecord.row_text`` drops empty cells, so it is not a verbatim
    substring of the markdown table.  Facts must quote the source line itself;
    this finds it by requiring every non-empty cell value to appear on one
    line, then falls back to the longest uniquely matching value.
    """

    anchors = [
        value
        for letter, value in record.cells
        if letter != GROUP_COLUMN and value
    ]
    if not anchors:
        return None
    lines = chunk_text.splitlines()
    matches = [line for line in lines if all(anchor in line for anchor in anchors)]
    if len(matches) == 1:
        return matches[0]
    for anchor in sorted(anchors, key=len, reverse=True):
        found = [line for line in lines if anchor in line]
        if len(found) == 1:
            return found[0]
    return None

