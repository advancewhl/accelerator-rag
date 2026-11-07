"""Sourced engineering facts with explicit unknowns.

Every fact records the nine facets required by the research plan §4.1: object,
attribute, raw value, unit, comparison relation, condition, revision, evidence
role and original position.  A facet the source does not support stays
``UNKNOWN`` and is named in ``unknown_fields``; extractors must never fill it by
inference.  The validator enforces that ``unknown_fields`` is exactly the set of
facets that are unknown, so a reviewer can check completeness mechanically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Iterable, Mapping

SCHEMA_VERSION = "phase2-fact-v1"


class _Unknown:
    """Sentinel for "the source does not support this field"."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNKNOWN"

    __str__ = __repr__

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Unknown)

    def __hash__(self) -> int:
        return hash(_Unknown)

    def __reduce__(self):
        return (_unknown, ())


def _unknown() -> _Unknown:
    return UNKNOWN


UNKNOWN = _Unknown()

# The nine §4.1 facets, split where one facet carries two distinct roles.
FACETS = (
    "subject",
    "attribute",
    "raw_value",
    "unit",
    "comparator",
    "conditions",
    "revision_id",
    "source_role",
    "evidence_role",
    "citation",
)

LAYERS = ("parameter", "connectivity", "process")
COMPARATORS = ("eq", "lt", "le", "gt", "ge", "range", "in", "unknown")
VALUE_KINDS = (
    "number",
    "quantity",
    "text",
    "enum",
    "version",
    "boolean",
    "date",
    "range",
    "unknown",
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
)
EVIDENCE_ROLES = ("fact_support", "condition", "unit", "header", "provenance")
ENTITY_KINDS = (
    "cabinet",
    "device",
    "switch",
    "port",
    "port_range",
    "cable",
    "vlan",
    "pv",
    "system",
    "module",
    "procedure",
    "step",
    "requirement",
    "test_item",
    "acceptance_item",
    "section",
    "document",
)
KEY_BASES = (
    "parenthesized",
    "prefix",
    "whole",
    "row_column",
    "table_title",
    "table_header",
    "section_heading",
    "explicit_in_text",
)
SCOPE_SOURCES = (
    "table_title",
    "table_header",
    "row_column",
    "section_heading",
    "document_title",
    "explicit_in_text",
)


