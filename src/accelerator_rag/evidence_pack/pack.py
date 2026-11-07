"""Budgeted evidence-pack selection and the equal-budget parent baseline.

The selection object is a pack of locatable atoms that covers the question's
required relations, not the top five parents.  A generic number or role atom is
not a witness unless it is about the asked object or comes from a candidate
chunk ranked for this question.  Conflicts are kept in pairs, never one-sided.
"""

from __future__ import annotations

from dataclasses import replace
import re

from .budget import pack_tokens
from .index import (
    CorpusIndex,
    atom_entity_match,
    merge_port_intervals,
    port_intervals,
)
from .relations import atom_satisfies, relevant_atom_ids
from .schema import (
    Atom,
    BudgetPolicy,
    Coverage,
    Needs,
    Pack,
    RELATION_NAMES,
    normalize_key,
)

_REQUIRED_WEIGHT = 100.0
_OPTIONAL_WEIGHT = 10.0
_ENTITY_WEIGHT = 25.0
_DIVERSITY_WEIGHT = 6.0
_DUPLICATE_PENALTY = 3.0
_TERM_WEIGHT = 3.0
_EXTRA_WITNESS_WEIGHT = 30.0
_ENUMERATION_WEIGHT = 12.0
_TARGET_ROLES = {"requirement", "design", "test_result", "acceptance", "test_scope"}
_STRUCTURAL_RELATIONS = {
    "requirement",
    "design",
    "test_result",
    "test_scope",
    "acceptance",
    "enumeration",
    "version_left",
    "version_right",
}


def _strong_relevance(atoms, needs: Needs, query: str, index: CorpusIndex) -> set[str]:
    return relevant_atom_ids(atoms, needs, query, index)


def _structural_relevance(atoms, candidate_chunks: set[str]) -> set[str]:
    return {
        atom.atom_id for atom in atoms if atom.chunk_id in candidate_chunks
    }


def _satisfaction_map(
    atoms: tuple[Atom, ...],
    needs: Needs,
    index: CorpusIndex,
    relevant: set[str],
    structural: set[str],
) -> dict[str, set[str]]:
    core_entities = {
        item.normalized: item.kind
        for item in needs.entities
        if item.kind in {"cabinet", "device"} and item.normalized
    }
    mapping: dict[str, set[str]] = {}
    for relation in needs.relations:
        allowed = (
            relevant | structural
            if relation.name in _STRUCTURAL_RELATIONS
            else relevant
        )
        mapping[relation.name] = {
            atom.atom_id
            for atom in atoms
            if atom_satisfies(
                atom,
                relation,
                index,
                needs,
                allowed,
                core_entities,
            )
        }
    return mapping


def _entity_map(atoms, needs) -> dict[str, set[str]]:
    entities = {
        item.normalized: item.kind
        for item in needs.entities
        if item.kind in {"device", "cabinet", "cable", "pv", "port", "number"}
    }
    mapping: dict[str, set[str]] = {}
    for atom in atoms:
        mapping[atom.atom_id] = {
            entity
            for entity, kind in entities.items()
            if atom_entity_match(atom, entity, kind)
        }
    return mapping


def _atom_port_intervals(atom) -> list[tuple[int, int]]:
    intervals: list[tuple[int, int]] = []
    for cell in atom.excerpt.strip().strip("|").split("|"):
        intervals.extend(port_intervals(cell))
    return intervals


def _intersects(left, right) -> bool:
    return any(
        not (a_high < b_low or b_high < a_low)
        for a_low, a_high in left
        for b_low, b_high in right
    )


def _port_union_covers(atoms, port_entities: tuple[str, ...]) -> bool:
    merged = merge_port_intervals(
        interval
        for atom in atoms
        for interval in _atom_port_intervals(atom)
    )
    if not merged:
        return False
    for port in port_entities:
        probes = port_intervals(port)
        if not probes:
            return False
        for low, high in probes:
            if not any(s_low <= low and high <= s_high for s_low, s_high in merged):
                return False
    return True


