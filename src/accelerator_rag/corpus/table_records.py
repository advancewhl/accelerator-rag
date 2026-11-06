"""Row records for spreadsheets and row-addressable tables.

The record layer sits beside, not instead of, canonical evidence chunks.  It
answers exact identifier questions (terminal, signal, slot) and then points back
to the parent chunk that carries the table text, so the normal evidence and
citation path still decides what the answer may claim.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
import unicodedata

from accelerator_rag.corpus.parsed_document import ParsedDocument
from accelerator_rag.domain.position import BlockType, PositionKind


_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-:/\.#]{1,}|[一-鿿]{2,}")
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


_LABEL_RANGE = re.compile(r"[A-Za-z]+(\d+):[A-Za-z]+(\d+)")


def _label_row_spans(label: str) -> list[tuple[int, int]]:
    """Physical row spans named by a chunk label such as ``S!A2:N2;A6:N36``."""

    if "!" not in label:
        return []
    ranges = label.rsplit("!", 1)[1]
    return [
        (int(match.group(1)), int(match.group(2)))
        for match in _LABEL_RANGE.finditer(ranges)
    ]


def _chunk_rows(chunks):
    """block_id -> [(chunk_id, data spans)] in chunk order.

    A sheet split into several parent chunks must send each row to the chunk
    whose data range holds it; a single block->chunk map points every row at
    whichever chunk was seen last.  The first span of a table chunk label is
    the repeated header, so only the remaining spans are data rows.
    """

    by_block: dict[str, list[tuple[str, list[tuple[int, int]]]]] = {}
    for chunk in chunks:
        spans = _label_row_spans(getattr(chunk, "position_label", "") or "")
        data_spans = spans[1:] if len(spans) > 1 else spans
        for block_id in getattr(chunk, "source_block_id_list", ()):
            by_block.setdefault(block_id, []).append((chunk.chunk_id, data_spans))
    return by_block


def _chunk_for_row(entries, row_number: int) -> str:
    for chunk_id, spans in entries:
        if any(low <= row_number <= high for low, high in spans):
            return chunk_id
    # A chunk without a parsable range (legacy/non-sheet table) is the only
    # holder of its block; several unparsable chunks cannot be told apart.
    if len(entries) == 1:
        return entries[0][0]
    return ""


def build_table_records(parsed: ParsedDocument, chunks=()) -> tuple[TableRecord, ...]:
    """One record per non-empty data row of every cell-range table block."""

    chunk_rows = _chunk_rows(chunks)
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
        metadata = dict(block.metadata)
        sheet = locator.get("sheet") or block.position.label.split("!")[0]
        group = metadata.get("group", "") or locator.get("group", "")
        numbers = table.row_numbers
        if not numbers:
            start = block.position.start
            numbers = tuple(range(start, start + len(table.rows)))
        entries = chunk_rows.get(block.block_id, [])
        for offset, row in enumerate(table.rows[table.header_rows :]):
            if not any(cell.strip() for cell in row):
                continue
            row_number = numbers[table.header_rows + offset]
            cells = tuple(
                (letter, row[index].strip() if index < len(row) else "")
                for index, letter in enumerate(letters)
            )
            record_headers = tuple(headers)
            if group:
                cells = cells + ((GROUP_COLUMN, group),)
                record_headers = record_headers + ("分组",)
            records.append(
                TableRecord(
                    record_id=f"{block.block_id}:r{row_number}",
                    revision_id=parsed.revision_id,
                    table_block_id=block.block_id,
                    sheet=sheet,
                    row_number=row_number,
                    headers=record_headers,
                    cells=cells,
                    row_text=" | ".join(value for _, value in cells if value),
                    chunk_id=_chunk_for_row(entries, row_number),
                )
            )
    return tuple(records)


GROUP_COLUMN = "_group"
_SPLIT = re.compile(r"[/:：()（）\[\]【】\s,，、;；]+")
_AREA_PREFIX = re.compile(r"^(un|la)(?=[a-z0-9])")
_PORT_PATTERNS = (
    re.compile(r"(?:端口|网口|port)\s*(?:号)?\s*[:：#]?\s*(\d{1,3})(?!\d)", re.I),
    re.compile(r"第\s*(\d{1,3})\s*(?:个)?(?:端口|网口|口)"),
    re.compile(r"(?<![A-Za-z0-9])(\d{1,3})\s*号?(?:端口|网口|口)(?!径)"),
)
_STRONG_ID = re.compile(r"(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9][A-Za-z0-9_\-:/\.#]{3,}")
_PORT_RANGE = re.compile(r"^\s*(\d{1,3})\s*(?:-|~|～|至|—)\s*(\d{1,3})\s*$")


def _squash(value: str) -> str:
    return re.sub(r"[^0-9a-z一-鿿]", "", _text(value))


def _value_keys(value: str) -> set[str]:
    """Exact keys of one cell: whole value, identifier forms and components."""

    keys = set(_keys(value))
    normalized = _text(value)
    if not normalized:
        return keys
    pieces = {normalized}
    for part in _SPLIT.split(normalized):
        part = part.strip("-_.").removesuffix("柜")
        if len(part) >= 2:
            pieces.add(part)
            for sub in part.split("-"):
                if len(sub) >= 2 and re.search(r"[a-z]", sub) and re.search(r"\d", sub):
                    pieces.add(sub)
    for piece in pieces:
        keys.add(piece)
        squashed = _squash(piece)
        if len(squashed) >= 2:
            keys.add("~" + squashed)
            stripped = _AREA_PREFIX.sub("", squashed)
            if stripped != squashed and len(stripped) >= 3:
                keys.add("~" + stripped)
    return keys


def _term_keys(term: str) -> set[str]:
    keys = set(_keys(term))
    normalized = _text(term).rstrip(_TRAILING).removesuffix("柜")
    if normalized:
        keys.add(normalized)
        squashed = _squash(normalized)
        if len(squashed) >= 2:
            keys.add("~" + squashed)
            stripped = _AREA_PREFIX.sub("", squashed)
            if stripped != squashed and len(stripped) >= 3:
                keys.add("~" + stripped)
    return keys


def query_ports(text: str) -> tuple[int, ...]:
    ports: list[int] = []
    for pattern in _PORT_PATTERNS:
        for match in pattern.finditer(text):
            number = int(match.group(1))
            if 0 < number <= 512 and number not in ports:
                ports.append(number)
    return tuple(ports)


def _port_contains(value: str, port: int) -> bool:
    value = value.strip()
    match = _PORT_RANGE.match(value)
    if match:
        low, high = sorted((int(match.group(1)), int(match.group(2))))
        return low <= port <= high
    for part in re.split(r"[,，、;；\s]+", value):
        if part.isdigit() and int(part) == port:
            return True
        sub = _PORT_RANGE.match(part)
        if sub:
            low, high = sorted((int(sub.group(1)), int(sub.group(2))))
            if low <= port <= high:
                return True
    return False


@dataclass(frozen=True)
class RecordHit:
    record: TableRecord
    score: float
    matched: tuple[str, ...]

    def to_dict(self) -> dict:
        payload = self.record.to_dict()
        payload["score"] = round(self.score, 4)
        payload["matched"] = list(self.matched)
        return payload


class TableRecordIndex:
    """Exact, normalized identifier lookup; never prefix or fuzzy matching.

    Keys are the whole cell value plus exact identifier forms of it (component
    split on separators, punctuation-free form, area prefix ``UN-``/``LA-``
    dropped).  Multi-term questions are ranked by the summed selectivity of
    distinct matched terms, so ``FEL2-CN01柜 DEVSW001 第20口`` prefers the row
    that satisfies all three over rows matching one common token.
    """

    def __init__(self, records: tuple[TableRecord, ...]):
        self.records = tuple(records)
        self._by_key: dict[str, list[int]] = {}
        self._port_columns: dict[int, tuple[int, ...]] = {}
        for position, record in enumerate(self.records):
            for _, value in record.cells:
                for key in _value_keys(value):
                    bucket = self._by_key.setdefault(key, [])
                    if not bucket or bucket[-1] != position:
                        bucket.append(position)
            port_columns = tuple(
                index
                for index, header in enumerate(record.headers)
                if "端口" in header or "网口" in header or header.lower() == "port"
            )
            if port_columns:
                self._port_columns[position] = port_columns

    @classmethod
    def from_payload(cls, payload) -> "TableRecordIndex":
        return cls(tuple(TableRecord.from_dict(item) for item in payload or ()))

    def to_payload(self) -> list[dict]:
        return [record.to_dict() for record in self.records]

    def _positions(self, keys, revision_ids) -> set[int]:
        found: set[int] = set()
        for key in keys:
            for position in self._by_key.get(key, ()):
                if (
                    revision_ids is not None
                    and self.records[position].revision_id not in revision_ids
                ):
                    continue
                found.add(position)
        return found

    def lookup(self, term: str, revision_ids=None) -> list[TableRecord]:
        positions = self._positions(_keys(term), revision_ids)
        records = [self.records[position] for position in positions]
        records.sort(
            key=lambda item: (
                item.revision_id,
                item.sheet,
                item.row_number,
                item.table_block_id,
            )
        )
        return records

    def search(self, text: str, revision_ids=None, *, limit: int = 50):
        """Ranked exact matches for every identifier and port in ``text``."""

        total = max(1, len(self.records))
        # Bare numbers hit serial-number columns everywhere; ports are
        # handled below as an explicit range constraint instead.
        terms = [term for term in _query_terms(text) if not term.isdigit()]
        matched_by_position: dict[int, dict[str, float]] = {}
        term_hits: list[tuple[str, set[int]]] = []
        for term in terms:
            positions = self._positions(_term_keys(term), revision_ids)
            if positions:
                term_hits.append((term, positions))
        for term, positions in term_hits:
            weight = math.log(1 + total / len(positions))
            for position in positions:
                matched_by_position.setdefault(position, {})[term] = weight
        for position, matched in matched_by_position.items():
            # A token and its own fragment (FEL2-CN01 / CN01) are one fact.
            for term in list(matched):
                if any(
                    other != term and term in other for other in matched
                ):
                    matched.pop(term, None)
        ports = query_ports(text)
        if ports and matched_by_position:
            for position in list(matched_by_position):
                record = self.records[position]
                columns = self._port_columns.get(position, ())
                values = record.cells
                for port in ports:
                    port_key = f"e{port:03d}"
                    in_column = any(
                        index < len(values) and _port_contains(values[index][1], port)
                        for index in columns
                    )
                    in_cable = any(
                        port_key in _value_keys(value) for _, value in values
                    )
                    if in_column or in_cable:
                        matched_by_position[position][f"端口{port}"] = math.log(
                            1 + total
                        )
        hits = [
            RecordHit(
                self.records[position],
                sum(matched.values()),
                tuple(sorted(matched)),
            )
            for position, matched in matched_by_position.items()
            if matched
        ]
        hits.sort(
            key=lambda hit: (
                -round(hit.score, 6),
                hit.record.revision_id,
                hit.record.sheet,
                hit.record.row_number,
            )
        )
        return hits[:limit]

    def unmatched_identifiers(self, text: str, revision_ids=None) -> list[str]:
        """Identifier-like query tokens (letters+digits) that match no row."""

        missing = []
        for term in _query_terms(text):
            if not _STRONG_ID.fullmatch(term):
                continue
            if not self._positions(_term_keys(term), revision_ids):
                missing.append(term)
        return missing

    def lookup_in_text(
        self,
        text: str,
        revision_ids=None,
        *,
        limit: int = 200,
        ratio: float = 0.85,
    ) -> list[TableRecord]:
        """Best-ranked records; rows matching fewer constraints drop out."""

        if self.unmatched_identifiers(text, revision_ids):
            # The question names a specific object (cabinet, cable, device)
            # that no row carries; rows matching only the remaining generic
            # constraints would be presented as the answer.
            return []
        hits = self.search(text, revision_ids, limit=limit)
        if not hits:
            return []
        best = hits[0].score
        return [hit.record for hit in hits if hit.score >= best * ratio]
