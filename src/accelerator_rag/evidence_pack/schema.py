"""Immutable records for question-driven evidence packs (phase 3).

The pack is the selection object: a set of locatable atoms that together cover
the relations a question needs, under a token budget.  Parent chunks stay
referenced for inspection; every claim must trace back to an atom, and every
atom to a verbatim source position.  Records never read ``gold``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
from typing import Iterable, Mapping

SCHEMA_VERSION = "phase3-evidence-pack-v1"

ROUTES = ("exact_record", "document_explanation", "cross_source")
CHANNELS = (
    "bm25",
    "row_exact",
    "fact",
    "revision",
    "neighbor",
    "literal",
    "structure",
    "graph",
    "dense",
    "archiver",
)
RELATION_NAMES = (
    "value",
    "unit",
    "condition",
    "counterpart",
    "scope",
    "enumeration",
    "version_left",
    "version_right",
    "requirement",
    "design",
    "test_result",
    "test_scope",
    "acceptance",
    "boundary",
    "provenance",
    "external_observation",
)
LOCATOR_KINDS = (
    "paragraph",
    "table_row",
    "table_header",
    "table_title",
    "footnote",
    "figure_caption",
    "section",
    "pdf_page",
    "slide",
    "external_observation",
)
EVIDENCE_ROLES = (
    "fact_support",
    "condition",
    "unit",
    "header",
    "provenance",
    "external_observation",
)
ENTITY_KINDS = (
    "device",
    "cabinet",
    "cable",
    "pv",
    "port",
    "revision",
    "number",
    "term",
)
CONFLICT_KINDS = ("value", "role", "version", "scope")
CONFLICT_RESOLUTIONS = (
    "preserved",
    "affects_target",
    "not_affecting",
    "unresolved",
)


class PackError(ValueError):
    """A record violates the phase-3 contract."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise PackError(code, message)


_TOKEN_ESTIMATE = re.compile(
    r"[A-Za-z0-9_]+(?:[.:/-][A-Za-z0-9_]+)*"
    r"|[一-鿿]"
    r"|[^\sA-Za-z0-9_一-鿿]"
)


def estimate_tokens(text: str) -> int:
    """Deterministic offline estimate: ASCII word / CJK char / punctuation.

    The production tokenizer is different; phase-4 comparisons must re-run with
    the production counter and report the difference.
    """

    return len(_TOKEN_ESTIMATE.findall(text))


def normalize_key(text: str) -> str:
    """Comparison form only; raw identifiers are never rewritten."""

    import unicodedata

    return unicodedata.normalize("NFKC", text).casefold().strip()


def cabinet_key(text: str) -> str:
    """Identity key for cabinet paths; ``LA-`` is a location prefix only.

    ``CAB-A-CN01``, ``CAB-A:CN-01`` and ``LA-CAB-A:CN-01`` share a key; ``EXT-CAB-A-CN01``
    keeps its ``ext-`` prefix and never collides with the local cabinet.
    """

    folded = normalize_key(text).replace(":", "-")
    folded = re.sub(r"^la-", "", folded)
    folded = re.sub(
        r"-cn-?0*(\d+)$",
        lambda match: f"-cn{int(match.group(1))}",
        folded,
    )
    return folded