def coverage_for(
    selected_atoms: tuple[Atom, ...],
    needs: Needs,
    index: CorpusIndex,
    enumeration: dict,
    relevant: set[str],
    structural: set[str],
) -> tuple[Coverage, ...]:
    selected = {atom.atom_id for atom in selected_atoms}
    mapping = _satisfaction_map(
        selected_atoms, needs, index, relevant, structural
    )
    covered: list[Coverage] = []
    for relation in needs.relations:
        if relation.name == "enumeration":
            satisfied, missing = _enumeration_status(selected, enumeration)
            atom_ids = tuple(
                atom_id
                for summary in enumeration.values()
                for atom_id in summary.get("atom_ids", ())
                if atom_id in selected
            )
            covered.append(
                Coverage(
                    name=relation.name,
                    required=relation.required,
                    satisfied=satisfied,
                    atom_ids=atom_ids,
                    missing=missing,
                    reason=relation.reason,
                )
            )
            continue
        witnesses = [
            atom
            for atom in selected_atoms
            if atom.atom_id in mapping.get(relation.name, set())
        ]
        port_entities = tuple(
            item.normalized
            for item in needs.entities
            if item.kind == "port" and item.normalized
        )
        if relation.name in {"value", "scope"} and port_entities:
            probes = [
                interval
                for port in port_entities
                for interval in port_intervals(port)
            ]
            witnesses = [
                atom
                for atom in witnesses
                if _intersects(_atom_port_intervals(atom), probes)
            ]
            satisfied = bool(witnesses) and _port_union_covers(
                witnesses, port_entities
            )
        else:
            satisfied = bool(witnesses)
        atom_ids = tuple(atom.atom_id for atom in witnesses)
        missing = "" if satisfied else f"未找到满足「{relation.name}」关系的证据原子"
        covered.append(
            Coverage(
                name=relation.name,
                required=relation.required,
                satisfied=satisfied,
                atom_ids=atom_ids,
                missing=missing,
                reason=relation.reason,
            )
        )
    return tuple(covered)


def _enumeration_status(
    selected: set[str], enumeration: dict
) -> tuple[bool, str]:
    if not enumeration:
        return False, "未定位到需要完整枚举的目标表"
    incomplete = [
        block
        for block, summary in enumeration.items()
        if not summary.get("complete", False)
    ]
    if incomplete:
        return False, "目标表存在未选入的行：" + ", ".join(sorted(incomplete))
    missing = [
        block
        for block, summary in enumeration.items()
        if not set(summary.get("atom_ids", ())) <= selected
    ]
    if missing:
        return False, "目标表的行未全部进入证据包：" + ", ".join(sorted(missing))
    return True, ""


def _diversity(
    selected_atoms: tuple[Atom, ...],
    mapping: dict[str, set[str]],
    required: set[str],
) -> int:
    revisions: dict[str, set[str]] = {name: set() for name in required}
    for atom in selected_atoms:
        for name in required:
            if atom.atom_id in mapping.get(name, set()):
                revisions[name].add(atom.revision_id)
    return sum(max(0, len(values) - 1) for values in revisions.values())


def _objective(
    selected_atoms: tuple[Atom, ...],
    coverage: tuple[Coverage, ...],
    budget: int,
    *,
    entity_hits: int = 0,
    diversity: int = 0,
) -> float:
    required = sum(1 for item in coverage if item.required and item.satisfied)
    optional = sum(1 for item in coverage if not item.required and item.satisfied)
    texts = [
        normalize_key(re.sub(r"\s+", " ", atom.excerpt)) for atom in selected_atoms
    ]
    duplicates = len(texts) - len(set(texts))
    tokens = pack_tokens(selected_atoms)
    relevance = sum(min(2.0, max(0.0, atom.score)) for atom in selected_atoms)
    return (
        _REQUIRED_WEIGHT * required
        + _OPTIONAL_WEIGHT * optional
        + _ENTITY_WEIGHT * entity_hits
        + _DIVERSITY_WEIGHT * diversity
        - _DUPLICATE_PENALTY * duplicates
        - tokens / max(1, budget)
        - 0.05 * len(selected_atoms)
        + 0.01 * relevance
    )