class FactError(ValueError):
    """A fact violates the phase-2 contract."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise FactError(code, message)


@dataclass(frozen=True)
class IdentityKey:
    """One identity component taken verbatim from the source."""

    name: str
    value: str
    basis: str

    def __post_init__(self) -> None:
        _require(bool(self.name) and self.name.isascii(), "KEY_NAME", self.name)
        _require(bool(self.value), "KEY_VALUE", self.name)
        _require(
            self.basis in KEY_BASES, "KEY_BASIS", f"{self.name}={self.basis}"
        )


@dataclass(frozen=True)
class EntityRef:
    """An object as the source names it; scope stays unknown unless stated."""

    kind: str
    raw_id: str
    scope: str | _Unknown = UNKNOWN
    scope_source: str | _Unknown = UNKNOWN
    keys: tuple[IdentityKey, ...] = ()

    def __post_init__(self) -> None:
        _require(self.kind in ENTITY_KINDS, "ENTITY_KIND", self.kind)
        _require(bool(self.raw_id), "ENTITY_RAW_ID", self.kind)
        if self.scope is not UNKNOWN:
            _require(bool(self.scope), "ENTITY_SCOPE", self.raw_id)
            _require(
                self.scope_source in SCOPE_SOURCES,
                "ENTITY_SCOPE_SOURCE",
                f"{self.raw_id}: {self.scope_source}",
            )
        else:
            _require(
                self.scope_source is UNKNOWN,
                "ENTITY_SCOPE_SOURCE",
                f"{self.raw_id}: scope is unknown but scope_source is set",
            )
        seen: set[str] = set()
        for key in self.keys:
            _require(key.name not in seen, "ENTITY_KEY_DUPLICATE", key.name)
            seen.add(key.name)

    def key(self, name: str) -> str | None:
        for item in self.keys:
            if item.name == name:
                return item.value
        return None


@dataclass(frozen=True)
class Citation:
    """Where the fact is written, with a verbatim excerpt."""

    chunk_id: str
    revision_id: str
    locator_kind: str
    locator_label: str
    excerpt: str
    source_role: str
    page_start: int | None = None
    page_end: int | None = None
    table_block_id: str = ""
    row_number: int | None = None

    def __post_init__(self) -> None:
        for name in ("chunk_id", "revision_id", "locator_label", "excerpt"):
            _require(bool(getattr(self, name)), "CITATION_FIELD", name)
        _require(
            self.locator_kind in LOCATOR_KINDS,
            "CITATION_LOCATOR",
            self.locator_kind,
        )
        _require(self.source_role != "", "CITATION_ROLE", self.chunk_id)
        if self.locator_kind in {"table_row", "table_header", "table_title"}:
            _require(
                bool(self.table_block_id),
                "CITATION_TABLE_BLOCK",
                self.chunk_id,
            )
        if self.locator_kind in {"table_row", "table_header"}:
            _require(
                type(self.row_number) is int,
                "CITATION_ROW_NUMBER",
                self.chunk_id,
            )


@dataclass(frozen=True)
class Condition:
    """A stated condition, with its own position; never inferred."""

    kind: str
    raw: str
    citation: Citation

    def __post_init__(self) -> None:
        _require(bool(self.kind) and self.kind.isascii(), "CONDITION_KIND", self.kind)
        _require(bool(self.raw), "CONDITION_RAW", self.kind)
        _require(
            isinstance(self.citation, Citation), "CONDITION_CITATION", self.kind
        )


@dataclass(frozen=True)
class Fact:
    """One sourced engineering fact."""

    fact_id: str
    layer: str
    fact_type: str
    subject: EntityRef
    attribute: str | _Unknown
    raw_value: str | _Unknown
    value_kind: str
    comparator: str
    revision_id: str
    source_role: str
    evidence_role: str
    citation: Citation
    conditions: tuple[Condition, ...] = ()
    object_ref: EntityRef | _Unknown = UNKNOWN
    number: float | _Unknown = UNKNOWN
    low: float | _Unknown = UNKNOWN
    high: float | _Unknown = UNKNOWN
    unit: str | _Unknown = UNKNOWN
    unknown_fields: tuple[str, ...] = ()
    extra: tuple[tuple[str, str], ...] = ()
    extracted_by: str = ""

    def __post_init__(self) -> None:
        validate_fact(self)

    # -- serialization -------------------------------------------------

    def to_dict(self) -> dict:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "fact_id": self.fact_id,
            "layer": self.layer,
            "fact_type": self.fact_type,
            "subject": entity_to_dict(self.subject),
            "attribute": value_to_json(self.attribute),
            "object": entity_to_dict(self.object_ref),
            "raw_value": value_to_json(self.raw_value),
            "value_kind": self.value_kind,
            "comparator": self.comparator,
            "number": value_to_json(self.number),
            "low": value_to_json(self.low),
            "high": value_to_json(self.high),
            "unit": value_to_json(self.unit),
            "conditions": [condition_to_dict(item) for item in self.conditions],
            "revision_id": self.revision_id,
            "source_role": self.source_role,
            "evidence_role": self.evidence_role,
            "citation": citation_to_dict(self.citation),
            "unknown_fields": list(self.unknown_fields),
            "extra": [list(item) for item in self.extra],
            "extracted_by": self.extracted_by,
        }
        return payload

    @classmethod
    def from_dict(cls, data: Mapping) -> "Fact":
        _require(
            data.get("schema_version") == SCHEMA_VERSION,
            "SCHEMA_VERSION",
            str(data.get("schema_version")),
        )
        return cls(
            fact_id=data["fact_id"],
            layer=data["layer"],
            fact_type=data["fact_type"],
            subject=entity_from_dict(data["subject"]),
            attribute=json_to_value(data.get("attribute")),
            raw_value=json_to_value(data.get("raw_value")),
            value_kind=data["value_kind"],
            comparator=data["comparator"],
            number=json_to_value(data.get("number")),
            low=json_to_value(data.get("low")),
            high=json_to_value(data.get("high")),
            unit=json_to_value(data.get("unit")),
            conditions=tuple(
                condition_from_dict(item) for item in data.get("conditions", ())
            ),
            object_ref=entity_from_dict(data.get("object")),
            revision_id=data["revision_id"],
            source_role=data["source_role"],
            evidence_role=data["evidence_role"],
            citation=citation_from_dict(data["citation"]),
            unknown_fields=tuple(data.get("unknown_fields", ())),
            extra=tuple(tuple(item) for item in data.get("extra", ())),
            extracted_by=data.get("extracted_by", ""),
        )


def validate_fact(fact: Fact) -> None:
    """Raise ``FactError`` unless the record is complete and honest."""

    _require(
        isinstance(fact.fact_id, str)
        and fact.fact_id.startswith("F")
        and len(fact.fact_id) == 17
        and all(ch in "0123456789abcdef" for ch in fact.fact_id[1:]),
        "FACT_ID",
        fact.fact_id,
    )
    _require(fact.layer in LAYERS, "FACT_LAYER", fact.layer)
    _require(
        bool(fact.fact_type) and fact.fact_type.isascii(),
        "FACT_TYPE",
        fact.fact_type,
    )
    _require(isinstance(fact.subject, EntityRef), "FACT_SUBJECT", fact.fact_id)
    _require(
        fact.value_kind in VALUE_KINDS, "VALUE_KIND", fact.value_kind
    )
    _require(
        fact.comparator in COMPARATORS, "COMPARATOR", fact.comparator
    )
    _require(bool(fact.revision_id), "REVISION_ID", fact.fact_id)
    _require(
        fact.evidence_role in EVIDENCE_ROLES,
        "EVIDENCE_ROLE",
        fact.evidence_role,
    )
    _require(isinstance(fact.citation, Citation), "FACT_CITATION", fact.fact_id)
    _require(
        fact.citation.revision_id == fact.revision_id,
        "CITATION_REVISION",
        f"{fact.fact_id}: {fact.citation.revision_id} != {fact.revision_id}",
    )
    _require(
        fact.source_role == fact.citation.source_role,
        "SOURCE_ROLE",
        f"{fact.fact_id}: {fact.source_role} != {fact.citation.source_role}",
    )
    if fact.object_ref is not UNKNOWN:
        _require(
            isinstance(fact.object_ref, EntityRef),
            "FACT_OBJECT",
            fact.fact_id,
        )
    _require(
        fact.fact_type != "relation" or isinstance(fact.object_ref, EntityRef),
        "RELATION_OBJECT",
        fact.fact_id,
    )
    _require(
        fact.fact_type != "attribute" or fact.object_ref is UNKNOWN,
        "ATTRIBUTE_OBJECT",
        fact.fact_id,
    )
    for name in ("number", "low", "high"):
        value = getattr(fact, name)
        _require(
            value is UNKNOWN or type(value) is float,
            "FACT_NUMBER",
            f"{fact.fact_id}: {name}={value!r}",
        )
    for name in ("attribute", "raw_value", "unit"):
        value = getattr(fact, name)
        _require(
            value is UNKNOWN or (isinstance(value, str) and value != ""),
            "FACT_TEXT",
            f"{fact.fact_id}: {name}={value!r}",
        )
    _require(
        isinstance(fact.conditions, tuple),
        "FACT_CONDITIONS",
        fact.fact_id,
    )
    for item in fact.conditions:
        _require(isinstance(item, Condition), "FACT_CONDITION", fact.fact_id)
    _require(
        fact.raw_value is not UNKNOWN,
        "RAW_VALUE_REQUIRED",
        f"{fact.fact_id}: raw_value must be present (use a relation fact)",
    )
    _require(
        isinstance(fact.extracted_by, str) and bool(fact.extracted_by),
        "EXTRACTED_BY",
        fact.fact_id,
    )
    _require(isinstance(fact.extra, tuple), "FACT_EXTRA", fact.fact_id)
    for item in fact.extra:
        _require(
            isinstance(item, tuple)
            and len(item) == 2
            and isinstance(item[0], str)
            and bool(item[0])
            and isinstance(item[1], str)
            and bool(item[1]),
            "FACT_EXTRA",
            f"{fact.fact_id}: extra entries must be (name, value) string pairs",
        )

    unknown = set(fact.unknown_fields)
    _require(
        fact.unknown_fields == tuple(sorted(unknown)),
        "UNKNOWN_FIELDS_ORDER",
        fact.fact_id,
    )
    _require(
        all(name in FACETS for name in unknown),
        "UNKNOWN_FIELD_NAME",
        f"{fact.fact_id}: {sorted(unknown)}",
    )
    observed = {
        name
        for name in FACETS
        if is_unknown(getattr(fact, "citation" if name == "citation" else name))
    }
    if not fact.conditions:
        observed.add("conditions")
    _require(
        unknown == observed,
        "UNKNOWN_FIELDS_MISMATCH",
        f"{fact.fact_id}: declared {sorted(unknown)} but observed {sorted(observed)}",
    )
    if fact.value_kind in {"number", "quantity"}:
        _require(
            fact.number is not UNKNOWN,
            "NUMERIC_VALUE",
            f"{fact.fact_id}: {fact.value_kind} needs a parsed number",
        )
    if fact.value_kind == "range":
        _require(
            fact.low is not UNKNOWN and fact.high is not UNKNOWN,
            "NUMERIC_VALUE",
            f"{fact.fact_id}: range needs low and high",
        )


def is_unknown(value: object) -> bool:
    if value is UNKNOWN:
        return True
    if isinstance(value, str):
        return value == ""
    return value is None


def value_to_json(value: object) -> object:
    if value is UNKNOWN:
        return None
    return value


def json_to_value(value: object) -> object:
    if value is None:
        return UNKNOWN
    return value


def entity_to_dict(entity: EntityRef | _Unknown) -> dict | None:
    if entity is UNKNOWN:
        return None
    return {
        "kind": entity.kind,
        "raw_id": entity.raw_id,
        "scope": value_to_json(entity.scope),
        "scope_source": value_to_json(entity.scope_source),
        "keys": [
            {"name": key.name, "value": key.value, "basis": key.basis}
            for key in entity.keys
        ],
    }


def entity_from_dict(data: Mapping | None) -> EntityRef | _Unknown:
    if not data:
        return UNKNOWN
    return EntityRef(
        kind=data["kind"],
        raw_id=data["raw_id"],
        scope=json_to_value(data.get("scope")),
        scope_source=json_to_value(data.get("scope_source")),
        keys=tuple(
            IdentityKey(name=key["name"], value=key["value"], basis=key["basis"])
            for key in data.get("keys", ())
        ),
    )


def citation_to_dict(citation: Citation) -> dict:
    return {
        "chunk_id": citation.chunk_id,
        "revision_id": citation.revision_id,
        "locator_kind": citation.locator_kind,
        "locator_label": citation.locator_label,
        "excerpt": citation.excerpt,
        "source_role": citation.source_role,
        "page_start": citation.page_start,
        "page_end": citation.page_end,
        "table_block_id": citation.table_block_id,
        "row_number": citation.row_number,
    }


def citation_from_dict(data: Mapping) -> Citation:
    return Citation(
        chunk_id=data["chunk_id"],
        revision_id=data["revision_id"],
        locator_kind=data["locator_kind"],
        locator_label=data["locator_label"],
        excerpt=data["excerpt"],
        source_role=data["source_role"],
        page_start=data.get("page_start"),
        page_end=data.get("page_end"),
        table_block_id=data.get("table_block_id", ""),
        row_number=data.get("row_number"),
    )


def condition_to_dict(condition: Condition) -> dict:
    return {
        "kind": condition.kind,
        "raw": condition.raw,
        "citation": citation_to_dict(condition.citation),
    }


def condition_from_dict(data: Mapping) -> Condition:
    return Condition(
        kind=data["kind"],
        raw=data["raw"],
        citation=citation_from_dict(data["citation"]),
    )


def make_fact_id(
    *,
    layer: str,
    fact_type: str,
    subject_raw: str,
    attribute: str,
    object_raw: str,
    raw_value: str,
    revision_id: str,
    locator_label: str,
    excerpt: str,
) -> str:
    """Deterministic identity; identical evidence yields the same fact id."""

    payload = "\x1f".join(
        (
            layer,
            fact_type,
            subject_raw,
            attribute,
            object_raw,
            raw_value,
            revision_id,
            locator_label,
            excerpt,
        )
    )
    return "F" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def excerpt_segments(excerpt: str) -> tuple[str, ...]:
    """Split an excerpt on ``……`` into the verbatim pieces it claims."""

    return tuple(part.strip() for part in excerpt.split("……") if part.strip())


def excerpt_in_text(excerpt: str, text: str) -> bool:
    """True when every claimed fragment appears verbatim in ``text``."""

    segments = excerpt_segments(excerpt)
    if not segments:
        return False
    position = 0
    for part in segments:
        found = text.find(part, position)
        if found < 0:
            return False
        position = found + len(part)
    return True


@dataclass
class FactSet:
    """Facts keyed by id, with JSONL round-trip and citation checks."""

    facts: dict[str, Fact] = field(default_factory=dict)

    def add(self, fact: Fact) -> None:
        _require(fact.fact_id not in self.facts, "DUPLICATE_FACT", fact.fact_id)
        self.facts[fact.fact_id] = fact

    def extend(self, facts: Iterable[Fact]) -> None:
        for fact in facts:
            self.add(fact)

    def sorted(self) -> list[Fact]:
        return [self.facts[key] for key in sorted(self.facts)]

    def by_layer(self, layer: str) -> list[Fact]:
        return [fact for fact in self.sorted() if fact.layer == layer]

    def write_jsonl(self, path) -> int:
        from pathlib import Path

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            for fact in self.sorted():
                handle.write(
                    json.dumps(fact.to_dict(), ensure_ascii=False) + "\n"
                )
        return len(self.facts)

    @classmethod
    def read_jsonl(cls, path) -> "FactSet":
        from pathlib import Path

        result = cls()
        with Path(path).open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    result.add(Fact.from_dict(json.loads(line)))
        return result


def check_citations(
    facts: Iterable[Fact], chunk_text: Mapping[str, str]
) -> list[str]:
    """Return human-readable problems; empty means every excerpt is verbatim."""

    problems: list[str] = []
    for fact in facts:
        for label, citation in (
            (("fact", fact.citation),)
            + tuple(
                (f"condition-{index}", condition.citation)
                for index, condition in enumerate(fact.conditions, 1)
            )
        ):
            text = chunk_text.get(citation.chunk_id)
            if text is None:
                problems.append(
                    f"{fact.fact_id}/{label}: unknown chunk {citation.chunk_id}"
                )
                continue
            if not excerpt_in_text(citation.excerpt, text):
                problems.append(
                    f"{fact.fact_id}/{label}: excerpt not verbatim in "
                    f"{citation.chunk_id}"
                )
                continue
            if label == "fact":
                for name in ("raw_value", "unit"):
                    value = getattr(fact, name)
                    if (
                        value is not UNKNOWN
                        and isinstance(value, str)
                        and value not in citation.excerpt
                    ):
                        problems.append(
                            f"{fact.fact_id}: {name} not in its excerpt"
                        )
    return problems
