"""Read-only corpus, row, fact and revision index for evidence packs.

Everything is built from the frozen rc.3 snapshot and the phase-2 facts; no
index writes, no embeddings and no model calls happen here.  Optional dense and
Archiver sources are adapters supplied by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

from accelerator_rag.domain.knowledge import KnowledgeChunk
from accelerator_rag.facts.corpus import (
    ALLOWED_SPLITS,
    CorpusScope,
    load_scope,
    markdown_tables,
    verbatim_row_line,
)
from accelerator_rag.facts.schema import Fact, FactSet
from accelerator_rag.retrieval.bm25 import BM25Retriever

from .schema import (
    Atom,
    entity_in_text,
    estimate_tokens,
    normalize_key,
    atom_id_for,
)

_CJK = re.compile(r"[一-鿿]")
_SENTENCE_BREAK = re.compile(r"(?<=[。！？；])\s*|(?<=[.!?;])\s+")
_CN_NUMBER = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_ORDINAL = re.compile(r"第([一二三四五六七八九十两\d]+)版")
_ARCHIVE_LABEL = re.compile(
    r"归档(?:文档)?[（(](\d{4})(\d{2})?[）)]|归档(\d{4})(\d{2})?|归档副本|归档版"
)
_GENERIC_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.:+/-]{2,}|\d+(?:\.\d+)?(?:[-~～至—]\d+(?:\.\d+)?)?")


def _text(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value)).casefold().strip()


def _ordinal_value(raw: str) -> int | None:
    raw = raw.strip()
    if raw.isdigit():
        return int(raw)
    if raw in _CN_NUMBER:
        return _CN_NUMBER[raw]
    if raw.startswith("十") and len(raw) == 1:
        return 10
    if len(raw) == 2 and raw[0] in _CN_NUMBER and raw[1] == "十":
        return _CN_NUMBER[raw[0]] * 10
    if len(raw) == 3 and raw[1] == "十":
        return _CN_NUMBER[raw[0]] * 10 + _CN_NUMBER[raw[2]]
    return None


@dataclass(frozen=True)
class RevisionProfile:
    revision_id: str
    family_id: str
    label: str
    ordinal: int | None
    archive: str
    document_kind: str
    source_role: str
    title: str

    @property
    def is_archive(self) -> bool:
        return bool(self.archive)

    def sort_key(self) -> tuple:
        if self.is_archive:
            return (1, self.archive, self.revision_id)
        return (0, self.ordinal if self.ordinal is not None else 0, self.revision_id)

    def describe(self) -> dict:
        return {
            "revision_id": self.revision_id,
            "family_id": self.family_id,
            "label": self.label,
            "ordinal": self.ordinal,
            "archive": self.archive,
            "document_kind": self.document_kind,
            "source_role": self.source_role,
        }


def revision_profile(revision_id: str, meta: dict, family_id: str) -> RevisionProfile:
    label = str(meta.get("revision_label", "") or "")
    title = str(meta.get("document_title", "") or "")
    ordinal = None
    match = _ORDINAL.search(label)
    if match:
        ordinal = _ordinal_value(match.group(1))
    archive = ""
    match = _ARCHIVE_LABEL.search(label)
    if match:
        if match.group(1):
            archive = match.group(1) + (match.group(2) or "")
        elif match.group(3):
            archive = match.group(3) + (match.group(4) or "")
        else:
            archive = "unknown"
    if ordinal is None and not archive and "操作手册" in label:
        ordinal = 1
    return RevisionProfile(
        revision_id=revision_id,
        family_id=family_id,
        label=label,
        ordinal=ordinal,
        archive=archive,
        document_kind=str(meta.get("document_kind", "") or ""),
        source_role=str(meta.get("evidence_role", "") or ""),
        title=title,
    )


def role_from_headers(headers: tuple[str, ...]) -> str:
    """Structural role of a table row, from its column names only."""

    joined = " ".join(headers)
    if any(word in joined for word in ("结论", "验收", "评审", "符合性")):
        return "acceptance_conclusion"
    if any(word in joined for word in ("测试结果", "实测结果")):
        return "test_result"
    if any(word in joined for word in ("测试内容", "测试方法", "测试项")):
        return "test_plan"
    if any(word in joined for word in ("要求", "指标", "技术指标")):
        return "design_target"
    return ""


@dataclass(frozen=True)
class RowAtom:
    chunk_id: str
    revision_id: str
    family_id: str
    table_block_id: str
    sheet: str
    row_number: int
    headers: tuple[str, ...]
    cells: tuple[tuple[str, str], ...]
    line: str
    locator_label: str
    table_index: int = 0

    def to_atom(self, *, score: float, route: str = "row_exact") -> Atom:
        excerpt = self.line.strip()
        return Atom(
            atom_id=atom_id_for(
                chunk_id=self.chunk_id,
                locator_kind="table_row",
                locator_label=self.locator_label,
                excerpt=excerpt,
                row_number=self.row_number,
                table_block_id=self.table_block_id,
            ),
            chunk_id=self.chunk_id,
            revision_id=self.revision_id,
            locator_kind="table_row",
            locator_label=self.locator_label,
            excerpt=excerpt,
            source_role=role_from_headers(self.headers),
            evidence_role="fact_support",
            route=route,
            score=score,
            tokens=estimate_tokens(excerpt),
            row_number=self.row_number,
            table_block_id=self.table_block_id,
        )


@dataclass
class CorpusIndex:
    chunks: dict[str, KnowledgeChunk]
    families: dict[str, dict]
    revisions: dict[str, dict]
    revision_family: dict[str, str]
    profiles: dict[str, RevisionProfile]
    family_chunks: dict[str, tuple[str, ...]]
    family_revisions: dict[str, tuple[str, ...]]
    document_order: dict[str, tuple[str, ...]]
    rows: tuple[RowAtom, ...]
    row_by_chunk: dict[str, tuple[int, ...]]
    chunk_headers: dict[str, tuple[str, ...]]
    row_atoms: dict[str, RowAtom]
    facts: FactSet
    facts_by_chunk: dict[str, tuple[str, ...]]
    facts_by_revision: dict[str, tuple[str, ...]]
    facts_by_subject: dict[str, tuple[str, ...]]
    bm25: BM25Retriever

    def chunk(self, chunk_id: str) -> KnowledgeChunk:
        return self.chunks[chunk_id]

    def revision_of(self, chunk_id: str) -> str:
        return self.chunks[chunk_id].document_id

    def profile(self, revision_id: str) -> RevisionProfile:
        return self.profiles[revision_id]

    def chunk_tokens(self, chunk_id: str) -> int:
        return estimate_tokens(self.chunks[chunk_id].text)

    def chunk_facts(self, chunk_id: str) -> tuple[Fact, ...]:
        return tuple(self.facts.facts[fid] for fid in self.facts_by_chunk.get(chunk_id, ()))

    def revision_facts(self, revision_id: str) -> tuple[Fact, ...]:
        return tuple(
            self.facts.facts[fid]
            for fid in self.facts_by_revision.get(revision_id, ())
        )

    def rows_of(self, chunk_id: str) -> tuple[RowAtom, ...]:
        return tuple(self.rows[index] for index in self.row_by_chunk.get(chunk_id, ()))

    def family_for(self, chunk_id: str) -> str:
        return self.chunks[chunk_id].family_id or self.chunks[chunk_id].document_id

    def versions(self, family_id: str) -> tuple[RevisionProfile, ...]:
        return tuple(
            sorted(
                (self.profiles[rid] for rid in self.family_revisions.get(family_id, ())),
                key=RevisionProfile.sort_key,
            )
        )

    def bm25_search(
        self,
        query: str,
        *,
        top_k: int,
        revision_ids: set[str] | None = None,
        family_ids: set[str] | None = None,
    ) -> list[tuple[str, float]]:
        hits = self.bm25.search(query, top_k=max(top_k * 4, top_k))
        selected: list[tuple[str, float]] = []
        for hit in hits:
            chunk = hit.chunk
            if revision_ids is not None and chunk.document_id not in revision_ids:
                continue
            if family_ids is not None and self.family_for(chunk.chunk_id) not in family_ids:
                continue
            selected.append((chunk.chunk_id, float(hit.score)))
            if len(selected) == top_k:
                break
        return selected

    def sentence_atoms(
        self,
        chunk_id: str,
        *,
        score: float,
        route: str,
        query_terms: set[str] | None = None,
    ) -> tuple[Atom, ...]:
        chunk = self.chunks[chunk_id]
        atoms: list[Atom] = []
        for index, piece in enumerate(_sentences(chunk.text), 1):
            excerpt = piece.strip()
            if not excerpt:
                continue
            overlap = _term_overlap(excerpt, query_terms or set())
            atom = Atom(
                atom_id=atom_id_for(
                    chunk_id=chunk_id,
                    locator_kind=_locator_kind(chunk),
                    locator_label=f"{chunk.position_label or chunk.effective_position_kind}#s{index}",
                    excerpt=excerpt,
                ),
                chunk_id=chunk_id,
                revision_id=chunk.document_id,
                locator_kind=_locator_kind(chunk),
                locator_label=f"{chunk.position_label or chunk.effective_position_kind}#s{index}",
                excerpt=excerpt,
                source_role=chunk.evidence_role,
                evidence_role="fact_support",
                route=route,
                score=round(score + 0.1 * min(overlap, 8), 6),
                tokens=estimate_tokens(excerpt),
            )
            atoms.append(atom)
        return tuple(atoms)

    def all_paragraphs(self, revision_id: str) -> tuple[Atom, ...]:
        atoms: list[Atom] = []
        for chunk_id in self.document_order.get(revision_id, ()):
            chunk = self.chunks[chunk_id]
            if _locator_kind(chunk) not in {"paragraph", "section", "pdf_page", "slide"}:
                continue
            atoms.extend(
                self.sentence_atoms(
                    chunk_id, score=0.0, route="revision", query_terms=set()
                )
            )
        return tuple(atoms)

    def fact_atom(self, fact: Fact, *, score: float, route: str = "fact") -> Atom:
        citation = fact.citation
        return Atom(
            atom_id=atom_id_for(
                chunk_id=citation.chunk_id,
                locator_kind=citation.locator_kind,
                locator_label=citation.locator_label,
                excerpt=citation.excerpt,
                row_number=citation.row_number,
                table_block_id=citation.table_block_id,
                evidence_role=fact.evidence_role,
            ),
            chunk_id=citation.chunk_id,
            revision_id=fact.revision_id,
            locator_kind=citation.locator_kind,
            locator_label=citation.locator_label,
            excerpt=citation.excerpt,
            source_role=fact.source_role,
            evidence_role=fact.evidence_role,
            route=route,
            score=score,
            tokens=estimate_tokens(citation.excerpt),
            row_number=citation.row_number,
            table_block_id=citation.table_block_id,
            fact_ids=(fact.fact_id,),
        )

    def facts_matching(
        self,
        *,
        entity_terms: set[str],
        entity_kinds: dict[str, str],
        text_terms: set[str],
        revision_ids: set[str],
        limit: int = 120,
    ) -> list[tuple[Fact, float]]:
        scored: list[tuple[Fact, float]] = []
        seen: set[str] = set()
        for revision_id in sorted(revision_ids):
            for fact_id in self.facts_by_revision.get(revision_id, ()):
                fact = self.facts.facts[fact_id]
                score = 0.0
                subject = _text(fact.subject.raw_id)
                keys = {_text(key.value) for key in fact.subject.keys}
                if any(
                    entity_in_text(term, subject, entity_kinds.get(term, "term"))
                    for term in entity_terms
                ):
                    score += 6.0
                if any(
                    entity_in_text(term, key, entity_kinds.get(term, "term"))
                    for key in keys
                    for term in entity_terms
                ):
                    score += 5.0
                if isinstance(fact.raw_value, str) and _text(fact.raw_value) in entity_terms:
                    score += 4.0
                attribute = fact.attribute if isinstance(fact.attribute, str) else ""
                hits = _term_overlap(attribute, text_terms)
                score += min(hits, 3) * 0.8
                if fact.citation.excerpt and any(
                    term in _text(fact.citation.excerpt) for term in entity_terms if len(term) >= 4
                ):
                    score += 1.5
                if score <= 0:
                    continue
                if fact.fact_id in seen:
                    continue
                seen.add(fact.fact_id)
                scored.append((fact, score))
        scored.sort(key=lambda item: (-item[1], item[0].fact_id))
        return scored[:limit]

    def rows_matching(
        self,
        *,
        entity_terms: set[str],
        entity_kinds: dict[str, str],
        text_terms: set[str],
        family_ids: set[str],
        revision_ids: set[str] | None = None,
        limit: int = 120,
    ) -> list[tuple[RowAtom, float]]:
        scored: list[tuple[RowAtom, float]] = []
        for row in self.rows:
            if row.family_id not in family_ids:
                continue
            if revision_ids is not None and row.revision_id not in revision_ids:
                continue
            cells = {_text(value) for _, value in row.cells if value}
            line = _text(row.line)
            score = 0.0
            for term in entity_terms:
                kind = entity_kinds.get(term, "term")
                if any(entity_in_text(term, cell, kind) for cell in cells):
                    score += 8.0
                elif entity_in_text(term, line, kind):
                    score += 3.0
            score += min(_term_overlap(row.line, text_terms), 6) * 0.6
            if score <= 0:
                continue
            scored.append((row, score))
        scored.sort(key=lambda item: (-item[1], item[0].chunk_id, item[0].row_number))
        return scored[:limit]

    def neighbor_chunks(
        self, chunk_id: str, *, limit: int = 3
    ) -> tuple[str, ...]:
        revision_id = self.revision_of(chunk_id)
        order = list(self.document_order.get(revision_id, ()))
        if chunk_id not in order:
            return ()
        index = order.index(chunk_id)
        selected: list[str] = []
        for delta in (-2, -1, 1, 2):
            position = index + delta
            if 0 <= position < len(order):
                selected.append(order[position])
        return tuple(selected[:limit])

    def revision_ids_for_families(self, family_ids: set[str]) -> set[str]:
        return {
            rid
            for family_id in family_ids
            for rid in self.family_revisions.get(family_id, ())
        }


def _sentences(text: str) -> tuple[str, ...]:
    pieces: list[str] = []
    for part in _SENTENCE_BREAK.split(text):
        part = part.strip()
        if not part:
            continue
        if len(part) > 600:
            pieces.extend(part[i : i + 600] for i in range(0, len(part), 600))
        else:
            pieces.append(part)
    return tuple(pieces)


def _locator_kind(chunk: KnowledgeChunk) -> str:
    kind = chunk.effective_position_kind
    if kind == "pdf_page":
        return "pdf_page"
    if kind in {"paragraph", "section", "slide", "cell_range"}:
        return "paragraph" if kind == "cell_range" else kind
    return "section"


def _term_overlap(text: str, terms: set[str]) -> int:
    if not terms:
        return 0
    folded = _text(text)
    return sum(1 for term in terms if term and term in folded)


_PORT_SEPARATORS = ("-", "~", "～", "至", "—")


def port_intervals(text: str) -> list[tuple[int, int]]:
    """Closed integer intervals from a port cell; no upper bound is assumed."""

    normalized = unicodedata.normalize("NFKC", text)
    intervals: list[tuple[int, int]] = []
    for token in normalized.split(","):
        token = token.strip()
        if not token:
            continue
        for separator in _PORT_SEPARATORS:
            if separator in token:
                parts = [part.strip() for part in token.split(separator)]
                if len(parts) == 2 and all(part.isdigit() for part in parts):
                    low, high = int(parts[0]), int(parts[1])
                    if low > high:
                        low, high = high, low
                    intervals.append((low, high))
                break
        else:
            if token.isdigit():
                value = int(token)
                intervals.append((value, value))
    return intervals


def merge_port_intervals(intervals) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for low, high in sorted(intervals):
        if merged and low <= merged[-1][1] + 1:
            if high > merged[-1][1]:
                merged[-1] = (merged[-1][0], high)
        else:
            merged.append((low, high))
    return merged


def port_covers(spec: str, probe: str) -> bool:
    spec_intervals = port_intervals(spec)
    probe_intervals = port_intervals(probe)
    if not spec_intervals or not probe_intervals:
        return False
    for low, high in probe_intervals:
        if not any(s_low <= low and high <= s_high for s_low, s_high in spec_intervals):
            return False
    return True


def atom_entity_match(atom, entity: str, kind: str) -> bool:
    """Identifier match with interval containment for ports and cables."""

    text = normalize_key(" ".join([atom.excerpt, atom.locator_label]))
    if entity_in_text(entity, text, kind):
        return True
    if kind == "port":
        cells = [cell for cell in atom.excerpt.strip().strip("|").split("|")]
        probe = unicodedata.normalize("NFKC", entity)
        return any(port_covers(cell, probe) for cell in cells)
    return False


def query_terms(query: str) -> set[str]:
    """ASCII identifiers plus deterministic CJK 2-4 grams for row matching."""

    terms: set[str] = set()
    for token in _GENERIC_ID.findall(unicodedata.normalize("NFKC", query)):
        token = token.strip(".,;:()（）")
        if len(token) >= 3:
            terms.add(_text(token))
    for run in _CJK.findall(query):
        pass
    for run in re.findall(r"[一-鿿]{2,}", unicodedata.normalize("NFKC", query)):
        for size in (2, 3, 4):
            for start in range(0, len(run) - size + 1):
                terms.add(run[start : start + size])
    return terms


def entity_terms(entities) -> set[str]:
    return {item.normalized for item in entities if item.normalized}


def load_index(
    *,
    splits: tuple[str, ...] = ALLOWED_SPLITS,
    family_ids: tuple[str, ...] | None = None,
    facts_path: str | Path,
    with_parsed: bool = True,
    allow_family_ids: tuple[str, ...] | None = None,
) -> CorpusIndex:
    scope = load_scope(
        splits,
        family_ids=family_ids,
        with_parsed=with_parsed,
        allow_family_ids=allow_family_ids,
    )
    facts = FactSet.read_jsonl(facts_path)
    return build_index(scope, facts)


def build_index(scope: CorpusScope, facts: FactSet) -> CorpusIndex:
    chunks = {chunk.chunk_id: chunk for chunk in scope.chunks()}
    families = dict(scope.families)
    revisions = dict(scope.revisions)
    revision_family: dict[str, str] = {}
    family_revisions: dict[str, list[str]] = {}
    for family_id, meta in families.items():
        for revision_id in meta.get("revision_ids", ()):
            if revision_id in revisions:
                revision_family[revision_id] = family_id
                family_revisions.setdefault(family_id, []).append(revision_id)
    profiles = {
        revision_id: revision_profile(
            revision_id, meta, revision_family.get(revision_id, "")
        )
        for revision_id, meta in revisions.items()
    }
    family_chunks: dict[str, list[str]] = {}
    document_order: dict[str, list[str]] = {}
    for chunk in chunks.values():
        family_id = chunk.family_id or chunk.document_id
        family_chunks.setdefault(family_id, []).append(chunk.chunk_id)
        document_order.setdefault(chunk.document_id, []).append(chunk.chunk_id)
    for order in document_order.values():
        order.sort(
            key=lambda cid: (
                getattr(chunks[cid], "document_ordinal", 0),
                chunks[cid].page_start,
                chunks[cid].page_end,
                cid,
            )
        )
    rows: list[RowAtom] = []
    row_by_chunk: dict[str, list[int]] = {}
    for revision_id in sorted(scope.revisions):
        revision_chunks = list(scope.chunks_by_revision.get(revision_id, ()))
        chunk_by_id = {chunk.chunk_id: chunk for chunk in revision_chunks}
        for record in scope.records_by_revision.get(revision_id, ()):
            chunk = chunk_by_id.get(record.chunk_id)
            if chunk is None:
                continue
            line = verbatim_row_line(record, chunk.text)
            if line is None:
                continue
            label = f"{chunk.position_label or chunk.effective_position_kind}#r{record.row_number}"
            row = RowAtom(
                chunk_id=chunk.chunk_id,
                revision_id=revision_id,
                family_id=chunk.family_id or chunk.document_id,
                table_block_id=record.table_block_id,
                sheet=record.sheet,
                row_number=record.row_number,
                headers=record.headers,
                cells=record.cells,
                line=line,
                locator_label=label,
            )
            row_by_chunk.setdefault(chunk.chunk_id, []).append(len(rows))
            rows.append(row)
        for chunk in revision_chunks:
            if chunk.effective_position_kind == "cell_range":
                continue
            for table in markdown_tables(chunk, revision_id):
                for markdown_row in table.rows:
                    label = f"{table.label_prefix}r{markdown_row.row_number}"
                    row = RowAtom(
                        chunk_id=chunk.chunk_id,
                        revision_id=revision_id,
                        family_id=chunk.family_id or chunk.document_id,
                        table_block_id=table.block_id,
                        sheet="",
                        row_number=markdown_row.row_number,
                        headers=table.header,
                        cells=tuple(
                            zip(
                                table.header[: len(markdown_row.cells)]
                                or tuple(
                                    f"c{i}"
                                    for i in range(1, len(markdown_row.cells) + 1)
                                ),
                                markdown_row.cells,
                            )
                        ),
                        line=markdown_row.line,
                        locator_label=label,
                        table_index=table.table_index,
                    )
                    row_by_chunk.setdefault(chunk.chunk_id, []).append(len(rows))
                    rows.append(row)
    facts_by_chunk: dict[str, list[str]] = {}
    facts_by_revision: dict[str, list[str]] = {}
    chunk_headers: dict[str, set[str]] = {}
    for row in rows:
        chunk_headers.setdefault(row.chunk_id, set()).update(
            header.strip() for header in row.headers if header.strip()
        )
    header_map = {
        chunk_id: tuple(sorted(values))
        for chunk_id, values in chunk_headers.items()
    }
    facts_by_subject: dict[str, list[str]] = {}
    for fact in facts.sorted():
        facts_by_chunk.setdefault(fact.citation.chunk_id, []).append(fact.fact_id)
        facts_by_revision.setdefault(fact.revision_id, []).append(fact.fact_id)
        subject = _text(fact.subject.raw_id)
        facts_by_subject.setdefault(subject, []).append(fact.fact_id)
        for key in fact.subject.keys:
            facts_by_subject.setdefault(_text(key.value), []).append(fact.fact_id)
    row_atoms = {
        row.to_atom(score=0.0).atom_id: row for row in rows
    }
    return CorpusIndex(
        chunks=chunks,
        families=families,
        revisions=revisions,
        revision_family=revision_family,
        profiles=profiles,
        family_chunks={k: tuple(v) for k, v in family_chunks.items()},
        family_revisions={k: tuple(sorted(v)) for k, v in family_revisions.items()},
        document_order={k: tuple(v) for k, v in document_order.items()},
        rows=tuple(rows),
        row_by_chunk={k: tuple(v) for k, v in row_by_chunk.items()},
        chunk_headers=header_map,
        row_atoms=row_atoms,
        facts=facts,
        facts_by_chunk={k: tuple(sorted(v)) for k, v in facts_by_chunk.items()},
        facts_by_revision={k: tuple(sorted(v)) for k, v in facts_by_revision.items()},
        facts_by_subject={k: tuple(sorted(set(v))) for k, v in facts_by_subject.items()},
        bm25=BM25Retriever(list(chunks.values())),
    )


@dataclass(frozen=True)
class VersionMarker:
    kind: str
    value: object
    raw: str


def version_markers(query: str) -> tuple[VersionMarker, ...]:
    text = unicodedata.normalize("NFKC", query)
    found: list[tuple[int, VersionMarker]] = []
    for match in _ORDINAL.finditer(text):
        value = _ordinal_value(match.group(1))
        if value is not None:
            found.append((match.start(), VersionMarker("ordinal", value, match.group(0))))
    for match in re.finditer(r"(\d{4})\s*归档副本?", text):
        found.append((match.start(), VersionMarker("archive", match.group(1), match.group(0))))
    for word, kind in (
        ("初版", "ordinal"),
        ("上一版", "previous"),
        ("新版", "newest"),
        ("新版本", "newest"),
        ("旧版", "oldest"),
        ("旧版本", "oldest"),
        ("两版", "both"),
        ("各版", "both"),
        ("两个版本", "both"),
    ):
        for match in re.finditer(re.escape(word), text):
            value = 1 if kind == "ordinal" else None
            found.append((match.start(), VersionMarker(kind, value, match.group(0))))
    found.sort(key=lambda item: item[0])
    return tuple(item[1] for item in found)


def resolve_version_pair(
    query: str,
    *,
    family_ids: tuple[str, ...],
    index: CorpusIndex,
    explicit: tuple[str, ...] = (),
) -> tuple[str, str]:
    if len(explicit) == 2:
        profiles = [
            index.profiles[revision_id]
            for revision_id in explicit
            if revision_id in index.profiles
        ]
        if len(profiles) == 2:
            ordered = sorted(profiles, key=RevisionProfile.sort_key)
            return (ordered[0].revision_id, ordered[-1].revision_id)
        return (explicit[0], explicit[1])
    candidates: list[tuple[RevisionProfile, ...]] = []
    for family_id in family_ids:
        versions = tuple(
            profile
            for profile in index.versions(family_id)
            if profile.document_kind == "operation_manual"
            or profile.ordinal is not None
            or profile.is_archive
        )
        if len(versions) >= 2:
            candidates.append(versions)
    if not candidates:
        return ()
    markers = version_markers(query)
    best: tuple[int, tuple[RevisionProfile, ...]] | None = None
    for versions in candidates:
        score = _marker_match_score(markers, versions)
        order = (score, len(versions))
        if best is None or order > best[0]:
            best = (order, versions)
    versions = best[1]
    selected = _select_marker_profiles(markers, versions)
    if len(selected) < 2:
        selected = _default_pair(versions)
    if len(selected) < 2:
        return ()
    selected = sorted(selected, key=RevisionProfile.sort_key)
    return (selected[0].revision_id, selected[-1].revision_id)


def _marker_match_score(
    markers: tuple[VersionMarker, ...], versions: tuple[RevisionProfile, ...]
) -> int:
    score = 0
    for marker in markers:
        if marker.kind == "ordinal" and any(
            profile.ordinal == marker.value for profile in versions
        ):
            score += 2
        if marker.kind == "archive" and any(
            profile.archive.startswith(str(marker.value)) for profile in versions
        ):
            score += 2
        if marker.kind in {"newest", "oldest", "previous", "both"}:
            score += 1
    return score


def _select_marker_profiles(
    markers: tuple[VersionMarker, ...], versions: tuple[RevisionProfile, ...]
) -> list[RevisionProfile]:
    selected: list[RevisionProfile] = []
    for marker in markers:
        if marker.kind == "ordinal":
            match = next(
                (profile for profile in versions if profile.ordinal == marker.value),
                None,
            )
            if match is not None:
                selected.append(match)
        elif marker.kind == "archive":
            match = next(
                (
                    profile
                    for profile in versions
                    if profile.archive.startswith(str(marker.value))
                ),
                None,
            )
            if match is not None:
                selected.append(match)
        elif marker.kind == "newest":
            ranked = sorted(
                (profile for profile in versions if profile.ordinal is not None),
                key=lambda profile: profile.ordinal,
            )
            if ranked:
                selected.append(ranked[-1])
        elif marker.kind == "oldest":
            ranked = sorted(versions, key=RevisionProfile.sort_key)
            if ranked:
                selected.append(ranked[0])
    unique: dict[str, RevisionProfile] = {}
    for profile in selected:
        unique.setdefault(profile.revision_id, profile)
    chosen = list(unique.values())
    if len(chosen) == 1 and markers and any(
        marker.kind in {"newest", "previous", "both"} for marker in markers
    ):
        chosen.extend(_neighbor_for(chosen[0], versions))
    return chosen


def _neighbor_for(
    profile: RevisionProfile, versions: tuple[RevisionProfile, ...]
) -> list[RevisionProfile]:
    ordered = sorted(versions, key=RevisionProfile.sort_key)
    ids = [item.revision_id for item in ordered]
    if profile.revision_id not in ids:
        return []
    position = ids.index(profile.revision_id)
    if position > 0:
        return [ordered[position - 1]]
    if position + 1 < len(ordered):
        return [ordered[position + 1]]
    return []


def _default_pair(versions: tuple[RevisionProfile, ...]) -> list[RevisionProfile]:
    ordered = sorted(versions, key=RevisionProfile.sort_key)
    editions = [profile for profile in ordered if profile.ordinal is not None and not profile.is_archive]
    if len(editions) >= 2:
        return editions[:2]
    if editions and any(profile.is_archive for profile in ordered):
        archive = next(profile for profile in ordered if profile.is_archive)
        return [editions[0], archive]
    return ordered[:2]
