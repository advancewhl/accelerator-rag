"""Pass-count ablation and exhaustive small-pool optimum for pack selection.

Two modes:

``full``
    Re-run dev/val with ``max_passes`` 0/1/2/3 and report deterministic
    coverage and cost.  ``max_passes=0`` is greedy fill without local swaps.

``exhaustive``
    Take 20 deterministic S1-DEV-L3L4 questions, restrict each candidate pool
    to at most 16 atoms, and enumerate every subset under the same token
    budget.  The optimum is compared with greedy passes 0/1/2/3.  The pool is
    documented: one highest-score witness per required relation, then the
    highest-score remaining atoms.

All outputs are local-only under ``reports/phase3/`` (gitignored).
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.evidence_pack.budget import policy_for  # noqa: E402
from accelerator_rag.evidence_pack.index import (  # noqa: E402
    load_index,
    port_intervals,
    resolve_version_pair,
)
from accelerator_rag.evidence_pack.needs import parse_needs  # noqa: E402
from accelerator_rag.evidence_pack.pack import (  # noqa: E402
    _atom_port_intervals,
    _intersects,
    _port_union_covers,
    _satisfaction_map,
    _strong_relevance,
    _structural_relevance,
    select_pack,
)
from accelerator_rag.evidence_pack.recall import allowed_revisions, recall  # noqa: E402
from accelerator_rag.evidence_pack.relations import complete  # noqa: E402

FACTS = ROOT / "data" / "facts" / "facts.jsonl"
QUESTIONS = ROOT / "data" / "evaluation" / "research-benchmark-300-v1"
OUT = ROOT / "reports" / "phase3"


def _questions(split: str) -> list[dict]:
    return json.loads(
        (QUESTIONS / split / "questions.json").read_text(encoding="utf-8")
    )["items"]


def _gold(report: dict, question: dict) -> dict:
    gold = {item["chunk_id"] for item in question["gold"].get("evidence_minimal", ())}
    pack = {atom["chunk_id"] for atom in report["pack"]["atoms"] if atom.get("chunk_id")}
    supports = [set(item.get("support", ())) for item in question["gold"].get("required_facts", ())]
    return {
        "gold_recall": len(gold & pack) / len(gold) if gold else 1.0,
        "gold_full": gold <= pack,
        "support": (
            sum(1 for support in supports if support & pack) / len(supports)
            if supports else 1.0
        ),
    }


def run_full(*, passes: list[int], out: Path) -> dict:
    from accelerator_rag.evidence_pack.pipeline import run_question

    results = {}
    for split in ("dev", "val"):
        index = load_index(splits=(split,), facts_path=str(FACTS))
        questions = _questions(split)
        for count in passes:
            rows = []
            for question in questions:
                report = run_question(
                    index,
                    question,
                    reranker="none",
                    include_baseline=False,
                    max_passes=count,
                )
                row = {
                    "question_id": report["question_id"],
                    "verdict_class": report["verdict_class"],
                    "status": report["verification"]["status"],
                    "route": report["route"],
                    "tokens": report["pack"]["tokens"],
                    "budget": report["pack"]["budget"],
                    "atoms": len(report["pack"]["atoms"]),
                    "objective": report["pack"]["selection"]["objective"],
                    **_gold(report, question),
                }
                rows.append(row)
            deterministic = [row for row in rows if row["verdict_class"] == "deterministic"]
            results[f"{split}-passes{count}"] = {
                "questions": len(rows),
                "deterministic": len(deterministic),
                "status_counts": dict(sorted(collections.Counter(row["status"] for row in rows).items())),
                "mean_gold_recall": round(
                    sum(row["gold_recall"] for row in deterministic) / len(deterministic), 4
                ),
                "gold_full": sum(row["gold_full"] for row in deterministic),
                "mean_support": round(
                    sum(row["support"] for row in deterministic) / len(deterministic), 4
                ),
                "mean_tokens": round(
                    sum(row["tokens"] for row in rows) / len(rows), 2
                ),
                "mean_atoms": round(sum(row["atoms"] for row in rows) / len(rows), 2),
                "budget_failures": sum(row["tokens"] > row["budget"] for row in rows),
            }
            print(f"full {split} passes={count}: {results[f'{split}-passes{count}']}", flush=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return results


def _pool(atoms, needs, mapping, *, limit: int = 16):
    by_id = {atom.atom_id: atom for atom in atoms}
    selected: list[str] = []

    def add(atom_id):
        if atom_id in by_id and atom_id not in selected and len(selected) < limit:
            selected.append(atom_id)

    for relation in needs.relations:
        if not relation.required:
            continue
        witnesses = sorted(
            mapping.get(relation.name, set()),
            key=lambda atom_id: (-by_id[atom_id].score, atom_id),
        )
        for atom_id in witnesses:
            add(atom_id)
    for atom in sorted(atoms, key=lambda item: (-item.score, item.atom_id)):
        add(atom.atom_id)
    return tuple(by_id[atom_id] for atom_id in selected)


def _coverage_score(mask, pool, needs, mapping, port_entities, rel_masks):
    required = 0
    optional = 0
    for relation in needs.relations:
        bits = mask & rel_masks[relation.name]
        if not bits:
            satisfied = False
        elif relation.name in {"value", "scope"} and port_entities:
            witnesses = [pool[i] for i in range(len(pool)) if bits >> i & 1]
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
            satisfied = bool(witnesses) and _port_union_covers(witnesses, port_entities)
        else:
            satisfied = True
        if relation.required:
            required += bool(satisfied)
        else:
            optional += bool(satisfied)
    return required, optional, 100.0 * required + 10.0 * optional


def _exhaustive(pool, needs, policy, mapping, port_entities):
    n = len(pool)
    tokens = [atom.tokens for atom in pool]
    chunk_bits: dict[str, int] = {}
    for position, atom in enumerate(pool):
        chunk_bits[atom.chunk_id] = chunk_bits.get(atom.chunk_id, 0) | (1 << position)
    rel_masks = {
        relation.name: sum(
            1 << position
            for position, atom in enumerate(pool)
            if atom.atom_id in mapping.get(relation.name, set())
        )
        for relation in needs.relations
    }
    best = None
    best_key = None
    for mask in range(1 << n):
        cost = sum(tokens[i] for i in range(n) if mask >> i & 1)
        cost += 24 * sum(1 for chunk_mask in chunk_bits.values() if mask & chunk_mask)
        if cost > policy.tokens:
            continue
        required, optional, score = _coverage_score(
            mask, pool, needs, mapping, port_entities, rel_masks
        )
        key = (score, -cost, -mask)
        if best_key is None or key > best_key:
            best, best_key = mask, key
    required, optional, score = _coverage_score(
        best, pool, needs, mapping, port_entities, rel_masks
    )
    return {
        "mask": best,
        "atoms": [pool[i].atom_id for i in range(n) if best >> i & 1],
        "required_satisfied": required,
        "optional_satisfied": optional,
        "coverage_score": score,
        "tokens": sum(tokens[i] for i in range(n) if best >> i & 1)
        + 24 * sum(1 for chunk_mask in chunk_bits.values() if best & chunk_mask),
    }


def run_exhaustive(*, limit: int, pool_limit: int, out: Path) -> dict:
    index = load_index(splits=("dev",), facts_path=str(FACTS))
    eligible = []
    for question in _questions("dev"):
        if question["cluster_id"] != "S1-DEV-L3L4":
            continue
        if question["gold"].get("verdict_class") != "deterministic":
            continue
        if parse_needs(question).relation("enumeration") is not None:
            continue
        eligible.append(question)
    questions = eligible[:limit]
    rows = []
    for question in questions:
        needs = parse_needs(question)
        pair = resolve_version_pair(
            question["query"],
            family_ids=tuple(question["family_ids"]),
            index=index,
            explicit=needs.version_pair,
        )
        if pair:
            from dataclasses import replace

            needs = replace(needs, version_pair=pair, revision_ids=pair)
        policy = policy_for(needs)
        family_ids = set(question["family_ids"])
        revisions = allowed_revisions(index, needs, family_ids)
        recalled = recall(
            index,
            needs,
            question["query"],
            family_ids=family_ids,
            round_no=1,
        )
        completion = complete(
            index,
            needs,
            question["query"],
            recalled.atoms,
            family_ids=family_ids,
            revisions=revisions,
        )
        candidate_order = tuple(item.chunk_id for item in recalled.candidates[:24])
        relevant = _strong_relevance(
            completion.atoms, needs, question["query"], index
        )
        structural = _structural_relevance(
            completion.atoms, set(candidate_order)
        )
        full_mapping = _satisfaction_map(
            completion.atoms, needs, index, relevant, structural
        )
        pool = _pool(
            completion.atoms, needs, full_mapping, limit=pool_limit
        )
        pool_relevant = _strong_relevance(
            pool, needs, question["query"], index
        )
        pool_structural = _structural_relevance(pool, set(candidate_order))
        mapping = _satisfaction_map(
            pool, needs, index, pool_relevant, pool_structural
        )
        port_entities = tuple(
            item.normalized
            for item in needs.entities
            if item.kind == "port" and item.normalized
        )
        optimum = _exhaustive(pool, needs, policy, mapping, port_entities)
        greedy = {}
        for passes in (0, 1, 2, 3):
            pack = select_pack(
                pool,
                needs,
                index,
                policy,
                query=question["query"],
                candidate_order=candidate_order,
                conflicts=(),
                enumeration={},
                max_passes=passes,
            )
            required = sum(
                1 for item in pack.coverage if item.required and item.satisfied
            )
            optional = sum(
                1 for item in pack.coverage if not item.required and item.satisfied
            )
            greedy[passes] = {
                "required_satisfied": required,
                "optional_satisfied": optional,
                "coverage_score": 100.0 * required + 10.0 * optional,
                "tokens": pack.tokens,
                "atoms": len(pack.atoms),
                "objective": pack.selection["objective"],
            }
        row = {
            "question_id": question["base_id"],
            "pool": len(pool),
            "budget": policy.tokens,
            "optimum": optimum,
            "greedy": greedy,
        }
        for passes, item in greedy.items():
            denominator = max(1.0, optimum["coverage_score"])
            item["loss_pp"] = round(
                100.0 * (optimum["coverage_score"] - item["coverage_score"]) / denominator,
                3,
            )
        rows.append(row)
        print(
            f"{question['base_id']} pool={len(pool)} opt={optimum['coverage_score']} "
            f"g0={greedy[0]['coverage_score']} g1={greedy[1]['coverage_score']} "
            f"g2={greedy[2]['coverage_score']} g3={greedy[3]['coverage_score']}",
            flush=True,
        )
    summary = {}
    for passes in (0, 1, 2, 3):
        losses = [row["greedy"][passes]["loss_pp"] for row in rows]
        summary[f"passes{passes}"] = {
            "mean_loss_pp": round(sum(losses) / len(losses), 3) if losses else None,
            "max_loss_pp": max(losses) if losses else None,
            "better_than_optimum": sum(
                row["greedy"][passes]["coverage_score"]
                > row["optimum"]["coverage_score"]
                for row in rows
            ),
        }
    payload = {"questions": rows, "summary": summary}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=["full", "exhaustive"])
    parser.add_argument("--passes", nargs="+", type=int, default=[1, 2, 3])
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--pool-limit", type=int, default=16)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    if args.mode == "full":
        out = Path(args.out) if args.out else OUT / "ablation-passes.json"
        run_full(passes=args.passes, out=out)
    else:
        out = Path(args.out) if args.out else OUT / "ablation-exhaustive.json"
        payload = run_exhaustive(
            limit=args.limit, pool_limit=args.pool_limit, out=out
        )
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
