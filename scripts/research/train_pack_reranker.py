"""Train and cross-family-evaluate the phase-3 linear pack reranker.

Training labels come from dev questions only: an atom is positive when it is
inside the gold minimal evidence and its text overlaps the gold excerpt; hard
negatives are non-gold atoms that still match the question's object or terms.
Validation is whole-family held out (dev families train, val families test).
"""

from __future__ import annotations

import argparse
import collections
from dataclasses import replace
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from accelerator_rag.evidence_pack.fingerprints import (  # noqa: E402
    facts_digest,
    questions_digest,
)
from accelerator_rag.evidence_pack.index import (  # noqa: E402
    load_index,
    resolve_version_pair,
)
from accelerator_rag.evidence_pack.needs import parse_needs  # noqa: E402
from accelerator_rag.evidence_pack.recall import recall, allowed_revisions  # noqa: E402
from accelerator_rag.evidence_pack.relations import complete  # noqa: E402
from accelerator_rag.evidence_pack.rerank import (  # noqa: E402
    FEATURES,
    RULE_WEIGHTS,
    _feature_vector,
)

DEFAULT_FACTS = ROOT / "data" / "facts" / "facts.jsonl"
QUESTIONS = ROOT / "data" / "evaluation" / "research-benchmark-300-v1"
DEFAULT_OUT = ROOT / "data" / "evidence-pack" / "reranker.json"


def _questions(split: str):
    return json.loads(
        (QUESTIONS / split / "questions.json").read_text(encoding="utf-8")
    )["items"]


def _label(atom, gold) -> int:
    excerpts = [
        item["excerpt"]
        for item in gold.get("evidence_minimal", ())
        if item["chunk_id"] == atom.chunk_id
    ]
    if not excerpts:
        return 0
    text = atom.excerpt.strip()
    for excerpt in excerpts:
        if text in excerpt or excerpt in text:
            return 1
    return 0


def _near_miss_atoms(atom):
    """Synthetic near misses: adjacent ports, wrong cabinet, role substitution."""

    variants = []
    port = re.search(r"(\d+)\s*-\s*(\d+)", atom.excerpt)
    if port and int(port.group(1)) < int(port.group(2)):
        swapped = (
            atom.excerpt[: port.start()]
            + f"{port.group(2)}-{port.group(1)}"
            + atom.excerpt[port.end() :]
        )
        variants.append(replace(atom, excerpt=swapped))
    cabinet = re.search(r"(?:[A-Z0-9]+[-:])*CN[-:]?\d+", atom.excerpt)
    if cabinet and not cabinet.group(0).startswith("EXT-"):
        wrong = atom.excerpt[: cabinet.start()] + "EXT-" + atom.excerpt[cabinet.start() :]
        variants.append(replace(atom, excerpt=wrong))
    clauses = re.split(r"(?<=[，,；;])", atom.excerpt)
    kept = [clause for clause in clauses if not re.search(r"条件|适用|模式", clause)]
    if len(kept) != len(clauses) and "".join(kept).strip():
        variants.append(replace(atom, excerpt="".join(kept)))
    if atom.source_role == "test_result":
        variants.append(replace(atom, source_role="design_target"))
    return variants[:3]


