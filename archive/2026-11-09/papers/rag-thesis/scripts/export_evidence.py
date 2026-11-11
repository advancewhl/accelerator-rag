"""Recompute paper tables from frozen local reports; never loads models or indexes."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import statistics
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
DATA = OUT / "data"
SOURCES: dict[str, dict] = {}


def read(path):
    p = ROOT / path
    SOURCES[path] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
    return json.loads(p.read_text())


def norm(text):
    text = unicodedata.normalize("NFKC", text).replace("\x00", "")
    text = re.sub(r"(?<=[A-Za-z])-\s+(?=[a-z])", "", text)
    return re.sub(r"\s+", "", text).casefold()


def matches(chunk, target):
    return (chunk["document_id"] == target["document_id"]
            and chunk["page_start"] <= target["page"] <= chunk["page_end"]
            and norm(target["excerpt"]) in norm(chunk["text"]))


def recompute(evaluation):
    ranks = []
    for case in evaluation["cases"]:
        if not case["answerable"]:
            continue
        satisfied = set()
        first = None
        for rank, result in enumerate(case["results"][:5], 1):
            for j, group in enumerate(case["evidence_groups"]):
                if any(matches(result["chunk"], t) for t in group["alternatives"]):
                    satisfied.add(j)
            complete = bool(satisfied) if case["judgment_mode"] == "any" else len(satisfied) == len(case["evidence_groups"])
            if complete and first is None:
                first = rank
        assert first == case["first_complete_rank"], case["id"]
        ranks.append(first)
    metrics = {f"Hit@{k}": sum(r is not None and r <= k for r in ranks) / len(ranks) for k in (1, 3, 5)}
    metrics["MRR@5"] = sum(1 / r if r else 0 for r in ranks) / len(ranks)
    for key, value in metrics.items():
        assert math.isclose(value, evaluation["metrics"][key], abs_tol=1e-12), key
    return metrics


def write_csv(name, rows):
    with (DATA / name).open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    registry = read("data/documents/registry.json")
    corpus = read("reports/rag-stage-two-five-corpus-audit.json")
    audit = read("reports/rag-stage-two-seven-one-evidence-audit.json")
    models = read("reports/rag-stage-two-eight-multilingual-retrieval.json")
    composition = read("reports/rag-stage-two-eight-one-dense-composition.json")
    rerank = read("reports/rag-stage-two-eight-two-reranking.json")
    passage = read("reports/rag-stage-two-six-dense-passage.json")
    direct = read("reports/rag-stage-two-five-retrieval-baseline.json")
    stage27 = read("reports/rag-stage-two-seven-embedding-comparison.json")
    production = read("reports/rag-production-readiness-20261026.json")
    stage3 = read("reports/rag-stage-three-production-loop.json")
    switch = read("reports/rag-ds-1017-switch-20261027.json")
    catalog = read("reports/rag-catalog-answer-20261027.json")
    benchmark = read("data/evaluation/retrieval_baseline.json")
    read("config/rag-production.json")
    docs = {d["doc_id"]: d for d in registry}
    excluded = corpus["retrieval_eligibility"]["per_document_ineligible"]
    corpus_rows = [{"document_id": d["document_id"], "title": d["title"],
                    "version": docs[d["document_id"]]["version"], "language": d["language"],
                    "category": d["category"], "pages": d["page_count"],
                    "canonical_chunks": d["chunk_count"],
                    "eligible_chunks": d["chunk_count"] - excluded.get(d["document_id"], 0)}
                   for d in corpus["documents"]]
    assert sum(d["pages"] for d in corpus_rows) == 2178
    assert sum(d["eligible_chunks"] for d in corpus_rows) == 4532
    write_csv("corpus.csv", corpus_rows)

    evaluations = {
        "BM25": audit["rejudged"]["BM25"],
        "BGE-small-zh": audit["rejudged"]["BAAI/bge-small-zh-v1.5"],
        "BGE-base-zh": audit["rejudged"]["BAAI/bge-base-zh-v1.5"],
        "E5": composition["evaluations"]["E5 single"],
        "BGE-M3": models["models"]["BAAI/bge-m3"]["evaluation"],
        "Qwen3": composition["evaluations"]["Qwen3 single"],
        "Language router": composition["evaluations"]["Language Router"],
        "Dual RRF": composition["evaluations"]["E5 + Qwen3 RRF"],
        "Dual + reranker": rerank["evaluations"]["E5 + Qwen3 + Reranker"],
        "E5 + multi-query": models["models"]["intfloat/multilingual-e5-base + multi-query"]["evaluation"],
        "Qwen3 + multi-query": models["models"]["Qwen/Qwen3-Embedding-0.6B + multi-query"]["evaluation"],
    }
    method_rows, rank_rows = [], []
    for name, evaluation in evaluations.items():
        metrics = recompute(evaluation)
        method_rows.append({"method": name, "judgment_revision": "evidence-contract-v2", "n": 21,
                            **metrics, "complete_at_5": round(metrics["Hit@5"] * 21)})
        rank_rows.extend({"method": name, "query_id": c["id"], "query": c["query"],
                          "language": c["language"], "language_relation": c["language_relation"],
                          "first_complete_rank": c["first_complete_rank"],
                          "groups_at_5": c["groups_satisfied_at_k"]["5"],
                          "required_groups": len(c["evidence_groups"])}
                         for c in evaluation["cases"] if c["answerable"])
    write_csv("retrieval-metrics-v2.csv", method_rows)
    write_csv("query-ranks-v2.csv", rank_rows)

    ablation_rows = []
    for method, versions in audit["metrics_comparison"].items():
        for version, metric in versions.items():
            ablation_rows.append({"experiment": "annotation-only rejudgment", "method": method,
                                 "condition": version, "Hit@5": metric["Hit@5"], "MRR@5": metric["MRR@5"]})
    for key in ("dense_a", "dense_b"):
        metric = recompute(passage[key])
        ablation_rows.append({"experiment": "passage A/B (v1 labels)", "method": "BGE-small-zh",
                             "condition": "direct" if key == "dense_a" else "passage",
                             "Hit@5": metric["Hit@5"], "MRR@5": metric["MRR@5"]})
    write_csv("historical-ablations.csv", ablation_rows)

    latency_rows = []
    for case in production["cases"]:
        if case.get("id") is None:
            continue
        response = case["response"]
        latency_rows.append({"query_id": case["id"], "answerable": case["answerable"],
                             "status": response["status"], **response["latency"]})
    assert len(latency_rows) == 32
    for field, expected in production["mean_latency_32"].items():
        assert math.isclose(statistics.mean(r[field] for r in latency_rows), expected, abs_tol=1e-10)
    supported = sum(r["supported"] for c in production["cases"] if c.get("answerable") for r in c["response"]["requirements"])
    requirements = sum(len(c["response"]["requirements"]) for c in production["cases"] if c.get("answerable"))
    assert (supported, requirements) == (32, 33)
    for c in production["cases"]:
        if "requirements" not in c["response"]:
            continue
        flags = [r["supported"] for r in c["response"]["requirements"]]
        calculated = "answered" if all(flags) else "partial" if any(flags) else "insufficient"
        assert calculated == c["response"]["status"]
    write_csv("production-latency-20261026.csv", latency_rows)
    queries = benchmark["queries"]
    benchmark_rows = [{"query_id": q["id"], "query": q["query"], "answerable": q["answerable"],
                       "language": q["language"], "category": q["category"],
                       "negative_type": q.get("negative_type", ""), "judgment_mode": q["judgment_mode"],
                       "evidence_groups": len(q["evidence_groups"])} for q in queries]
    write_csv("benchmark.csv", benchmark_rows)
    snapshot = {
        "as_of": "2026-10-27", "scope": "Local historical evidence; no new inference or live deployment checks",
        "corpus": corpus_rows, "overview": corpus["overview"],
        "eligibility": corpus["retrieval_eligibility"],
        "metrics_v2": method_rows, "ranks_v2": rank_rows,
        "historical_ablations": ablation_rows,
        "passage": passage["passage_statistics"], "input_audit": direct["embedding_input_audit"],
        "audit_summary": audit["audit_summary"], "benchmark": benchmark_rows,
        "model_passages": {k: v["passage_statistics"]["embedding_passages"] for k, v in stage27["models"].items()},
        "candidate_coverage": rerank["candidate_coverage"],
        "winning_coverage": rerank["final_winning_passage_coverage"],
        "rerank_cpu_timing": rerank["timing"],
        "latency": latency_rows,
        "production": {k: production[k] for k in ["model", "answerable", "negative", "requirement_coverage", "mean_latency_32", "mean_latency_answerable", "median_total_answerable", "frozen_citations"]},
        "stage3": {k: stage3[k] for k in ["standalone_rag", "answerable", "negative", "mean_latency_seconds"]},
        "switch_cases": switch["cases"], "catalog": catalog["catalog"],
        "verification": {"independently_rejudged_methods": len(evaluations),
                         "answerable_rankings_checked": len(rank_rows), "production_cases_checked": 32,
                         "production_state_recomputed": True, "latency_means_recomputed": True},
    }
    (DATA / "evidence-snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    # Fingerprint the implementation described by this manuscript as well as the measurements.
    for folder in ["corpus", "retrieval", "evaluation", "storage", "rag"]:
        for p in sorted((ROOT / "src/accelerator_rag" / folder).glob("*.py")):
            path = p.relative_to(ROOT).as_posix()
            SOURCES[path] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
    for p in [ROOT / "src/accelerator_rag/embedding.py", ROOT / "src/accelerator_rag/domain/knowledge.py"]:
        SOURCES[p.relative_to(ROOT).as_posix()] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
    (DATA / "source-manifest.json").write_text(json.dumps({"as_of": "2026-10-27", "sources": SOURCES}, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(snapshot["verification"], ensure_ascii=False))
    print("Corpus totals:", sum(d["pages"] for d in corpus_rows), sum(d["eligible_chunks"] for d in corpus_rows))


if __name__ == "__main__":
    main()
