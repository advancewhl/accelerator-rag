"""Run the phase-3 evidence-pack pipeline over one dev/val split, or replay it.

Usage:
  python3 scripts/research/run_evidence_pack.py --split dev --out reports/phase3/dev.json
  python3 scripts/research/run_evidence_pack.py --split dev --reranker rule --out reports/phase3/dev-rule.json
  python3 scripts/research/run_evidence_pack.py --split dev --verify reports/phase3/dev.json
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.evidence_pack.archiver import StaticArchiver, load_export  # noqa: E402
from accelerator_rag.evidence_pack.fingerprints import (  # noqa: E402
    corpus_digest,
    facts_digest,
    questions_digest,
)
from accelerator_rag.evidence_pack.dense import EmbeddingDenseChannel  # noqa: E402
from accelerator_rag.evidence_pack.dense_local import (  # noqa: E402
    CachedPassageDenseChannel,
    FusedDenseChannel,
)
from accelerator_rag.evidence_pack.index import load_index  # noqa: E402
from accelerator_rag.evidence_pack.pipeline import run_question  # noqa: E402

DEFAULT_FACTS = ROOT / "data" / "facts" / "facts.jsonl"
QUESTIONS = ROOT / "data" / "evaluation" / "research-benchmark-300-v1"
SPLITS = ("dev", "val")
RUN_SCHEMA = "phase3-evidence-pack-run-v1"


def _display_path(path: str | Path) -> str:
    target = Path(path)
    try:
        return str(target.resolve().relative_to(ROOT))
    except ValueError:
        return str(target)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _questions(split: str) -> list[dict]:
    if split not in SPLITS:
        raise SystemExit(f"split not allowed in phase 3: {split}")
    payload = json.loads((QUESTIONS / split / "questions.json").read_text(encoding="utf-8"))
    return payload["items"]


def _evaluate(report: dict, question: dict) -> dict:
    gold = {
        item["chunk_id"]
        for item in question["gold"].get("evidence_minimal", ())
    }
    pack_chunks = {
        atom["chunk_id"]
        for atom in report["pack"]["atoms"]
        if atom.get("chunk_id")
    }
    baseline = report.get("baseline") or {}
    baseline_chunks = {
        parent["chunk_id"] for parent in baseline.get("parents", ())
    }
    supports = []
    support_unavailable = 0
    for item in question["gold"].get("required_facts", ()):
        if isinstance(item, dict):
            supports.append(set(item.get("support", ())))
        else:
            # The patched gold carries a few plain statements without a
            # support list.  Keep them out of this metric instead of assuming
            # support; the summary reports how many questions are affected.
            support_unavailable += 1
    support_total = len(supports)
    support_pack = sum(1 for support in supports if support & pack_chunks)
    support_baseline = sum(1 for support in supports if support & baseline_chunks)
    selected = {atom["atom_id"] for atom in report["pack"]["atoms"]}
    conflicts = report["pack"].get("conflicts", ())
    preserved = 0
    for conflict in conflicts:
        sides = set(conflict["atom_ids"])
        if sides <= selected:
            preserved += 1
        elif not (sides & selected) and conflict["resolution"] == "unresolved":
            preserved += 1
    enumeration = next(
        (
            item
            for item in report["pack"]["coverage"]
            if item["name"] == "enumeration" and item["required"]
        ),
        None,
    )
    return {
        "gold_chunks": len(gold),
        "gold_chunk_recall_pack": (
            len(gold & pack_chunks) / len(gold) if gold else 1.0
        ),
        "gold_chunk_recall_baseline": (
            len(gold & baseline_chunks) / len(gold) if gold else 1.0
        ),
        "gold_full_pack": gold <= pack_chunks,
        "gold_full_baseline": gold <= baseline_chunks,
        "required_fact_support_pack": (
            support_pack / support_total if support_total else None
        ),
        "required_fact_support_baseline": (
            support_baseline / support_total if support_total else None
        ),
        "required_fact_support_unavailable": support_unavailable,
        "conflicts": len(conflicts),
        "conflicts_preserved": preserved,
        "enumeration_required": enumeration is not None,
        "enumeration_satisfied": bool(enumeration and enumeration["satisfied"]),
        "budget_ok": report["pack"]["tokens"] <= report["pack"]["budget"],
        "parents": len(report["pack"]["parents"]),
    }


DENSE_DIR = ROOT / "data" / "evidence-pack" / "dense"


def _cached_dense_channel(kind: str, split: str, questions: list[dict]):
    def load(model_key: str):
        path = DENSE_DIR / f"{model_key}.npz"
        if not path.exists():
            raise SystemExit(
                f"missing dense vectors: {path}; run build_dense_vectors.py first"
            )
        data = np.load(path, allow_pickle=False)
        meta = json.loads(str(data["meta"]))
        if not all(meta.get("fingerprint_match", {}).values()):
            raise SystemExit(f"{model_key}: local model fingerprint mismatch")
        query_by_id = {
            str(qid): vector
            for qid, vector in zip(
                data["query_ids"], data["query_vectors"], strict=True
            )
        }
        query_vectors = {
            question["query"]: query_by_id[question["base_id"]]
            for question in questions
            if question["base_id"] in query_by_id
        }
        return CachedPassageDenseChannel(
            name=model_key,
            passage_parents=tuple(str(value) for value in data["parent_chunk_ids"]),
            passage_vectors=data["passage_vectors"],
            query_vectors=query_vectors,
        )

    if kind == "both":
        return FusedDenseChannel((load("e5"), load("qwen3")))
    return load(kind)


def run_split(
    split: str,
    *,
    facts_path: Path,
    reranker: str,
    learned: str | None,
    archiver_path: str | None,
    limit: int | None,
    dense: str = "off",
) -> dict:
    questions = _questions(split)
    if limit is not None:
        questions = questions[:limit]
    index = load_index(
        splits=(split,), facts_path=facts_path, with_parsed=True
    )
    archiver = None
    archiver_sha = ""
    if archiver_path:
        export = load_export(archiver_path)
        archiver = StaticArchiver(export)
        archiver_sha = _file_sha256(Path(archiver_path))
    dense_channel = None
    if dense == "hash":
        dense_channel = EmbeddingDenseChannel.hashing(
            list(index.chunks.values())
        )
    elif dense in {"e5", "qwen3", "both"}:
        dense_channel = _cached_dense_channel(dense, split, questions)
    learned_sha = _file_sha256(Path(learned)) if learned else ""
    facts_ref = _display_path(facts_path)
    recompute = {
        "facts_sha256": facts_digest(str(facts_path)),
        "facts_path": facts_ref,
        "questions_sha256": questions_digest(split),
        "corpus_snapshot": corpus_digest((split,)),
        "archiver_sha256": archiver_sha,
        "learned_sha256": learned_sha,
    }
    command_parts = [
        "python3",
        "scripts/research/run_evidence_pack.py",
        f"--split {split}",
        f"--reranker {reranker}",
    ]
    if learned:
        command_parts.append(f"--learned {_display_path(learned)}")
    if archiver_path:
        command_parts.append(f"--archiver {_display_path(archiver_path)}")
    if dense != "off":
        command_parts.append(f"--dense {dense}")
    if limit is not None:
        command_parts.append(f"--limit {limit}")
    command_parts.append(f"--facts {facts_ref}")
    command = " ".join(command_parts)
    reports, evaluations = [], []
    for question in questions:
        needs_atoms = ()
        if archiver is not None:
            # PV entities are parsed inside the pipeline; the adapter filters by
            # the same question text, so pre-parse through the same parser.
            from accelerator_rag.evidence_pack.needs import parse_needs

            needs_atoms = archiver.atoms_for(parse_needs(question))
        report = run_question(
            index,
            question,
            reranker=reranker,
            learned_path=learned,
            archiver_atoms=needs_atoms,
            dense=dense_channel,
            command=command,
            recompute=recompute,
            include_baseline=True,
        )
        evaluation = _evaluate(report, question)
        report["evaluation"] = evaluation
        reports.append(report)
        evaluations.append(evaluation)

    deterministic = [
        report for report in reports if report["verdict_class"] == "deterministic"
    ]
    status_counts = dict(
        sorted(collections.Counter(r["verification"]["status"] for r in reports).items())
    )
    route_counts = dict(
        sorted(collections.Counter(r["route"] for r in reports).items())
    )
    task_status: dict[str, collections.Counter] = {}
    for report in reports:
        task_status.setdefault(report["task_type"], collections.Counter())[
            report["verification"]["status"]
        ] += 1
    channel_calls: collections.Counter = collections.Counter()
    round_counts: collections.Counter = collections.Counter()
    for report in reports:
        round_counts[len(report["rounds"])] += 1
        for item in report["rounds"]:
            for name, values in item["recall"]["channels"].items():
                channel_calls[name] += int(values.get("calls", 0) or 0)
    avg_tokens = (
        sum(report["pack"]["tokens"] for report in reports) / len(reports)
        if reports
        else 0.0
    )
    avg_budget = (
        sum(report["pack"]["budget"] for report in reports) / len(reports)
        if reports
        else 0.0
    )
    avg_parents = (
        sum(len(report["pack"]["parents"]) for report in reports) / len(reports)
        if reports
        else 0.0
    )
    avg_full_text_parents = (
        sum(
            sum(1 for parent in report["pack"]["parents"] if parent.get("full_text"))
            for report in reports
        )
        / len(reports)
        if reports
        else 0.0
    )
    avg_chars = (
        sum(report["pack"].get("chars", 0) for report in reports) / len(reports)
        if reports
        else 0.0
    )
    det_evals = [report["evaluation"] for report in deterministic]
    cluster_by_id = {
        question["base_id"]: question["cluster_id"] for question in questions
    }
    by_cluster: dict[str, list[dict]] = collections.defaultdict(list)
    for report in deterministic:
        by_cluster[cluster_by_id[report["question_id"]]].append(report)
    cluster_metrics = {}
    for cluster, members in sorted(by_cluster.items()):
        evals = [report["evaluation"] for report in members]
        cluster_metrics[cluster] = {
            "questions": len(members),
            "gold_chunk_recall_pack": round(
                sum(item["gold_chunk_recall_pack"] for item in evals) / len(evals), 4
            ),
            "gold_chunk_recall_baseline": round(
                sum(item["gold_chunk_recall_baseline"] for item in evals) / len(evals), 4
            ),
            "status_counts": dict(
                sorted(
                    collections.Counter(
                        report["verification"]["status"] for report in members
                    ).items()
                )
            ),
        }
    summary = {
        "question_count": len(reports),
        "deterministic_count": len(deterministic),
        "status_counts": status_counts,
        "route_counts": route_counts,
        "task_status_counts": {
            task: dict(sorted(counts.items()))
            for task, counts in sorted(task_status.items())
        },
        "round_counts": dict(sorted(round_counts.items())),
        "channel_calls": dict(sorted(channel_calls.items())),
        "avg_pack_tokens": round(avg_tokens, 2),
        "avg_budget": round(avg_budget, 2),
        "avg_parents": round(avg_parents, 2),
        "avg_full_text_parents": round(avg_full_text_parents, 2),
        "avg_pack_chars": round(avg_chars, 2),
        "det_avg_pack_tokens": round(
            sum(report["pack"]["tokens"] for report in deterministic) / len(deterministic), 2
        )
        if deterministic
        else None,
        "det_avg_budget": round(
            sum(report["pack"]["budget"] for report in deterministic) / len(deterministic), 2
        )
        if deterministic
        else None,
        "det_avg_parents": round(
            sum(len(report["pack"]["parents"]) for report in deterministic)
            / len(deterministic),
            2,
        )
        if deterministic
        else None,
        "det_avg_full_text_parents": round(
            sum(
                sum(
                    1
                    for parent in report["pack"]["parents"]
                    if parent.get("full_text")
                )
                for report in deterministic
            )
            / len(deterministic),
            2,
        )
        if deterministic
        else None,
        "gold_chunk_recall_pack": round(
            sum(item["gold_chunk_recall_pack"] for item in det_evals)
            / len(det_evals),
            4,
        )
        if det_evals
        else None,
        "gold_chunk_recall_baseline": round(
            sum(item["gold_chunk_recall_baseline"] for item in det_evals)
            / len(det_evals),
            4,
        )
        if det_evals
        else None,
        "gold_full_pack": sum(item["gold_full_pack"] for item in det_evals),
        "gold_full_baseline": sum(item["gold_full_baseline"] for item in det_evals),
        "required_fact_support_pack": round(
            sum(
                item["required_fact_support_pack"]
                for item in det_evals
                if item["required_fact_support_pack"] is not None
            )
            / max(
                1,
                sum(
                    1
                    for item in det_evals
                    if item["required_fact_support_pack"] is not None
                ),
            ),
            4,
        )
        if any(
            item["required_fact_support_pack"] is not None for item in det_evals
        )
        else None,
        "required_fact_support_baseline": round(
            sum(
                item["required_fact_support_baseline"]
                for item in det_evals
                if item["required_fact_support_baseline"] is not None
            )
            / max(
                1,
                sum(
                    1
                    for item in det_evals
                    if item["required_fact_support_baseline"] is not None
                ),
            ),
            4,
        )
        if any(
            item["required_fact_support_baseline"] is not None for item in det_evals
        )
        else None,
        "required_fact_support_questions": sum(
            1
            for item in det_evals
            if item["required_fact_support_pack"] is not None
        ),
        "required_fact_support_unavailable": sum(
            1
            for item in det_evals
            if item["required_fact_support_pack"] is None
        ),
        "conflicts": sum(item["conflicts"] for item in det_evals),
        "conflicts_preserved": sum(item["conflicts_preserved"] for item in det_evals),
        "conflicts_all": sum(len(report["pack"]["conflicts"]) for report in reports),
        "budget_failures": sum(not item["budget_ok"] for item in det_evals),
        "enumeration_required": sum(
            item["enumeration_required"] for item in det_evals
        ),
        "enumeration_satisfied": sum(
            item["enumeration_satisfied"] for item in det_evals
        ),
        "cluster_metrics": cluster_metrics,
        "family_count": len(
            {family for question in questions for family in question["family_ids"]}
        ),
        "cluster_count": len(by_cluster),
        "note": (
            "状态计数是机制状态，不是准确率；gold 指标按题聚合，"
            "cluster_metrics 给出按 cluster 的分解，正式报告仍须用聚类 bootstrap。"
        ),
    }
    return {
        "schema_version": RUN_SCHEMA,
        "split": split,
        "run": {
            "reranker": reranker,
            "learned": learned or "",
            "archiver": archiver_path or "",
            "dense": dense,
            "limit": limit,
        },
        "facts_sha256": recompute["facts_sha256"],
        "questions_sha256": recompute["questions_sha256"],
        "corpus_snapshot": recompute["corpus_snapshot"],
        "summary": summary,
        "reports": reports,
    }


def _canonical(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def verify(recorded_path: Path, *, facts_path: Path, limit: int | None) -> int:
    recorded = json.loads(recorded_path.read_text(encoding="utf-8"))
    if recorded.get("schema_version") != RUN_SCHEMA:
        print("unexpected report schema")
        return 1
    run = recorded.get("run", {})
    fresh = run_split(
        recorded["split"],
        facts_path=facts_path,
        reranker=run.get("reranker", "none"),
        learned=run.get("learned") or None,
        archiver_path=run.get("archiver") or None,
        limit=run.get("limit"),
        dense=run.get("dense", "off"),
    )
    if _canonical(recorded) != _canonical(fresh):
        for old, new in zip(recorded["reports"], fresh["reports"], strict=False):
            if _canonical(old) != _canonical(new):
                print(f"report differs: {old['question_id']}")
                break
        else:
            print("summary differs")
        return 1
    print(f"replay ok: {len(recorded['reports'])} reports")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=list(SPLITS))
    parser.add_argument("--facts", default=str(DEFAULT_FACTS))
    parser.add_argument("--reranker", default="rule", choices=["none", "rule", "learned"])
    parser.add_argument("--learned", default="")
    parser.add_argument("--archiver", default="")
    parser.add_argument(
        "--dense", default="off", choices=["off", "hash", "e5", "qwen3", "both"]
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", default="")
    parser.add_argument("--verify", default="", help="replay a recorded run")
    args = parser.parse_args(argv)
    facts_path = Path(args.facts)
    if args.verify:
        return verify(Path(args.verify), facts_path=facts_path, limit=args.limit)
    result = run_split(
        args.split,
        facts_path=facts_path,
        reranker=args.reranker,
        learned=args.learned or None,
        archiver_path=args.archiver or None,
        limit=args.limit,
        dense=args.dense,
    )
    out = Path(args.out) if args.out else ROOT / "reports" / "phase3" / f"{args.split}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(result, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