def _preselect_conflicts(
    atoms: tuple[Atom, ...], conflicts, budget: int
) -> tuple[list[Atom], list[str], set[str], tuple]:
    """Keep both sides of every conflict, or neither; never one side.

    Conflicts sharing an atom are re-evaluated until stable.  A conflict whose
    sides cannot fit is marked ``resolution="unresolved"``, not left as
    ``preserved`` with a free-text note.
    """
    by_id = {atom.atom_id: atom for atom in atoms}
    selected: dict[str, Atom] = {}
    blocked: set[str] = set()
    unresolved: list[str] = []
    status: dict[str, str] = {}
    reasons: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        for conflict in conflicts:
            sides = [
                by_id[atom_id]
                for atom_id in conflict.atom_ids
                if atom_id in by_id
            ]
            side_ids = {atom.atom_id for atom in sides}
            if len(sides) < 2:
                status[conflict.conflict_id] = "unresolved"
                reasons[conflict.conflict_id] = (
                    "冲突一方不在候选原子中，未据此下结论"
                )
                blocked.update(side_ids)
                changed = True
                continue
            if status.get(conflict.conflict_id) == "unresolved":
                if side_ids - blocked:
                    blocked.update(side_ids)
                    changed = True
                continue
            if side_ids & blocked:
                status[conflict.conflict_id] = "unresolved"
                reasons[conflict.conflict_id] = (
                    "冲突一方被另一冲突排除，未据此下结论"
                )
                for atom_id in side_ids:
                    selected.pop(atom_id, None)
                blocked.update(side_ids)
                changed = True
                continue
            trial = list(selected.values()) + sides
            if pack_tokens(trial) <= budget:
                for atom in sides:
                    selected[atom.atom_id] = atom
                status[conflict.conflict_id] = "kept"
            else:
                status[conflict.conflict_id] = "unresolved"
                reasons[conflict.conflict_id] = (
                    "预算不足以同时保留冲突双方，未据此下结论"
                )
                for atom_id in side_ids:
                    selected.pop(atom_id, None)
                blocked.update(side_ids)
                changed = True
    selected = {
        atom_id: atom for atom_id, atom in selected.items() if atom_id not in blocked
    }
    conflicts_out = []
    for conflict in conflicts:
        if status.get(conflict.conflict_id) == "unresolved":
            reason = reasons.get(conflict.conflict_id, conflict.reason)
            unresolved.append(f"{conflict.conflict_id}: {reason}")
            conflicts_out.append(
                replace(
                    conflict,
                    resolution="unresolved",
                    reason=reason,
                )
            )
        else:
            conflicts_out.append(conflict)
    return (
        list(selected.values()),
        unresolved,
        blocked,
        tuple(conflicts_out),
    )


def _targets(needs: Needs) -> dict[str, int]:
    targets: dict[str, int] = {}
    enumeration = needs.relation("enumeration") is not None
    for relation in needs.relations:
        name = relation.name
        if name in {"value", "counterpart"}:
            targets[name] = 3 if enumeration else 2
        elif name == "boundary":
            targets[name] = 2
        elif name in {"requirement", "design", "test_result", "acceptance"}:
            targets[name] = 2
        elif name == "test_scope":
            targets[name] = 1
        else:
            targets[name] = 1
    return targets


def _term_map(atoms, query: str) -> dict[str, set[str]]:
    from .index import query_terms

    terms = {term for term in query_terms(query) if len(term) >= 3}
    mapping: dict[str, set[str]] = {}
    for atom in atoms:
        text = normalize_key(atom.excerpt)
        mapping[atom.atom_id] = {term for term in terms if term in text}
    return mapping