def entity_in_text(entity: str, text: str, kind: str = "term") -> bool:
    """Kind-aware identifier matching; cabinets never match a longer path.

    ``CAB-A-CN01`` is not ``EXT-CAB-A-CN01``; a device id may appear inside a path
    such as ``LA-EXT-CAB-A-CN:DEVXSW02`` because the cabinet entity disambiguates.
    """

    if not entity:
        return False
    if kind == "cabinet":
        key = cabinet_key(entity)
        for match in re.finditer(
            r"(?:[a-z0-9]+[-:])+cn[-:]?0*\d+", text
        ):
            if cabinet_key(match.group(0)) == key:
                return True
        pattern = rf"(?<![a-z0-9_.:+/-]){re.escape(entity)}(?![a-z0-9_.:+/-])"
        return bool(re.search(pattern, text))
    if kind in {"port", "number"}:
        pattern = rf"(?<![a-z0-9_.-]){re.escape(entity)}(?![a-z0-9_.-])"
        return bool(re.search(pattern, text))
    if kind == "device":
        match = re.search(r"([a-z]+sw\d+)$", entity)
        key = match.group(1) if match else entity
        pattern = rf"(?<![a-z0-9_]){re.escape(key)}(?![a-z0-9_])"
        return bool(re.search(pattern, text))
    if kind in {"pv", "cable"}:
        pattern = rf"(?<![a-z0-9_]){re.escape(entity)}(?![a-z0-9_])"
        return bool(re.search(pattern, text))
    return entity in text


def atom_id_for(
    *,
    chunk_id: str,
    locator_kind: str,
    locator_label: str,
    excerpt: str,
    row_number: int | None = None,
    table_block_id: str = "",
    evidence_role: str = "fact_support",
) -> str:
    payload = "\x1f".join(
        (
            chunk_id,
            locator_kind,
            locator_label,
            str(row_number if row_number is not None else ""),
            table_block_id,
            evidence_role,
            excerpt,
        )
    )
    return "A" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


@dataclass(frozen=True)
class EntityNeed:
    raw: str
    normalized: str
    kind: str
    source: str = "query"

    def __post_init__(self) -> None:
        _require(bool(self.raw), "ENTITY_RAW", self.kind)
        _require(self.kind in ENTITY_KINDS, "ENTITY_KIND", self.kind)
        _require(bool(self.source), "ENTITY_SOURCE", self.raw)


@dataclass(frozen=True)
class RelationNeed:
    name: str
    required: bool
    reason: str
    role_filter: tuple[str, ...] = ()
    revision_filter: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(self.name in RELATION_NAMES, "RELATION_NAME", self.name)
        _require(bool(self.reason), "RELATION_REASON", self.name)
        for item in self.revision_filter:
            _require(item in {"left", "right"}, "RELATION_SIDE", item)


@dataclass(frozen=True)
class Needs:
    question_id: str
    route: str
    entities: tuple[EntityNeed, ...]
    relations: tuple[RelationNeed, ...]
    revision_ids: tuple[str, ...]
    version_pair: tuple[str, str] = ()
    comparison: bool = False
    reason: str = ""

    def __post_init__(self) -> None:
        _require(bool(self.question_id), "NEEDS_QUESTION", self.route)
        _require(self.route in ROUTES, "NEEDS_ROUTE", self.route)
        names = [item.name for item in self.relations]
        _require(len(names) == len(set(names)), "NEEDS_DUPLICATE_RELATION", ",".join(names))
        if self.version_pair:
            left, right = self.version_pair
            _require(bool(left) and bool(right) and left != right, "NEEDS_VERSION_PAIR", str(self.version_pair))

    def relation(self, name: str) -> RelationNeed | None:
        for item in self.relations:
            if item.name == name:
                return item
        return None

    def required_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.relations if item.required)


@dataclass(frozen=True)
class BudgetPolicy:
    route: str
    base_tokens: int
    max_parents: int
    max_rounds: int
    tokens: int
    relation_count: int

    def __post_init__(self) -> None:
        _require(self.route in ROUTES, "BUDGET_ROUTE", self.route)
        for name in ("base_tokens", "max_parents", "max_rounds", "tokens", "relation_count"):
            value = getattr(self, name)
            _require(type(value) is int and value >= 0, "BUDGET_VALUE", name)
        _require(1 <= self.tokens <= 6000, "BUDGET_LIMIT", str(self.tokens))

    def describe(self) -> dict:
        return {
            "route": self.route,
            "base_tokens": self.base_tokens,
            "relation_surcharge": max(0, self.relation_count - 3) * 150,
            "tokens": self.tokens,
            "max_parents": self.max_parents,
            "max_rounds": self.max_rounds,
            "estimator": "ascii_word+cjk_char+punct",
        }


