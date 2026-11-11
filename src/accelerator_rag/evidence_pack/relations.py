"""Relation completion: units, conditions, counterparts, roles, versions, sets.

Completion never invents evidence.  It pulls in atoms the question's relations
require (a condition's own citation, the other end of a connection, the test
result for the same object, both revision sides) and detects conflicts without
deleting either side.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
import re
import unicodedata

from accelerator_rag.facts.schema import Fact, UNKNOWN

from .index import CorpusIndex, atom_entity_match, entity_terms, query_terms
from .schema import (
    Atom,
    Conflict,
    Needs,
    RelationNeed,
    atom_id_for,
    estimate_tokens,
    make_conflict_id,
    normalize_key,
)

ROLE_MATCH = {
    "requirement": {"design_target", "test_plan"},
    "design": {"design_target"},
    "test_result": {"test_result"},
    "acceptance": {"acceptance_conclusion"},
}
_SCOPE = re.compile(r"CN[-:]?\d+|柜|工作表|表题")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_UNIT = re.compile(r"(?:%|μs|µs|us|ns|ms|\bs\b|V|A|Hz|kHz|MHz|GHz|℃|°C|mm|cm|kg|kW|W|dB)")
_CONDITION_WORD = re.compile(r"适用|条件|模式|范围|端点|量程|工况")
_ASCII_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.:+/-]{2,}")
_DOC_SUBJECT = re.compile(r"报告|大纲|总结|评审|申请书|验收书|说明书|操作手册")


@dataclass(frozen=True)
class CompletionResult:
    atoms: tuple[Atom, ...]
    conflicts: tuple[Conflict, ...]
    alignment: tuple[dict, ...]
    enumeration: dict
    trace: dict

    def to_dict(self) -> dict:
        return {
            "atoms": [atom.to_dict() for atom in self.atoms],
            "conflicts": [item.to_dict() for item in self.conflicts],
            "alignment": list(self.alignment),
            "enumeration": self.enumeration,
            "trace": self.trace,
        }


def _facts(index: CorpusIndex, atom: Atom) -> tuple[Fact, ...]:
    return tuple(
        index.facts.facts[fid]
        for fid in atom.fact_ids
        if fid in index.facts.facts
    )


def _row_cells(excerpt: str) -> tuple[str, ...]:
    if "|" not in excerpt:
        return ()
    return tuple(
        cell.strip() for cell in excerpt.strip().strip("|").split("|")
    )


def _has_unit(text: str) -> bool:
    return bool(_UNIT.search(text))


def relevant_atom_ids(atoms, needs: Needs, query: str, index: CorpusIndex) -> set[str]:
    """Atoms that mention the question's objects or enough of its terms.

    A generic number/unit/role atom is not a witness unless it is about the
    asked object; otherwise the pack would cover relation names, not answers.
    """

    entities = {
        item.normalized: item.kind for item in needs.entities if item.normalized
    }
    terms = {term for term in query_terms(query) if len(term) >= 3}
    selected: set[str] = set()
    for atom in atoms:
        parts = [atom.excerpt, atom.locator_label]
        for fact in _facts(index, atom):
            parts.append(str(fact.subject.raw_id))
            parts.extend(key.value for key in fact.subject.keys)
            if not isinstance(fact.object_ref, type(UNKNOWN)):
                parts.append(str(fact.object_ref.raw_id))
            if isinstance(fact.attribute, str):
                parts.append(fact.attribute)
        text = normalize_key(" ".join(parts))
        matched = any(
            atom_entity_match(atom, entity, kind)
            for entity, kind in entities.items()
        )
        if not matched:
            overlap = {term for term in terms if term in text}
            matched = (
                len(overlap) >= 2
                or any(len(term) >= 4 and term.isascii() for term in overlap)
                or (bool(overlap) and len(query.strip()) <= 8)
            )
        if matched:
            selected.add(atom.atom_id)
    return selected


def atom_satisfies(
    atom: Atom,
    relation: RelationNeed,
    index: CorpusIndex,
    needs: Needs,
    relevant: set[str] | None = None,
    core_entities: dict[str, str] | None = None,
) -> bool:
    """Whether one atom is a witness for one relation (coverage semantics)."""

    if (
        relevant is not None
        and relation.name not in {"provenance", "version_left", "version_right"}
        and atom.atom_id not in relevant
    ):
        return False
    if relation.name in {"value", "counterpart", "scope"}:
        cabinets = [
            entity
            for entity, kind in core_entities.items()
            if kind == "cabinet"
        ] if core_entities else []
        devices = [
            entity
            for entity, kind in core_entities.items()
            if kind == "device"
        ] if core_entities else []
        if cabinets and not any(
            atom_entity_match(atom, entity, "cabinet") for entity in cabinets
        ):
            return False
        if devices and not any(
            atom_entity_match(atom, entity, "device") for entity in devices
        ):
            return False
    elif relation.name in {"unit", "condition", "boundary"} and core_entities:
        if not any(
            atom_entity_match(atom, entity, kind)
            for entity, kind in core_entities.items()
        ):
            return False
    facts = _facts(index, atom)
    role_matches = {fact.source_role for fact in facts} | {atom.source_role}
    cells = _row_cells(atom.excerpt)
    name = relation.name
    if name == "provenance":
        return bool(atom.chunk_id and atom.excerpt)
    if name == "value":
        return (
            any(not isinstance(fact.raw_value, type(UNKNOWN)) for fact in facts)
            or (atom.locator_kind == "table_row" and len([c for c in cells if c]) >= 2)
            or bool(_NUMBER.search(atom.excerpt))
        )
    if name == "unit":
        return any(
            not isinstance(fact.unit, type(UNKNOWN)) for fact in facts
        ) or _has_unit(atom.excerpt)
    if name == "condition":
        return (
            atom.evidence_role == "condition"
            or any(fact.conditions for fact in facts)
            or bool(_CONDITION_WORD.search(atom.excerpt))
        )
    if name == "counterpart":
        return (
            any(
                fact.fact_type == "relation"
                and not isinstance(fact.object_ref, type(UNKNOWN))
                for fact in facts
            )
            or len(_ASCII_TOKEN.findall(atom.excerpt)) >= 2
            or len([cell for cell in cells if cell]) >= 4
        )
    if name == "scope":
        return (
            any(
                not isinstance(fact.subject.scope, type(UNKNOWN))
                or (
                    not isinstance(fact.object_ref, type(UNKNOWN))
                    and not isinstance(fact.object_ref.scope, type(UNKNOWN))
                )
                for fact in facts
            )
            or bool(_SCOPE.search(atom.excerpt))
        )
    if name in {"version_left", "version_right"}:
        if not needs.version_pair:
            return False
        target = (
            needs.version_pair[0]
            if name == "version_left"
            else needs.version_pair[1]
        )
        return atom.revision_id == target
    if name in ROLE_MATCH:
        return bool(role_matches & ROLE_MATCH[name])
    if name == "test_scope":
        return any(
            fact.fact_type == "test_scope"
            or (
                isinstance(fact.attribute, str)
                and any(
                    word in fact.attribute
                    for word in ("测试条件", "测量范围", "测试范围", "量程", "端点")
                )
            )
            for fact in facts
        ) or bool(_CONDITION_WORD.search(atom.excerpt))
    if name == "boundary":
        return any(
            fact.comparator in {"lt", "le", "gt", "ge", "range"} for fact in facts
        ) or bool(
            re.search(r"小于|大于|不超过|不低于|范围|边界|→|≤|≥|<|>", atom.excerpt)
        ) or bool(
            re.search(r"\d+\s*[-~～至—]\s*\d+", atom.excerpt)
        )
    if name == "enumeration":
        return False  # decided over the whole selected pack
    if name == "external_observation":
        return atom.locator_kind == "external_observation"
    return False


def witnesses(
    atoms,
    relation: RelationNeed,
    index: CorpusIndex,
    needs: Needs,
    relevant: set[str] | None = None,
) -> tuple[Atom, ...]:
    return tuple(
        atom
        for atom in atoms
        if atom_satisfies(atom, relation, index, needs, relevant)
    )


def _condition_atom(index: CorpusIndex, fact: Fact, condition) -> Atom:
    citation = condition.citation
    excerpt = citation.excerpt
    label = citation.locator_label
    return Atom(
        atom_id=atom_id_for(
            chunk_id=citation.chunk_id,
            locator_kind=citation.locator_kind,
            locator_label=label,
            excerpt=excerpt,
            row_number=citation.row_number,
            table_block_id=citation.table_block_id,
            evidence_role="condition",
        ),
        chunk_id=citation.chunk_id,
        revision_id=citation.revision_id,
        locator_kind=citation.locator_kind,
        locator_label=label,
        excerpt=excerpt,
        source_role=fact.source_role,
        evidence_role="condition",
        route="graph",
        score=0.9,
        tokens=estimate_tokens(excerpt),
        row_number=citation.row_number,
        table_block_id=citation.table_block_id,
        fact_ids=(),
    )


def _role_facts(
    index: CorpusIndex,
    needs: Needs,
    revisions: set[str],
    name: str,
    text_terms: set[str],
    *,
    limit: int = 6,
) -> tuple[Fact, ...]:
    allowed = ROLE_MATCH.get(name)
    entities = entity_terms(needs.entities)
    terms = text_terms
    scored: list[tuple[float, Fact]] = []
    for revision_id in sorted(revisions):
        for fact_id in index.facts_by_revision.get(revision_id, ()):
            fact = index.facts.facts[fact_id]
            if allowed is not None and fact.source_role not in allowed:
                continue
            if name == "test_scope" and not (
                fact.fact_type == "test_scope"
                or (
                    isinstance(fact.attribute, str)
                    and any(
                        word in fact.attribute
                        for word in ("测试条件", "测量范围", "测试范围", "量程", "端点")
                    )
                )
            ):
                continue
            subject = normalize_key(fact.subject.raw_id)
            keys = {normalize_key(key.value) for key in fact.subject.keys}
            score = 0.0
            if subject in entities:
                score += 4.0
            if keys & entities:
                score += 3.0
            attribute = fact.attribute if isinstance(fact.attribute, str) else ""
            subject_text = normalize_key(fact.subject.raw_id)
            excerpt = normalize_key(fact.citation.excerpt)
            score += sum(0.5 for term in terms if term and term in subject_text)
            score += sum(0.6 for term in terms if term and term in normalize_key(attribute))
            score += sum(0.2 for term in terms if term and term in excerpt)
            if score <= 0:
                continue
            scored.append((score, fact))
    scored.sort(key=lambda item: (-item[0], item[1].fact_id))
    return tuple(fact for _, fact in scored[:limit])


def _shingles(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKC", text).casefold()
    words = set(re.findall(r"[a-z0-9_]+", folded))
    for run in re.findall(r"[一-鿿]+", folded):
        for index in range(0, len(run) - 1):
            words.add(run[index : index + 2])
    return words


def _similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _align_versions(
    index: CorpusIndex, needs: Needs, query: str
) -> tuple[list[Atom], list[dict]]:
    if not needs.version_pair:
        return [], []
    left_id, right_id = needs.version_pair
    terms = query_terms(query)
    pools: dict[str, list[Atom]] = {}
    for side, revision_id in (("left", left_id), ("right", right_id)):
        pool = [
            atom for atom in index.all_paragraphs(revision_id) if len(atom.excerpt) >= 8
        ]
        pool.sort(
            key=lambda atom: (
                -sum(1 for term in terms if term and term in atom.excerpt.casefold()),
                atom.atom_id,
            )
        )
        pools[side] = pool[:24]
    added: list[Atom] = []
    alignment: list[dict] = []
    used_right: set[str] = set()
    for left_atom in pools["left"]:
        left_shingles = _shingles(left_atom.excerpt)
        best = None
        best_score = 0.0
        for right_atom in pools["right"]:
            if right_atom.atom_id in used_right:
                continue
            score = _similarity(left_shingles, _shingles(right_atom.excerpt))
            if score > best_score:
                best, best_score = right_atom, score
        if best is not None and best_score >= 0.18:
            used_right.add(best.atom_id)
            added.extend([left_atom, best])
            alignment.append(
                {
                    "left_atom_id": left_atom.atom_id,
                    "right_atom_id": best.atom_id,
                    "left_revision_id": left_id,
                    "right_revision_id": right_id,
                    "similarity": round(best_score, 4),
                }
            )
    for atom in pools["left"][:8] + pools["right"][:8]:
        added.append(atom)
    unique: dict[str, Atom] = {}
    for atom in added:
        unique.setdefault(atom.atom_id, atom)
    return list(unique.values()), alignment


def _enumerate_rows(
    index: CorpusIndex,
    atoms,
    needs: Needs,
    revisions: set[str],
    *,
    limit: int = 160,
) -> tuple[list[Atom], dict]:
    if needs.relation("enumeration") is None:
        return [], {}
    counts: dict[str, int] = defaultdict(int)
    for atom in atoms:
        if atom.locator_kind == "table_row" and atom.table_block_id:
            counts[atom.table_block_id] += 1
    blocks = sorted(counts, key=lambda block: (-counts[block], block))[:2]
    added: list[Atom] = []
    summary: dict[str, dict] = {}
    for block in blocks:
        rows = [
            row
            for row in index.rows
            if row.table_block_id == block and row.revision_id in revisions
        ]
        rows.sort(key=lambda row: (row.chunk_id, row.row_number))
        selected = rows[:limit]
        atom_ids = []
        for row in selected:
            atom = row.to_atom(score=0.6, route="row_exact")
            added.append(atom)
            atom_ids.append(atom.atom_id)
        summary[block] = {
            "expected_rows": len(rows),
            "selected_rows": len(selected),
            "atom_ids": atom_ids,
            "complete": len(selected) == len(rows),
        }
    return added, summary


def _row_context(index: CorpusIndex, fact: Fact) -> tuple[str, ...]:
    for row in index.rows_of(fact.citation.chunk_id):
        if (
            row.row_number == fact.citation.row_number
            and row.table_block_id == fact.citation.table_block_id
        ):
            excluded = {
                normalize_key(str(fact.raw_value)),
                normalize_key(str(fact.attribute))
                if isinstance(fact.attribute, str)
                else "",
                normalize_key(str(fact.unit))
                if not isinstance(fact.unit, type(UNKNOWN))
                else "",
            }
            cells = [
                normalize_key(value)
                for _, value in row.cells
                if value.strip() and normalize_key(value) not in excluded
            ]
            return tuple(cells[:2])
    if fact.citation.locator_kind in {
        "paragraph",
        "section",
        "pdf_page",
        "slide",
        "figure_caption",
    }:
        return (fact.citation.locator_label,)
    return ()


def _excerpt_variants(items) -> bool:
    """True when all facts are extraction variants of the same sentence."""

    texts = [normalize_key(fact.citation.excerpt) for _, fact in items]
    if len(texts) < 2:
        return False
    for left in range(len(texts)):
        for right in range(left + 1, len(texts)):
            first, second = texts[left], texts[right]
            if first in second or second in first:
                continue
            first_set = set(first)
            second_set = set(second)
            overlap = len(first_set & second_set) / max(
                1, len(first_set | second_set)
            )
            if overlap < 0.8:
                return False
    return True


def _conflicts(
    index: CorpusIndex, atoms, needs: Needs
) -> tuple[tuple[Conflict, ...], tuple[Atom, ...]]:
    groups: dict[tuple, list[tuple[Atom, Fact]]] = defaultdict(list)
    for atom in atoms:
        for fact in _facts(index, atom):
            # Connectivity facts carry the port range as their value; the same
            # device has one row per range, so a value difference there is a
            # different row, not a contradiction.  Cross-table identity is
            # checked by exact_join instead.
            if fact.layer != "parameter" or fact.value_kind == "unknown":
                continue
            conditions = tuple(
                normalize_key(condition.raw) for condition in fact.conditions
            )
            subject = normalize_key(fact.subject.raw_id)
            key: tuple = (
                subject,
                normalize_key(fact.attribute if isinstance(fact.attribute, str) else ""),
                conditions,
            )
            if not key[1]:
                continue
            if _DOC_SUBJECT.search(subject):
                key = key + (_row_context(index, fact),)
            groups[key].append((atom, fact))
    conflicts: list[Conflict] = []
    marked: dict[str, str] = {}
    for key, items in sorted(groups.items()):
        subject, attribute, conditions = key[:3]
        context = key[3:]
        values = {
            (
                normalize_key(str(fact.raw_value)),
                normalize_key(str(fact.unit)) if not isinstance(fact.unit, type(UNKNOWN)) else "",
            )
            for _, fact in items
        }
        if len(values) <= 1:
            continue
        roles = {fact.source_role for _, fact in items}
        revisions = {fact.revision_id for _, fact in items}
        tables = {
            (fact.revision_id, fact.citation.table_block_id)
            for _, fact in items
        }
        labels = {
            (fact.revision_id, fact.citation.locator_label)
            for _, fact in items
        }
        if len(roles) == 1 and len(revisions) == 1 and len(tables) == 1:
            # One table, one role, several rows: the values belong to different
            # rows/items.  The row key is not a condition, so this is not a
            # value contradiction (documented limitation).
            continue
        if (
            len(roles) == 1
            and len(revisions) == 1
            and len(labels) > 1
            and all(
                fact.citation.locator_kind
                in {"paragraph", "section", "pdf_page", "slide", "figure_caption"}
                for _, fact in items
            )
        ):
            # Different paragraphs/figures in one document and role usually
            # describe different items (test figures, ranges, platforms).
            continue
        if _excerpt_variants(items):
            continue
        if len(roles) > 1:
            kind = "role"
            resolution = "preserved" if needs.comparison else "affects_target"
            reason = "同一对象/属性在多角色证据中取值不同；设计、测试、验收分别保留"
        elif len(revisions) > 1 and needs.version_pair:
            kind, resolution = "version", "preserved"
            reason = "不同修订侧的同名属性；按版本并列保留"
        elif needs.comparison:
            kind, resolution = "value", "preserved"
            reason = "对照题并列保存不同版本/来源的取值"
        else:
            kind, resolution = "value", "affects_target"
            reason = "同一对象/属性/条件出现不同取值，可能影响目标主张"
        atom_ids = tuple(sorted({atom.atom_id for atom, _ in items}))
        if len(atom_ids) < 2:
            # Both values sit on one atom; there is no separable side to keep.
            continue
        conflict_id = make_conflict_id(
            kind,
            subject,
            attribute
            + "||"
            + repr(conditions)
            + ("||" + repr(context) if context else ""),
        )
        conflicts.append(
            Conflict(
                conflict_id=conflict_id,
                kind=kind,
                subject=subject,
                attribute=attribute,
                atom_ids=atom_ids,
                resolution=resolution,
                reason=reason,
            )
        )
        for atom_id in atom_ids:
            marked[atom_id] = conflict_id
    marked_atoms = [
        replace(atom, conflict_group=marked[atom.atom_id])
        if atom.atom_id in marked
        else atom
        for atom in atoms
    ]
    return tuple(conflicts), tuple(marked_atoms)


def complete(
    index: CorpusIndex,
    needs: Needs,
    query: str,
    atoms,
    *,
    family_ids: set[str],
    revisions: set[str],
) -> CompletionResult:
    pool: list[Atom] = list(atoms)
    trace: dict[str, int] = defaultdict(int)
    trace["initial_atoms"] = len(pool)

    # 1. conditions travel with their fact.
    known = {(atom.chunk_id, atom.excerpt, atom.evidence_role) for atom in pool}
    for atom in list(pool):
        for fact in _facts(index, atom):
            for condition in fact.conditions:
                key = (
                    condition.citation.chunk_id,
                    condition.citation.excerpt,
                    "condition",
                )
                if key in known:
                    continue
                pool.append(_condition_atom(index, fact, condition))
                known.add(key)
                trace["condition_atoms"] += 1

    # 2. counterpart identities through relation facts.
    seen_ids = {atom.atom_id for atom in pool}
    for atom in list(pool):
        for fact in _facts(index, atom):
            if fact.fact_type != "relation" or isinstance(fact.object_ref, type(UNKNOWN)):
                continue
            keys = {normalize_key(fact.object_ref.raw_id)} | {
                normalize_key(key.value) for key in fact.object_ref.keys
            }
            for key in sorted(keys):
                for fact_id in index.facts_by_subject.get(key, ())[:4]:
                    other = index.facts.facts[fact_id]
                    if other.fact_id == fact.fact_id or other.revision_id not in revisions:
                        continue
                    new_atom = index.fact_atom(other, score=0.85, route="graph")
                    if new_atom.atom_id in seen_ids:
                        continue
                    seen_ids.add(new_atom.atom_id)
                    pool.append(new_atom)
                    trace["counterpart_atoms"] += 1

    # 3. role matrix: fill missing roles for the same object.
    text_terms = query_terms(query)
    for name in ("requirement", "design", "test_result", "acceptance", "test_scope"):
        relation = needs.relation(name)
        if relation is None or not relation.required:
            continue
        if any(atom_satisfies(atom, relation, index, needs) for atom in pool):
            continue
        for fact in _role_facts(index, needs, revisions, name, text_terms):
            new_atom = index.fact_atom(fact, score=0.8, route="graph")
            if new_atom.atom_id in seen_ids:
                continue
            seen_ids.add(new_atom.atom_id)
            pool.append(new_atom)
            trace[f"role_{name}_atoms"] += 1

    # 4. version sides align by content, never by position alone.
    aligned, alignment = _align_versions(index, needs, query)
    for atom in aligned:
        if atom.atom_id in seen_ids:
            continue
        seen_ids.add(atom.atom_id)
        pool.append(atom)
        trace["version_atoms"] += 1

    # 5. complete enumerations from the matched tables.
    enumerated, enumeration = _enumerate_rows(index, pool, needs, revisions)
    for atom in enumerated:
        if atom.atom_id in seen_ids:
            continue
        seen_ids.add(atom.atom_id)
        pool.append(atom)
        trace["enumeration_atoms"] += 1

    conflicts, marked = _conflicts(index, pool, needs)
    trace["conflicts"] = len(conflicts)
    trace["final_atoms"] = len(marked)
    return CompletionResult(
        atoms=marked,
        conflicts=conflicts,
        alignment=tuple(alignment),
        enumeration=enumeration,
        trace=dict(trace),
    )