def select_pack(
    atoms: tuple[Atom, ...],
    needs: Needs,
    index: CorpusIndex,
    policy: BudgetPolicy,
    *,
    query: str,
    candidate_order: tuple[str, ...],
    conflicts=(),
    enumeration: dict,
    alignment: tuple[dict, ...] = (),
    max_passes: int = 2,
    fill_scorer=None,
) -> Pack:
    """Greedy relation/object coverage under the token budget, then swaps."""

    budget = policy.tokens
    candidate_chunks = set(candidate_order)
    relevant = _strong_relevance(atoms, needs, query, index)
    structural = _structural_relevance(atoms, candidate_chunks)
    mapping = _satisfaction_map(atoms, needs, index, relevant, structural)
    entity_map = _entity_map(atoms, needs)
    required_entities = {
        item.normalized
        for item in needs.entities
        if item.kind in {"device", "cabinet", "cable", "pv", "port", "number"}
    }
    required = {item.name for item in needs.relations if item.required}
    optional = {item.name for item in needs.relations if not item.required}
    preselected, unresolved, blocked, conflicts = _preselect_conflicts(
        atoms, conflicts, budget
    )
    selected: dict[str, Atom] = {
        atom.atom_id: atom for atom in preselected if atom.atom_id not in blocked
    }
    aligned_atoms: list[Atom] = []
    if alignment:
        by_id = {atom.atom_id: atom for atom in atoms}
        for pair in sorted(
            alignment, key=lambda item: (-item.get("similarity", 0.0), item["left_atom_id"])
        ):
            pair_atoms = [
                by_id[atom_id]
                for atom_id in (pair["left_atom_id"], pair["right_atom_id"])
                if atom_id in by_id
            ]
            if len(pair_atoms) < 2:
                continue
            if pack_tokens(list(selected.values()) + pair_atoms) > budget:
                continue
            for atom in pair_atoms:
                if atom.atom_id not in selected:
                    selected[atom.atom_id] = atom
                    aligned_atoms.append(atom)
            if len(aligned_atoms) >= 4:
                break

    def covered_names() -> set[str]:
        return {
            name
            for name in RELATION_NAMES
            if any(
                atom_id in mapping.get(name, set()) for atom_id in selected
            )
        }

    def covered_entities() -> set[str]:
        result: set[str] = set()
        for atom_id in selected:
            result |= entity_map.get(atom_id, set())
        return result

    targets = _targets(needs)
    term_map = _term_map(atoms, query)
    enum_atoms = {
        atom_id
        for summary in enumeration.values()
        for atom_id in summary.get("atom_ids", ())
    }

    while True:
        chosen = None
        chosen_key = None
        names_covered = covered_names()
        entities_covered = covered_entities()
        terms_covered = {
            term for atom_id in selected for term in term_map.get(atom_id, set())
        }
        witness_cache = {
            name: {
                selected[atom_id].chunk_id
                for atom_id in selected
                if atom_id in mapping.get(name, set())
            }
            for name in RELATION_NAMES
        }
        for atom in atoms:
            if atom.atom_id in selected or atom.atom_id in blocked:
                continue
            if pack_tokens(list(selected.values()) + [atom]) > budget:
                continue
            atom_names = {
                name
                for name in RELATION_NAMES
                if atom.atom_id in mapping.get(name, set())
            }
            new_required = atom_names & required - names_covered
            new_optional = atom_names & optional - names_covered
            extra_required = {
                name
                for name in atom_names & required & names_covered
                if len(witness_cache[name]) < targets.get(name, 1)
                and atom.chunk_id not in witness_cache[name]
            }
            new_entities = entity_map.get(atom.atom_id, set()) - entities_covered
            new_terms = term_map.get(atom.atom_id, set()) - terms_covered
            gain = (
                _REQUIRED_WEIGHT * len(new_required)
                + _EXTRA_WITNESS_WEIGHT * len(extra_required)
                + _OPTIONAL_WEIGHT * len(new_optional)
                + _ENTITY_WEIGHT * len(new_entities)
                + _TERM_WEIGHT * min(4, len(new_terms))
            )
            if atom.atom_id in enum_atoms and atom.atom_id not in selected:
                gain += _ENUMERATION_WEIGHT
            if gain <= 0:
                continue
            ratio = gain / max(1, atom.tokens)
            key = (-ratio, -gain, -atom.score, atom.atom_id)
            if chosen_key is None or key < chosen_key:
                chosen, chosen_key = atom, key
        if chosen is None:
            break
        selected[chosen.atom_id] = chosen

    # Diversity: a second revision for a required relation adds evidence but
    # not a new relation; add the cheapest such atom while budget remains.
    while True:
        names_covered = covered_names()
        best = None
        best_key = None
        revisions = {
            name: {
                atom.revision_id
                for atom in selected.values()
                if atom.atom_id in mapping.get(name, set())
            }
            for name in required
        }
        for atom in atoms:
            if atom.atom_id in selected or atom.atom_id in blocked:
                continue
            if pack_tokens(list(selected.values()) + [atom]) > budget:
                continue
            gain = 0.0
            for name in required & names_covered:
                if atom.atom_id not in mapping.get(name, set()):
                    continue
                if atom.revision_id in revisions[name]:
                    continue
                if len(revisions[name]) < 3:
                    gain += _DIVERSITY_WEIGHT
            if gain <= 0:
                continue
            key = (-gain / max(1, atom.tokens), -atom.score, atom.atom_id)
            if best_key is None or key < best_key:
                best, best_key = atom, key
        if best is None:
            break
        selected[best.atom_id] = best

    # Fill the remaining budget with atoms from the ranked candidate chunks.
    # Rows and sentences from many parents fit where five full parent blocks do
    # not; this is the §4.2 selection-object change, not extra context.
    fill_target = int(budget * 0.9)
    conflict_side = {
        conflict.conflict_id: set(conflict.atom_ids) for conflict in conflicts
    }
    rank = {chunk_id: position for position, chunk_id in enumerate(candidate_order)}
    fill_pool = [
        atom
        for atom in atoms
        if atom.atom_id not in selected
        and atom.atom_id not in blocked
        and atom.chunk_id in candidate_chunks
        and (
            not atom.conflict_group
            or conflict_side.get(atom.conflict_group, set()) <= set(selected)
        )
    ]
    if fill_scorer is None:
        fill_candidates = sorted(
            fill_pool,
            key=lambda atom: (
                rank.get(atom.chunk_id, 999),
                -atom.score,
                atom.atom_id,
            ),
        )
    else:
        selected_texts = {
            normalize_key(re.sub(r"\s+", " ", atom.excerpt))
            for atom in selected.values()
        }
        scores = {
            atom.atom_id: fill_scorer(
                atom, rank.get(atom.chunk_id, 999), selected_texts
            )
            for atom in fill_pool
        }
        fill_candidates = sorted(
            fill_pool,
            key=lambda atom: (
                -scores[atom.atom_id],
                rank.get(atom.chunk_id, 999),
                atom.atom_id,
            ),
        )
    for atom in fill_candidates:
        if pack_tokens(list(selected.values())) >= fill_target:
            break
        if pack_tokens(list(selected.values()) + [atom]) > budget:
            continue
        selected[atom.atom_id] = atom

    # Local improvement: replace a low-value atom when required coverage or
    # object coverage increases without losing a covered relation.
    for _ in range(max_passes):
        improved = False
        current = tuple(selected.values())
        coverage_before = coverage_for(
            current, needs, index, enumeration, relevant, structural
        )
        score_before = _objective(
            current,
            coverage_before,
            budget,
            entity_hits=len(covered_entities()),
            diversity=_diversity(current, mapping, required),
        )
        protected = {
            atom_id
            for conflict in conflicts
            for atom_id in conflict.atom_ids
        } | {atom.atom_id for atom in aligned_atoms}
        for atom_id in sorted(selected):
            if atom_id in protected:
                continue
            base = {key: value for key, value in selected.items() if key != atom_id}
            for candidate in atoms:
                if candidate.atom_id in base or candidate.atom_id in blocked:
                    continue
                trial = {**base, candidate.atom_id: candidate}
                if pack_tokens(list(trial.values())) > budget:
                    continue
                coverage = coverage_for(
                    tuple(trial.values()), needs, index, enumeration, relevant, structural
                )
                entity_hits = len(
                    {
                        entity
                        for trial_id in trial
                        for entity in entity_map.get(trial_id, set())
                    }
                )
                score = _objective(
                    tuple(trial.values()),
                    coverage,
                    budget,
                    entity_hits=entity_hits,
                    diversity=_diversity(tuple(trial.values()), mapping, required),
                )
                if score > score_before + 1e-9:
                    selected = trial
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break

    final_atoms = tuple(sorted(selected.values(), key=Atom.sort_key))
    coverage = coverage_for(
        final_atoms, needs, index, enumeration, relevant, structural
    )

    conflicted = {
        atom.atom_id
        for conflict in conflicts
        if conflict.resolution == "unresolved"
        or any(atom_id not in selected for atom_id in conflict.atom_ids)
        for atom_id in conflict.atom_ids
        if atom_id in selected
    }
    adjusted: list[Coverage] = []
    for item in coverage:
        if item.satisfied and set(item.atom_ids) & conflicted:
            adjusted.append(
                replace(
                    item,
                    satisfied=False,
                    missing="冲突证据未能成对保留，不能据此下确定结论",
                )
            )
        else:
            adjusted.append(item)
    coverage = tuple(adjusted)

    parent_ids = sorted(
        {atom.chunk_id for atom in final_atoms if atom.chunk_id},
        key=lambda chunk_id: (
            -max(atom.score for atom in final_atoms if atom.chunk_id == chunk_id),
            chunk_id,
        ),
    )
    full_text_ids = set(parent_ids[: policy.max_parents])
    parents = tuple(
        {
            "chunk_id": chunk_id,
            "tokens": index.chunk_tokens(chunk_id),
            "source_role": index.chunks[chunk_id].evidence_role,
            "revision_id": index.revision_of(chunk_id),
            "position_label": index.chunks[chunk_id].position_label,
            "full_text": chunk_id in full_text_ids,
        }
        for chunk_id in parent_ids
    )
    tokens = pack_tokens(final_atoms)
    selection = {
        "policy": "relation_pack_v1",
        "budget": policy.describe(),
        "preselected_conflict_atoms": len(preselected),
        "preselected_alignment_atoms": len(aligned_atoms),
        "blocked_atoms": len(blocked),
        "passes": max_passes,
        "objective": round(
            _objective(
                final_atoms,
                coverage,
                budget,
                entity_hits=len(
                    {
                        entity
                        for atom in final_atoms
                        for entity in entity_map.get(atom.atom_id, set())
                    }
                ),
                diversity=_diversity(final_atoms, mapping, required),
            ),
            6,
        ),
        "atom_count": len(final_atoms),
        "referenced_parents": len(parent_ids),
        "full_text_parents": len(full_text_ids),
        "entity_count": len(
            {
                entity
                for atom in final_atoms
                for entity in entity_map.get(atom.atom_id, set())
            }
        ),
        "required_entities": len(required_entities),
    }
    return Pack(
        atoms=final_atoms,
        parents=parents,
        tokens=tokens,
        budget=budget,
        coverage=coverage,
        conflicts=tuple(conflicts),
        unresolved=tuple(unresolved),
        selection=selection,
    )