@dataclass(frozen=True)
class Atom:
    atom_id: str
    chunk_id: str
    revision_id: str
    locator_kind: str
    locator_label: str
    excerpt: str
    source_role: str
    evidence_role: str
    route: str
    score: float
    tokens: int
    row_number: int | None = None
    table_block_id: str = ""
    fact_ids: tuple[str, ...] = ()
    conflict_group: str = ""
    aliases: tuple[str, ...] = ()
    external: Mapping | None = None

    def __post_init__(self) -> None:
        _require(bool(self.atom_id) and self.atom_id.startswith("A"), "ATOM_ID", self.atom_id)
        _require(bool(self.chunk_id) or self.locator_kind == "external_observation", "ATOM_CHUNK", self.atom_id)
        _require(self.locator_kind in LOCATOR_KINDS, "ATOM_LOCATOR", self.locator_kind)
        _require(bool(self.locator_label), "ATOM_LOCATOR_LABEL", self.atom_id)
        _require(bool(self.excerpt), "ATOM_EXCERPT", self.atom_id)
        _require(self.evidence_role in EVIDENCE_ROLES, "ATOM_EVIDENCE_ROLE", self.evidence_role)
        _require(self.route in CHANNELS, "ATOM_ROUTE", self.route)
        _require(self.tokens >= 0, "ATOM_TOKENS", self.atom_id)
        if self.locator_kind in {"table_row", "table_header", "table_title"}:
            _require(bool(self.table_block_id), "ATOM_TABLE_BLOCK", self.atom_id)
        if self.locator_kind in {"table_row", "table_header"}:
            _require(type(self.row_number) is int, "ATOM_ROW_NUMBER", self.atom_id)
        if self.locator_kind == "external_observation":
            _require(self.external is not None, "ATOM_EXTERNAL", self.atom_id)

    def sort_key(self) -> tuple:
        return (
            -self.score,
            self.chunk_id,
            self.locator_kind,
            self.row_number if self.row_number is not None else -1,
            self.atom_id,
        )

    def to_dict(self) -> dict:
        payload = {
            "atom_id": self.atom_id,
            "chunk_id": self.chunk_id,
            "revision_id": self.revision_id,
            "locator_kind": self.locator_kind,
            "locator_label": self.locator_label,
            "excerpt": self.excerpt,
            "chars": len(self.excerpt),
            "source_role": self.source_role,
            "evidence_role": self.evidence_role,
            "route": self.route,
            "score": round(self.score, 6),
            "tokens": self.tokens,
            "fact_ids": list(self.fact_ids),
        }
        if self.row_number is not None:
            payload["row_number"] = self.row_number
        if self.table_block_id:
            payload["table_block_id"] = self.table_block_id
        if self.conflict_group:
            payload["conflict_group"] = self.conflict_group
        if self.aliases:
            payload["aliases"] = list(self.aliases)
        if self.external is not None:
            payload["external"] = dict(self.external)
        return payload


@dataclass(frozen=True)
class Candidate:
    chunk_id: str
    score: float
    routes: tuple[Mapping, ...] = ()
    revision_id: str = ""
    source_role: str = ""

    def __post_init__(self) -> None:
        _require(bool(self.chunk_id), "CANDIDATE_CHUNK", "")
        _require(self.score >= 0, "CANDIDATE_SCORE", self.chunk_id)
        for route in self.routes:
            _require(route.get("channel") in CHANNELS, "CANDIDATE_CHANNEL", str(route))

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "score": round(self.score, 6),
            "revision_id": self.revision_id,
            "source_role": self.source_role,
            "routes": [dict(route) for route in self.routes],
        }


