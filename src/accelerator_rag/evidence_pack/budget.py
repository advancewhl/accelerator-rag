"""Dynamic token budgets and the deterministic offline token estimate."""

from __future__ import annotations

from .schema import BudgetPolicy, Needs, estimate_tokens

BASE = {
    "exact_record": {"tokens": 1200, "parents": 3, "rounds": 1},
    "document_explanation": {"tokens": 2400, "parents": 5, "rounds": 2},
    "cross_source": {"tokens": 3600, "parents": 8, "rounds": 2},
}
RELATION_SURCHARGE = 150
MAX_TOKENS = 6000


def policy_for(needs: Needs) -> BudgetPolicy:
    base = BASE[needs.route]
    relations = sum(1 for item in needs.relations if item.required)
    tokens = min(
        MAX_TOKENS,
        base["tokens"] + max(0, relations - 3) * RELATION_SURCHARGE,
    )
    return BudgetPolicy(
        route=needs.route,
        base_tokens=base["tokens"],
        max_parents=base["parents"],
        max_rounds=base["rounds"],
        tokens=tokens,
        relation_count=relations,
    )


def count_tokens(text: str) -> int:
    return estimate_tokens(text)


def pack_tokens(atoms, overhead_per_parent: int = 24) -> int:
    """Atoms plus fixed parent metadata; full parent text is never counted."""

    parents = {atom.chunk_id for atom in atoms if atom.chunk_id}
    return sum(atom.tokens for atom in atoms) + overhead_per_parent * len(parents)


def fits(atoms, budget: int) -> bool:
    return pack_tokens(atoms) <= budget