def select_parent_baseline(
    atoms: tuple[Atom, ...],
    candidates,
    needs: Needs,
    index: CorpusIndex,
    policy: BudgetPolicy,
    *,
    query: str,
    conflicts=(),
    enumeration: dict,
) -> Pack:
    """Current production shape: the first five parent blocks, trimmed to fit.

    The baseline receives the same candidate list as the pack and does not
    adjudicate conflicts; it is a parent-selection reference, not a claimed
    answer.  Its full parent texts are the counted object.
    """

    chosen: list[tuple[str, int]] = []
    seen: set[str] = set()
    for candidate in candidates[:5]:
        if candidate.chunk_id in seen or candidate.chunk_id not in index.chunks:
            continue
        chosen.append((candidate.chunk_id, index.chunk_tokens(candidate.chunk_id)))
        seen.add(candidate.chunk_id)
    while chosen and sum(cost for _, cost in chosen) > policy.tokens:
        chosen.pop()
    selected_ids = {chunk_id for chunk_id, _ in chosen}
    selected_atoms = tuple(
        atom for atom in atoms if atom.chunk_id in selected_ids
    )
    relevant = _strong_relevance(atoms, needs, query, index)
    structural = _structural_relevance(atoms, selected_ids)
    coverage = coverage_for(
        selected_atoms, needs, index, enumeration, relevant, structural
    )
    tokens = sum(cost for _, cost in chosen)
    parents = tuple(
        {
            "chunk_id": chunk_id,
            "tokens": cost,
            "source_role": index.chunks[chunk_id].evidence_role,
            "revision_id": index.revision_of(chunk_id),
            "position_label": index.chunks[chunk_id].position_label,
            "full_text": True,
        }
        for chunk_id, cost in chosen
    )
    return Pack(
        atoms=selected_atoms,
        parents=parents,
        tokens=min(tokens, policy.tokens),
        budget=policy.tokens,
        coverage=coverage,
        conflicts=(),
        unresolved=(),
        selection={
            "policy": "parent_top5_baseline",
            "parent_count": len(chosen),
            "budget": policy.describe(),
            "conflicts": "baseline does not adjudicate conflicts",
        },
    )