def collect(
    index, questions, *, max_questions: int | None = None
) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    rows, labels, meta = [], [], []
    used = 0
    for question in questions:
        if question["gold"]["verdict_class"] != "deterministic":
            continue
        needs = parse_needs(question)
        pair = resolve_version_pair(
            question["query"],
            family_ids=tuple(question["family_ids"]),
            index=index,
            explicit=needs.version_pair,
        )
        if pair:
            needs = replace(needs, version_pair=pair, revision_ids=pair)
        family_ids = set(question["family_ids"])
        recalled = recall(index, needs, question["query"], family_ids=family_ids)
        completion = complete(
            index,
            needs,
            question["query"],
            recalled.atoms,
            family_ids=family_ids,
            revisions=allowed_revisions(index, needs, family_ids),
        )
        rank = {candidate.chunk_id: position for position, candidate in enumerate(recalled.candidates)}
        for atom in completion.atoms:
            label = _label(atom, question["gold"])
            if label is None:
                continue
            vector = _feature_vector(
                atom,
                needs,
                index,
                question["query"],
                candidate_rank=rank.get(atom.chunk_id, 99),
                selected_texts=set(),
            )
            rows.append([vector[name] for name in FEATURES])
            labels.append(label)
            meta.append(
                {
                    "question_id": question["base_id"],
                    "family_ids": question["family_ids"],
                }
            )
            if label == 1:
                for variant in _near_miss_atoms(atom):
                    variant_vector = _feature_vector(
                        variant,
                        needs,
                        index,
                        question["query"],
                        candidate_rank=rank.get(variant.chunk_id, 99),
                        selected_texts=set(),
                    )
                    rows.append(
                        [variant_vector[name] for name in FEATURES]
                    )
                    labels.append(0)
                    meta.append(
                        {
                            "question_id": question["base_id"],
                            "family_ids": question["family_ids"],
                        }
                    )
        used += 1
        if max_questions is not None and used >= max_questions:
            break
    return (
        np.asarray(rows, dtype=np.float64),
        np.asarray(labels, dtype=np.float64),
        meta,
    )


def _train(x, y, *, iterations=800, lr=0.08, l2=0.01):
    weights = np.zeros(x.shape[1], dtype=np.float64)
    bias = 0.0
    positives = y.sum()
    negatives = len(y) - positives
    if positives == 0 or negatives == 0:
        raise SystemExit("training needs both positive and negative atoms")
    weights_per_class = {1.0: negatives / positives, 0.0: 1.0}
    sample_weights = np.asarray([weights_per_class[value] for value in y])
    sample_weights /= sample_weights.mean()
    for _ in range(iterations):
        logits = x @ weights + bias
        predictions = 1.0 / (1.0 + np.exp(-np.clip(logits, -50, 50)))
        error = (predictions - y) * sample_weights
        gradient = x.T @ error / len(y) + l2 * weights
        bias_gradient = error.mean()
        weights -= lr * gradient
        bias -= lr * bias_gradient
    return weights, float(bias)


def _auc(scores, labels) -> float | None:
    labels = np.asarray(labels)
    positives = labels.sum()
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None
    order = np.argsort(scores)
    ranks = np.empty(len(scores))
    ranks[order] = np.arange(1, len(scores) + 1)
    return float(
        (ranks[labels == 1].sum() - positives * (positives + 1) / 2)
        / (positives * negatives)
    )


def evaluate(index, questions, weights, bias=None) -> dict:
    per_question = []
    for question in questions:
        if question["gold"]["verdict_class"] != "deterministic":
            continue
        needs = parse_needs(question)
        pair = resolve_version_pair(
            question["query"],
            family_ids=tuple(question["family_ids"]),
            index=index,
            explicit=needs.version_pair,
        )
        if pair:
            needs = replace(needs, version_pair=pair, revision_ids=pair)
        family_ids = set(question["family_ids"])
        recalled = recall(index, needs, question["query"], family_ids=family_ids)
        completion = complete(
            index,
            needs,
            question["query"],
            recalled.atoms,
            family_ids=family_ids,
            revisions=allowed_revisions(index, needs, family_ids),
        )
        rank = {candidate.chunk_id: position for position, candidate in enumerate(recalled.candidates)}
        atoms, labels, learned, rule = [], [], [], []
        for atom in completion.atoms:
            label = _label(atom, question["gold"])
            if label is None:
                continue
            vector = _feature_vector(
                atom,
                needs,
                index,
                question["query"],
                candidate_rank=rank.get(atom.chunk_id, 99),
                selected_texts=set(),
            )
            atoms.append(atom)
            labels.append(label)
            learned.append(
                float(np.dot(np.asarray([vector[name] for name in FEATURES]), weights))
                + (bias or 0.0)
            )
            rule.append(
                sum(vector[name] * RULE_WEIGHTS[name] for name in FEATURES)
            )
        if not labels:
            continue
        per_question.append(
            {
                "question_id": question["base_id"],
                "family_ids": question["family_ids"],
                "atoms": len(labels),
                "positives": int(sum(labels)),
                "auc_learned": _auc(np.asarray(learned), labels),
                "auc_rule": _auc(np.asarray(rule), labels),
                "precision10_learned": _precision_at(learned, labels, 10),
                "precision10_rule": _precision_at(rule, labels, 10),
            }
        )
    auc_learned = [
        item["auc_learned"] for item in per_question if item["auc_learned"] is not None
    ]
    auc_rule = [
        item["auc_rule"] for item in per_question if item["auc_rule"] is not None
    ]
    by_family = collections.defaultdict(list)
    for item in per_question:
        if item["auc_learned"] is None:
            continue
        for family in item["family_ids"]:
            by_family[family].append(item["auc_learned"])
    return {
        "questions": len(per_question),
        "mean_auc_learned": round(float(np.mean(auc_learned)), 4) if auc_learned else None,
        "mean_auc_rule": round(float(np.mean(auc_rule)), 4) if auc_rule else None,
        "mean_precision10_learned": round(
            float(np.mean([item["precision10_learned"] for item in per_question])), 4
        )
        if per_question
        else None,
        "mean_precision10_rule": round(
            float(np.mean([item["precision10_rule"] for item in per_question])), 4
        )
        if per_question
        else None,
        "by_family": {
            family: round(float(np.mean(values)), 4)
            for family, values in sorted(by_family.items())
        },
        "per_question": per_question,
    }


