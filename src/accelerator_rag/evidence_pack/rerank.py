"""Rule and learned evidence-pack rerankers (W3).

Reranking changes which non-witness atoms fill the remaining budget and their
order; it never removes a covered relation or one side of a conflict.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .index import CorpusIndex, query_terms
from .schema import Atom, Needs, entity_in_text, normalize_key

FEATURES = (
    "entity_match",
    "term_match",
    "candidate_rank",
    "role_match",
    "row_header_match",
    "unit_or_condition",
    "duplicate_penalty",
    "token_cost",
    "conflict_penalty",
)


def _feature_vector(
    atom: Atom,
    needs: Needs,
    index: CorpusIndex,
    query: str,
    *,
    candidate_rank: int,
    selected_texts: set[str],
) -> dict[str, float]:
    entities = {
        item.normalized: item.kind for item in needs.entities if item.normalized
    }
    text = normalize_key(" ".join([atom.excerpt, atom.locator_label]))
    term_hits = sum(
        1
        for term in query_terms(query)
        if len(term) >= 3 and term in text
    )
    wanted_roles = {
        item.name for item in needs.relations if item.required
    }
    role_match = 0.0
    if atom.source_role:
        role_match = 1.0 if any(
            role in atom.source_role or atom.source_role in role
            for role in wanted_roles
        ) else -1.0
    header_match = 0.0
    if atom.locator_kind == "table_row":
        headers = index.chunk_headers.get(atom.chunk_id, ())
        header_match = sum(
            1.0 for term in query_terms(query) if len(term) >= 2 and any(term in header for header in headers)
        )
    normalized = normalize_key(atom.excerpt)
    return {
        "entity_match": float(
            any(
                entity_in_text(entity, text, kind)
                for entity, kind in entities.items()
            )
        ),
        "term_match": float(min(term_hits, 6)),
        "candidate_rank": 1.0 / (1.0 + candidate_rank),
        "role_match": role_match,
        "row_header_match": min(header_match, 4.0),
        "unit_or_condition": float(
            atom.evidence_role in {"unit", "condition"} or bool(atom.fact_ids)
        ),
        "duplicate_penalty": 1.0 if normalized in selected_texts else 0.0,
        "token_cost": atom.tokens / 100.0,
        "conflict_penalty": 1.0 if atom.conflict_group else 0.0,
    }


RULE_WEIGHTS = {
    "entity_match": 2.0,
    "term_match": 1.0,
    "candidate_rank": 1.5,
    "role_match": 1.0,
    "row_header_match": 0.5,
    "unit_or_condition": 0.5,
    "duplicate_penalty": -2.0,
    "token_cost": -1.0,
    "conflict_penalty": -5.0,
}


@dataclass(frozen=True)
class ScoredAtom:
    atom_id: str
    score: float
    breakdown: dict[str, float]


class RuleReranker:
    name = "rule"
    weights = dict(RULE_WEIGHTS)
    bias = 0.0

    def score(
        self,
        atom: Atom,
        needs: Needs,
        index: CorpusIndex,
        query: str,
        *,
        candidate_rank: int,
        selected_texts: set[str],
    ) -> ScoredAtom:
        vector = _feature_vector(
            atom,
            needs,
            index,
            query,
            candidate_rank=candidate_rank,
            selected_texts=selected_texts,
        )
        breakdown = {
            name: round(vector[name] * self.weights[name], 6)
            for name in FEATURES
        }
        return ScoredAtom(
            atom_id=atom.atom_id,
            score=round(sum(breakdown.values()) + self.bias, 6),
            breakdown=breakdown,
        )


class LearnedReranker:
    name = "learned"

    def __init__(
        self,
        weights: dict[str, float],
        metadata: dict | None = None,
        bias: float = 0.0,
    ):
        self.weights = {
            name: float(weights.get(name, 0.0)) for name in FEATURES
        }
        self.metadata = dict(metadata or {})
        self.bias = float(bias)

    @classmethod
    def load(cls, path: str | Path) -> "LearnedReranker":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schema_version") != "phase3-linear-reranker-v1":
            raise ValueError("unsupported reranker weight file")
        return cls(
            payload["weights"],
            payload.get("metadata", {}),
            float(payload.get("bias", 0.0)),
        )

    def score(
        self,
        atom: Atom,
        needs: Needs,
        index: CorpusIndex,
        query: str,
        *,
        candidate_rank: int,
        selected_texts: set[str],
    ) -> ScoredAtom:
        vector = _feature_vector(
            atom,
            needs,
            index,
            query,
            candidate_rank=candidate_rank,
            selected_texts=selected_texts,
        )
        breakdown = {
            name: round(vector[name] * self.weights[name], 6)
            for name in FEATURES
        }
        return ScoredAtom(
            atom_id=atom.atom_id,
            score=round(sum(breakdown.values()) + self.bias, 6),
            breakdown=breakdown,
        )


def scorer_for(name: str, learned_path: str | Path | None = None):
    if name in {"none", ""}:
        return None
    if name == "rule":
        return RuleReranker()
    if name == "learned":
        if learned_path is None:
            raise ValueError(
                "learned reranker needs a weights file; run "
                "scripts/research/train_pack_reranker.py first"
            )
        return LearnedReranker.load(learned_path)
    raise ValueError(f"unknown reranker: {name}")
