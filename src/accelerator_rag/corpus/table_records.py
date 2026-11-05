"""Row records for spreadsheets and row-addressable tables.

The record layer sits beside, not instead of, canonical evidence chunks.  It
answers exact identifier questions (terminal, signal, slot) and then points back
to the parent chunk that carries the table text, so the normal evidence and
citation path still decides what the answer may claim.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from accelerator_rag.corpus.parsed_document import ParsedDocument
from accelerator_rag.domain.position import BlockType, PositionKind


_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-:/\.]{1,}|[一-鿿]{2,}")
_TRAILING = ".,;:!?，。；：！？、…"


def _query_terms(text: str):
    """Exact lookup candidates: trimmed tokens plus short CJK n-grams.

    Natural Chinese questions do not put spaces around device names, so a
    whole-run token such as ``主控柜的`` must also try ``主控柜``.  The n-grams
    are matched against the exact cell-value index, never used for fuzzy
    ranking.
    """

    seen: set[str] = set()
    for token in _TOKEN.findall(text):
        token = token.strip().rstrip(_TRAILING)
        if len(token) < 2:
            continue
        if token not in seen:
            seen.add(token)
            yield token
        if re.fullmatch(r"[一-鿿]+", token):
            for size in (2, 3, 4):
                for start in range(0, len(token) - size + 1):
                    gram = token[start : start + size]
                    if gram not in seen:
                        seen.add(gram)
                        yield gram


def _text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def _keys(value: str) -> set[str]:
    normalized = _text(value).rstrip(_TRAILING)
    if not normalized:
        return set()
    return {normalized, normalized.replace(" ", "")}


@dataclass(frozen=True)
class TableRecord:
    record_id: str
    revision_id: str
    table_block_id: str
    sheet: str
    row_number: int
    headers: tuple[str, ...]
    cells: tuple[tuple[str, str], ...]
    row_text: str
    chunk_id: str = ""

    def values(self) -> dict[str, str]:
        return dict(self.cells)

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "revision_id": self.revision_id,
            "table_block_id": self.table_block_id,
            "sheet": self.sheet,
            "row_number": self.row_number,
            "headers": list(self.headers),
            "cells": [list(item) for item in self.cells],
            "row_text": self.row_text,
            "chunk_id": self.chunk_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TableRecord":
        return cls(
            record_id=data["record_id"],
            revision_id=data["revision_id"],
            table_block_id=data["table_block_id"],
            sheet=data["sheet"],
            row_number=int(data["row_number"]),
            headers=tuple(data.get("headers", ())),
            cells=tuple(tuple(item) for item in data.get("cells", ())),
            row_text=data.get("row_text", ""),
            chunk_id=data.get("chunk_id", ""),
        )


def _column_letters(table) -> tuple[str, ...]:
    if table.column_letters:
        return table.column_letters
    width = max(len(row) for row in table.rows)
    letters = []
    for index in range(1, width + 1):
        value = index
        text = ""
        while value:
            value, remainder = divmod(value - 1, 26)
            text = chr(65 + remainder) + text
        letters.append(text)
    return tuple(letters)


def build_table_records(parsed: ParsedDocument, chunks=()) -> tuple[TableRecord, ...]:
    """One record per data row of every cell-range table block."""

    chunk_by_block: dict[str, str] = {}
    for chunk in chunks:
        for block_id in getattr(chunk, "source_block_id_list", ()):
            chunk_by_block[block_id] = chunk.chunk_id
    records: list[TableRecord] = []
    for block in parsed.blocks:
        if (
            block.block_type != BlockType.TABLE.value
            or block.table is None
            or block.position.kind != PositionKind.CELL_RANGE.value
        ):
            continue
        table = block.table
        if table.header_rows < 1 or len(table.rows) <= table.header_rows:
            continue
        letters = _column_letters(table)
        headers = []
        for index, letter in enumerate(letters):
            values = []
            for header_row in table.rows[: table.header_rows]:
                value = header_row[index].strip() if index < len(header_row) else ""
                if value and value not in values:
                    values.append(value)
            headers.append(" / ".join(values))
        locator = block.position.locator_dict
        sheet = locator.get("sheet") or block.position.label.split("!")[0]
        numbers = table.row_numbers
        if not numbers:
            start = block.position.start
            numbers = tuple(range(start, start + len(table.rows)))
        for offset, row in enumerate(table.rows[table.header_rows :]):
            row_number = numbers[table.header_rows + offset]
            cells = tuple(
                (letter, row[index].strip() if index < len(row) else "")
                for index, letter in enumerate(letters)
            )
            records.append(
                TableRecord(
                    record_id=f"{block.block_id}:r{row_number}",
                    revision_id=parsed.revision_id,
                    table_block_id=block.block_id,
                    sheet=sheet,
                    row_number=row_number,
                    headers=tuple(headers),
                    cells=cells,
                    row_text=" | ".join(value for _, value in cells),
                    chunk_id=chunk_by_block.get(block.block_id, ""),
                )
            )
    return tuple(records)


class TableRecordIndex:
    """Exact, normalized identifier lookup; never prefix or fuzzy matching."""

    def __init__(self, records: tuple[TableRecord, ...]):
        self.records = tuple(records)
        self._by_key: dict[str, list[TableRecord]] = {}
        for record in self.records:
            for _, value in record.cells:
                for key in _keys(value):
                    bucket = self._by_key.setdefault(key, [])
                    if record not in bucket:
                        bucket.append(record)

    @classmethod
    def from_payload(cls, payload) -> "TableRecordIndex":
        return cls(tuple(TableRecord.from_dict(item) for item in payload or ()))

    def to_payload(self) -> list[dict]:
        return [record.to_dict() for record in self.records]

    def lookup(self, term: str, revision_ids=None) -> list[TableRecord]:
        records = []
        for key in _keys(term):
            for record in self._by_key.get(key, ()):
                if revision_ids is not None and record.revision_id not in revision_ids:
                    continue
                if record not in records:
                    records.append(record)
        records.sort(
            key=lambda item: (
                item.revision_id,
                item.sheet,
                item.row_number,
                item.table_block_id,
            )
        )
        return records

    def lookup_in_text(self, text: str, revision_ids=None) -> list[TableRecord]:
        records = []
        terms = list(_query_terms(text))
        # Identifier-like ASCII/PV/terminal tokens are more selective than a
        # common Chinese 2-gram; search them first so they are not crowded out.
        ascii_terms = [
            term for term in terms if re.search(r"[A-Za-z0-9]", term)
        ]
        cjk_terms = [term for term in terms if term not in ascii_terms]
        for token in [*ascii_terms, *cjk_terms]:
            for record in self.lookup(token, revision_ids=revision_ids):
                if record not in records:
                    records.append(record)
            if len(records) >= 200:
                return records
        return records