@dataclass(frozen=True)
class Coverage:
    name: str
    required: bool
    satisfied: bool
    atom_ids: tuple[str, ...] = ()
    missing: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        _require(self.name in RELATION_NAMES, "COVERAGE_NAME", self.name)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "required": self.required,
            "satisfied": self.satisfied,
            "atom_ids": list(self.atom_ids),
            "missing": self.missing,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Conflict:
    conflict_id: str
    kind: str
    subject: str
    attribute: str
    atom_ids: tuple[str, ...]
    resolution: str
    reason: str = ""

    def __post_init__(self) -> None:
        _require(bool(self.conflict_id), "CONFLICT_ID", "")
        _require(self.kind in CONFLICT_KINDS, "CONFLICT_KIND", self.kind)
        _require(self.resolution in CONFLICT_RESOLUTIONS, "CONFLICT_RESOLUTION", self.resolution)
        _require(len(self.atom_ids) >= 2, "CONFLICT_SIDES", self.conflict_id)

    def to_dict(self) -> dict:
        return {
            "conflict_id": self.conflict_id,
            "kind": self.kind,
            "subject": self.subject,
            "attribute": self.attribute,
            "atom_ids": list(self.atom_ids),
            "resolution": self.resolution,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Pack:
    atoms: tuple[Atom, ...]
    parents: tuple[Mapping, ...]
    tokens: int
    budget: int
    coverage: tuple[Coverage, ...]
    conflicts: tuple[Conflict, ...] = ()
    unresolved: tuple[str, ...] = ()
    selection: Mapping = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require(self.tokens <= self.budget, "PACK_BUDGET", f"{self.tokens}>{self.budget}")
        ids = [atom.atom_id for atom in self.atoms]
        _require(len(ids) == len(set(ids)), "PACK_DUPLICATE_ATOM", ",".join(ids))
        known = set(ids)
        for item in self.coverage:
            _require(set(item.atom_ids) <= known, "COVERAGE_ATOM", item.name)
        for conflict in self.conflicts:
            _require(len(conflict.atom_ids) >= 2, "CONFLICT_SIDES", conflict.conflict_id)
        parent_ids = [item["chunk_id"] for item in self.parents]
        _require(len(parent_ids) == len(set(parent_ids)), "PACK_DUPLICATE_PARENT", ",".join(parent_ids))

    def atom(self, atom_id: str) -> Atom:
        for item in self.atoms:
            if item.atom_id == atom_id:
                return item
        raise KeyError(atom_id)

    def to_dict(self) -> dict:
        return {
            "atoms": [atom.to_dict() for atom in self.atoms],
            "parents": [dict(item) for item in self.parents],
            "tokens": self.tokens,
            "chars": sum(len(atom.excerpt) for atom in self.atoms),
            "budget": self.budget,
            "coverage": [item.to_dict() for item in self.coverage],
            "conflicts": [item.to_dict() for item in self.conflicts],
            "unresolved": list(self.unresolved),
            "selection": dict(self.selection),
        }


def make_conflict_id(kind: str, subject: str, attribute: str) -> str:
    payload = "\x1f".join((kind, subject, attribute))
    return "C" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def dedupe_atoms(atoms: Iterable[Atom]) -> tuple[Atom, ...]:
    """Keep the highest-scored copy of an atom; merge fact ids."""

    merged: dict[str, Atom] = {}
    for atom in atoms:
        existing = merged.get(atom.atom_id)
        if existing is None or atom.score > existing.score:
            if existing is not None and existing.fact_ids:
                merged[atom.atom_id] = Atom(
                    **{
                        **atom.__dict__,
                        "fact_ids": tuple(
                            sorted(set(existing.fact_ids) | set(atom.fact_ids))
                        ),
                    }
                )
            else:
                merged[atom.atom_id] = atom
        elif atom.fact_ids:
            merged[atom.atom_id] = Atom(
                **{
                    **existing.__dict__,
                    "fact_ids": tuple(
                        sorted(set(existing.fact_ids) | set(atom.fact_ids))
                    ),
                }
            )
    return tuple(sorted(merged.values(), key=Atom.sort_key))