def _precision_at(scores, labels, k):
    order = np.argsort(-np.asarray(scores))[:k]
    return float(np.asarray(labels)[order].mean())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", default=str(DEFAULT_FACTS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--report", default=str(ROOT / "reports" / "phase3" / "reranker.json"))
    parser.add_argument("--iterations", type=int, default=800)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    facts_path = Path(args.facts)
    dev_index = load_index(splits=("dev",), facts_path=facts_path)
    val_index = load_index(splits=("val",), facts_path=facts_path)
    train_x, train_y, train_meta = collect(
        dev_index, _questions("dev"), max_questions=args.limit
    )
    weights, bias = _train(train_x, train_y, iterations=args.iterations)
    evaluation = evaluate(val_index, _questions("val"), weights, bias)
    train_families = sorted(
        {family for item in train_meta for family in item["family_ids"]}
    )
    val_families = sorted(
        {
            family
            for question in _questions("val")
            for family in question["family_ids"]
        }
    )
    payload = {
        "schema_version": "phase3-linear-reranker-v1",
        "weights": {
            name: round(float(weight), 6)
            for name, weight in zip(FEATURES, weights, strict=True)
        },
        "bias": round(bias, 6),
        "metadata": {
            "train_split": "dev",
            "validation_split": "val",
            "train_families": train_families,
            "validation_families": val_families,
            "train_atoms": int(len(train_y)),
            "train_positives": int(train_y.sum()),
            "validation": {
                key: value
                for key, value in evaluation.items()
                if key != "per_question"
            },
            "rule_weights": RULE_WEIGHTS,
            "facts_sha256": facts_digest(str(facts_path)),
            "dev_questions_sha256": questions_digest("dev"),
            "val_questions_sha256": questions_digest("val"),
            "note": (
                "按文档族整体划分：dev 族训练、val 族验证；标签来自 dev gold "
                "最小证据，硬负例为同对象/同术语但不在 gold 中的原子。"
            ),
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(
            {
                "schema_version": "phase3-reranker-eval-v1",
                "train_families": train_families,
                "validation_families": val_families,
                "train_atoms": int(len(train_y)),
                "train_positives": int(train_y.sum()),
                "weights": payload["weights"],
                "bias": payload["bias"],
                "evaluation": evaluation,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "train_atoms": int(len(train_y)),
                "train_positives": int(train_y.sum()),
                "weights": payload["weights"],
                **{
                    key: evaluation[key]
                    for key in (
                        "questions",
                        "mean_auc_learned",
                        "mean_auc_rule",
                        "mean_precision10_learned",
                        "mean_precision10_rule",
                    )
                },
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
