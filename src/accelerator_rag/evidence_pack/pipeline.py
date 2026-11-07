"""End-to-end question-driven evidence-pack pipeline (phase 3)."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json

from .budget import policy_for
from .index import CorpusIndex, resolve_version_pair
from .needs import parse_needs
from .pack import select_pack, select_parent_baseline
from .recall import allowed_revisions, recall
from .relations import complete
from .rerank import scorer_for
from .schema import Atom, Pack
from .verify import verify

PIPELINE_VERSION = "phase3-pipeline-v1"


def _merge_atoms(*groups) -> tuple[Atom, ...]:
    merged: dict[str, Atom] = {}
    for group in groups:
        for atom in group:
            existing = merged.get(atom.atom_id)
            if existing is None or atom.score > existing.score:
                merged[atom.atom_id] = atom
    return tuple(sorted(merged.values(), key=Atom.sort_key))


def _merge_candidates(*groups):
    merged = {}
    for group in groups:
        for candidate in group:
            existing = merged.get(candidate.chunk_id)
            if existing is None or candidate.score > existing.score:
                merged[candidate.chunk_id] = candidate
    return tuple(
        sorted(merged.values(), key=lambda item: (-item.score, item.chunk_id))
    )


def run_question(
    index: CorpusIndex,
    question: dict,
    *,
    reranker: str = "rule",
    learned_path: str | None = None,
    archiver_atoms: tuple[Atom, ...] = (),
    dense=None,
    command: str = "",
    recompute: dict | None = None,
    include_baseline: bool = False,
    max_passes: int = 2,
) -> dict:
    split = question.get("split", "")
    if split not in {"dev", "val"}:
        raise ValueError(f"phase 3 only evaluates dev/val, got {split!r}")
    needs = parse_needs(question)
    pair = resolve_version_pair(
        question["query"],
        family_ids=tuple(question["family_ids"]),
        index=index,
        explicit=needs.version_pair,
    )
    if pair:
        needs = replace(needs, version_pair=pair, revision_ids=pair)
    policy = policy_for(needs)
    family_ids = set(question["family_ids"])
    revisions = allowed_revisions(index, needs, family_ids)
    scorer = scorer_for(reranker, learned_path)

    def fill_scorer(atom, rank, selected_texts):
        if scorer is None:
            return 0.0
        return scorer.score(
            atom,
            needs,
            index,
            question["query"],
            candidate_rank=rank,
            selected_texts=selected_texts,
        ).score

    rounds = []
    all_atoms: tuple[Atom, ...] = ()
    all_candidates = ()
    completion = None
    pack: Pack | None = None
    focus: tuple[str, ...] = ()
    for round_no in range(1, policy.max_rounds + 1):
        recalled = recall(
            index,
            needs,
            question["query"],
            family_ids=family_ids,
            round_no=round_no,
            focus=focus,
            dense=dense,
            archiver_atoms=archiver_atoms if round_no == 1 else (),
        )
        all_candidates = _merge_candidates(all_candidates, recalled.candidates)
        all_atoms = _merge_atoms(all_atoms, recalled.atoms)
        completion = complete(
            index,
            needs,
            question["query"],
            all_atoms,
            family_ids=family_ids,
            revisions=revisions,
        )
        candidate_order = tuple(
            item.chunk_id for item in all_candidates[:24]
        )
        pack = select_pack(
            completion.atoms,
            needs,
            index,
            policy,
            query=question["query"],
            candidate_order=candidate_order,
            conflicts=completion.conflicts,
            enumeration=completion.enumeration,
            alignment=completion.alignment,
            fill_scorer=fill_scorer if scorer is not None else None,
            max_passes=max_passes,
        )
        rounds.append(
            {
                "round": round_no,
                "recall": recalled.trace,
                "completion": completion.trace,
                "pack": pack.to_dict(),
            }
        )
        missing = [
            item.name
            for item in pack.coverage
            if item.required and not item.satisfied
        ]
        if not missing or round_no == policy.max_rounds:
            break
        focus = tuple(missing)

    assert completion is not None and pack is not None
    verification = verify(
        index,
        pack,
        needs,
        question,
        alignment=completion.alignment,
        enumeration=completion.enumeration,
    )
    baseline = None
    if include_baseline:
        baseline = select_parent_baseline(
            completion.atoms,
            all_candidates[:24],
            needs,
            index,
            policy,
            query=question["query"],
            conflicts=completion.conflicts,
            enumeration=completion.enumeration,
        ).to_dict()
    rerank_trace = {"name": "none", "weights": {}, "atoms": []}
    if scorer is not None:
        rank = {
            chunk_id: position
            for position, chunk_id in enumerate(
                [item.chunk_id for item in all_candidates[:24]]
            )
        }
        scored_atoms = []
        for atom in pack.atoms:
            scored = scorer.score(
                atom,
                needs,
                index,
                question["query"],
                candidate_rank=rank.get(atom.chunk_id, 99),
                selected_texts=set(),
            )
            scored_atoms.append(
                {
                    "atom_id": atom.atom_id,
                    "score": scored.score,
                    "score_breakdown": scored.breakdown,
                }
            )
        rerank_trace = {
            "name": getattr(scorer, "name", reranker),
            "weights": dict(getattr(scorer, "weights", {})),
            "atoms": scored_atoms,
        }
    report = {
        "schema_version": PIPELINE_VERSION,
        "question_id": question["base_id"],
        "split": split,
        "scenario": question.get("scenario", ""),
        "task_type": question.get("task_type", ""),
        "verdict_class": question.get("gold", {}).get("verdict_class", ""),
        "route": needs.route,
        "needs": {
            "entities": [
                {"raw": item.raw, "normalized": item.normalized, "kind": item.kind}
                for item in needs.entities
            ],
            "relations": [
                {
                    "name": item.name,
                    "required": item.required,
                    "reason": item.reason,
                }
                for item in needs.relations
            ],
            "revision_ids": list(needs.revision_ids),
            "version_pair": list(needs.version_pair),
            "reason": needs.reason,
        },
        "budget": policy.describe(),
        "reranker": {
            "name": reranker if scorer is not None else "none",
            "fill_scored": scorer is not None,
        },
        "rounds": rounds,
        "pack": pack.to_dict(),
        "verification": verification.to_dict(),
        "rerank": rerank_trace,
        "baseline": baseline,
        "recompute": {
            "command": command,
            "pipeline_version": PIPELINE_VERSION,
            "question_id": question["base_id"],
            **(recompute or {}),
        },
    }
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True)
    report["recompute"]["report_sha256"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    return report
