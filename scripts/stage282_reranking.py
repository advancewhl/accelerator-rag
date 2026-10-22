"""Stage 2.8.2: frozen Top-10 candidate generation and one offline reranker run."""

import os

os.environ.update(
    HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false"
)
from pathlib import Path
from dataclasses import asdict, replace
from hashlib import sha256
from datetime import datetime, timezone
from time import perf_counter
import gc
import json
import sys

import torch
from accelerator_rag.ingestion import IngestionService
from accelerator_rag.corpus.eligibility import eligibility_audit
from accelerator_rag.domain.knowledge import KnowledgeChunk, RetrievalResult
from accelerator_rag.evaluation.retrieval import evaluate, load_queries, target_matches

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reports/rag-stage-two-eight-one-dense-composition.json"
HISTORY = json.loads(BASE.read_text())
BASE_DIGEST = sha256(BASE.read_bytes()).hexdigest()
WORK = ROOT / "tmp/stage-two-eight-two"
WORK.mkdir(exist_ok=True)
CACHE = WORK / "original-query-candidates.json"
REPORT = ROOT / "reports/rag-stage-two-eight-two-reranking"
NAMES = {"E5": "intfloat/multilingual-e5-base", "Qwen3": "Qwen/Qwen3-Embedding-0.6B"}
torch.set_num_threads(6)


def verify_frozen():
    for path, digest in {
        **HISTORY["frozen_sha256"],
        **HISTORY["source_sha256"],
    }.items():
        assert sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    assert sha256(BASE.read_bytes()).hexdigest() == BASE_DIGEST


def load_corpus():
    verify_frozen()
    docs = IngestionService(ROOT).ingest_all_registered_pdfs()
    eligible, _ = eligibility_audit([c for d in docs for c in d.chunks])
    assert len(docs) == 13 and len(eligible) == 4532
    assert (
        sha256(
            json.dumps([asdict(c) for c in eligible], sort_keys=True).encode()
        ).hexdigest()
        == HISTORY["canonical_parent_sha256"]
    )
    qs = load_queries(
        ROOT / "data/evaluation/retrieval_baseline.json", docs, eligible_chunks=eligible
    )
    assert len(qs) == 32 and sum(q.answerable for q in qs) == 21
    return qs, {c.chunk_id: c for c in eligible}


def prepare():
    from qdrant_client import QdrantClient
    from accelerator_rag.embedding import EmbeddingModel
    from accelerator_rag.retrieval.dense import DenseRetriever
    from accelerator_rag.retrieval.passages import PassageBuilder
    from accelerator_rag.retrieval.index_contract import DenseIndexContract
    from accelerator_rag.storage.qdrant_passages import QdrantPassageStore

    qs, parents = load_corpus()
    output = {"baseline_sha256": BASE_DIGEST, "rankings": {}, "indexes": {}}
    for short, name in NAMES.items():
        meta = HISTORY["indexes"][name]
        fp = meta["fingerprint"]
        print("LOAD", short, flush=True)
        embedder = EmbeddingModel(
            name, model_path=fp["resolved_local_model_path"], batch_size=8
        )
        assert embedder.fingerprint() == fp
        builder = PassageBuilder(embedder)
        contract = DenseIndexContract.from_fingerprint(fp, builder.contract)
        assert contract.contract_id == meta["dense_index_contract_id"]
        client = QdrantClient(path=meta["index_path"])
        try:
            store = QdrantPassageStore(client, meta["collection"], contract)
            store.verify_contract()
            count = store.point_count()
            dense = DenseRetriever(embedder, store, passage_builder=builder)
            output["rankings"][short] = {}
            started = perf_counter()
            for q in qs:
                hits = dense.search(q.query, top_k=10)
                traces = dense.last_passage_trace
                expected = HISTORY["original_query_top10"][name][q.id]
                assert [h.chunk.chunk_id for h in hits] == [
                    h["chunk"]["chunk_id"] for h in expected
                ], q.id
                assert len(hits) == len(traces) == 10
                for hit, trace in zip(hits, traces, strict=True):
                    assert hit.chunk == parents[hit.chunk.chunk_id]
                    assert trace["parent_chunk_id"] == hit.chunk.chunk_id
                    assert trace["passage_excerpt"] in hit.chunk.text
                output["rankings"][short][q.query] = {
                    "query_id": q.id,
                    "results": [asdict(h) for h in hits],
                    "passage_trace": traces,
                }
                print("SEARCH", short, q.id, flush=True)
            assert store.point_count() == count
            output["indexes"][name] = {
                **meta,
                "point_count_before": count,
                "point_count_after": count,
                "top10_ids_match_stage281": "32/32",
                "query_encoding_search_count": 32,
                "generation_seconds": perf_counter() - started,
            }
        finally:
            client.close()
        del dense, store, embedder, builder
        gc.collect()
    verify_frozen()
    CACHE.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print("PREPARED", CACHE, flush=True)


class CachedDense:
    def __init__(self, rows):
        self.rows = rows
        self.last_passage_trace = []

    def search(self, query, *, top_k):
        assert top_k == 10
        row = self.rows[query]
        print("RERANK CANDIDATES", row["query_id"], flush=True)
        self.last_passage_trace = row["passage_trace"]
        return [
            RetrievalResult(
                h["rank"], h["score"], KnowledgeChunk(**h["chunk"]), h["retriever"]
            )
            for h in row["results"]
        ]


def coverage(q, chunks):
    groups = [
        i + 1
        for i, g in enumerate(q.evidence_groups)
        if any(target_matches(c, t) for c in chunks for t in g.alternatives)
    ]
    complete = (
        bool(groups)
        if q.judgment_mode == "any"
        else bool(groups) and len(groups) == len(q.evidence_groups)
    )
    return {
        "groups": groups,
        "required_groups": len(q.evidence_groups),
        "complete": complete,
    }


def run():
    from accelerator_rag.retrieval.reranker import Qwen3Reranker
    from accelerator_rag.retrieval.dense_reranked import DenseRerankedRetriever

    qs, parents = load_corpus()
    cache = json.loads(CACHE.read_text())
    assert cache["baseline_sha256"] == BASE_DIGEST
    preflight = []
    for q in qs:
        if not q.answerable:
            continue
        union = {}
        passages = []
        for short, name in NAMES.items():
            row = cache["rankings"][short][q.query]
            assert [h["chunk"]["chunk_id"] for h in row["results"]] == [
                h["chunk"]["chunk_id"]
                for h in HISTORY["original_query_top10"][name][q.id]
            ]
            for hit, trace in zip(row["results"], row["passage_trace"], strict=True):
                parent = KnowledgeChunk(**hit["chunk"])
                assert parent == parents[parent.chunk_id]
                union[parent.chunk_id] = parent
                passages.append(replace(parent, text=trace["passage_excerpt"]))
        preflight.append(
            {
                "query_id": q.id,
                "canonical_parent": coverage(q, list(union.values())),
                "actual_retrieved_passages": coverage(q, passages),
            }
        )
    print(
        "CANDIDATE CEILING",
        sum(c["canonical_parent"]["complete"] for c in preflight),
        "ACTUAL PASSAGE CEILING",
        sum(c["actual_retrieved_passages"]["complete"] for c in preflight),
        flush=True,
    )
    download = json.loads((WORK / "download.json").read_text())
    reranker = Qwen3Reranker(download["path"], batch_size=4)
    identity = {
        **reranker.fingerprint(),
        "resolved_revision": download["resolved_revision"],
    }
    if "weights_lfs_sha256_verified" in download:
        assert (
            identity["weights_files"]["model.safetensors"]
            == download["weights_lfs_sha256_verified"]
        )
        identity["official_lfs_sha256_verified"] = True
    print("RERANKER LOADED", reranker.load_seconds, flush=True)
    dense = {name: CachedDense(cache["rankings"][name]) for name in NAMES}
    retriever = DenseRerankedRetriever(dense["E5"], dense["Qwen3"], reranker)
    # No benchmark evidence/IDs are passed into the runtime retriever.
    started = perf_counter()
    evaluation = evaluate(retriever, qs)
    elapsed = perf_counter() - started
    print("EVALUATED", evaluation["metrics"], flush=True)
    ceilings = []
    final_passage_coverage = []
    traces = {}
    candidates = {}
    for q in qs:
        pool = retriever.candidates[q.query]
        traces[q.id] = retriever.traces[q.query]
        candidates[q.id] = pool
        if q.answerable:
            parent_chunks = [KnowledgeChunk(**c) for c in pool["parents"]]
            passage_chunks = [
                replace(parents[c["parent_chunk_id"]], text=c["passage_text"])
                for c in pool["passages"]
            ]
            ceilings.append(
                {
                    "query_id": q.id,
                    "canonical_parent": coverage(q, parent_chunks),
                    "actual_retrieved_passages": coverage(q, passage_chunks),
                }
            )
            winners = [
                replace(parents[t["parent_chunk_id"]], text=t["winning_passage_text"])
                for t in traces[q.id][:5]
            ]
            final_passage_coverage.append({"query_id": q.id, **coverage(q, winners)})
    # Coverage is an offline diagnosis, never an input to reranking.
    parent_ceiling = sum(c["canonical_parent"]["complete"] for c in ceilings)
    passage_ceiling = sum(c["actual_retrieved_passages"]["complete"] for c in ceilings)
    assert ceilings == preflight
    assert parent_ceiling >= HISTORY["candidate_union"]["complete_count"]
    evaluations = {
        label: HISTORY["evaluations"][label]
        for label in ["E5 single", "Language Router", "E5 + Qwen3 RRF"]
    }
    label = "E5 + Qwen3 + Reranker"
    evaluations[label] = evaluation
    by_method = {
        name: {c["id"]: c for c in e["cases"]} for name, e in evaluations.items()
    }
    successes = {
        name: {
            q.id
            for q in qs
            if q.answerable and rows[q.id]["first_complete_rank"] is not None
        }
        for name, rows in by_method.items()
    }
    new = successes[label]
    changes = {
        base: {
            "gains": sorted(new - successes[base]),
            "losses": sorted(successes[base] - new),
        }
        for base in ["E5 single", "Language Router"]
    }
    answerable_ids = {q.id for q in qs if q.answerable}
    misses = sorted(answerable_ids - new)
    ranking_misses = [
        c["query_id"]
        for c in ceilings
        if c["canonical_parent"]["complete"] and c["query_id"] not in new
    ]
    unseen_evidence = [
        c["query_id"]
        for c in ceilings
        if c["canonical_parent"]["complete"]
        and not c["actual_retrieved_passages"]["complete"]
    ]
    hits = len(new)
    choice = "A" if hits >= 20 else "B" if hits == 19 else "C"
    decision = {
        "choice": choice,
        "reason": "达到 20/21，推荐固化双模型候选生成加 Qwen3-Reranker-0.6B；停止本轮实验。"
        if choice == "A"
        else "仍为 19/21，当前重排器不足；下一阶段再试更强 reranker，本轮不调参。"
        if choice == "B"
        else "低于 19/21，当前 0.6B reranker 在此固定配置与 benchmark 上不适用；保留 Language Router，不调参。",
    }
    focus_ids = [
        "xfel-normal-energy",
        "shine-ioc-startup",
        "shine-main-linac",
        "cryo-interlock",
    ]
    focus = {
        name: {
            qid: {
                "first_complete_rank": rows[qid]["first_complete_rank"],
                "groups_at5": rows[qid]["groups_satisfied_at_k"]["5"],
                "required_groups": len(rows[qid]["evidence_groups"]),
            }
            for qid in focus_ids
        }
        for name, rows in by_method.items()
    }
    negatives = [
        {
            "query_id": c["id"],
            "top1_score": c["top1_score"],
            "result_count": len(c["results"]),
        }
        for c in evaluation["cases"]
        if not c["answerable"]
    ]
    assert len(negatives) == 11 and all(
        c["result_count"] == 5 and 0 <= c["top1_score"] <= 1 for c in negatives
    )
    verify_frozen()
    result = {
        "status": "EXECUTED",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "control_source": {"path": str(BASE.relative_to(ROOT)), "sha256": BASE_DIGEST},
        "frozen_sha256": HISTORY["frozen_sha256"],
        "source_sha256": HISTORY["source_sha256"],
        "canonical_parent_sha256": HISTORY["canonical_parent_sha256"],
        "judgment_revision": HISTORY["judgment_revision"],
        "pdf_count": 13,
        "eligible_parents": 4532,
        "answerable_query_count": 21,
        "negative_query_count": 11,
        "configuration": {
            "candidate_parent_depth_per_model": 10,
            "final_parent_depth": 5,
            "query": "original only",
            "passage_input": "actual winning passage text, no full parent expansion",
            "passage_dedupe": "canonical parent ID + exact passage text; retain all source IDs",
            "parent_aggregation": "max child reranker score",
            "sort": "reranker score descending, parent ID ascending",
            "instruction": "official default, uniform across queries",
            "offline_benchmark": True,
        },
        "reranker": identity,
        "indexes": cache["indexes"],
        "document_embeddings_computed": 0,
        "remote_inference_requests": 0,
        "candidate_cache_sha256": sha256(CACHE.read_bytes()).hexdigest(),
        "timing": {
            "model_load_seconds": reranker.load_seconds,
            "total_rerank_seconds": retriever.rerank_seconds,
            "evaluation_wall_seconds": elapsed,
            "cpu_threads": torch.get_num_threads(),
            "average_candidate_parents": sum(
                p["parent_count"] for p in candidates.values()
            )
            / 32,
            "average_candidate_passages": sum(
                p["passage_count"] for p in candidates.values()
            )
            / 32,
            "scored_pairs": reranker.scored_pairs,
            "max_observed_pair_tokens": reranker.max_observed_tokens,
            "truncated_pairs": 0,
        },
        "candidate_coverage": {
            "canonical_parent_complete_count": parent_ceiling,
            "actual_retrieved_passage_complete_count": passage_ceiling,
            "count": 21,
            "cases": ceilings,
        },
        "final_winning_passage_coverage": {
            "description": "Diagnostic only; does not replace the frozen canonical-parent metric",
            "complete_count": sum(c["complete"] for c in final_passage_coverage),
            "count": 21,
            "cases": final_passage_coverage,
        },
        "evaluations": evaluations,
        "qwen3_single_supplement": HISTORY["evaluations"]["Qwen3 single"]["metrics"],
        "changes": changes,
        "misses": misses,
        "candidate_complete_but_final_miss": ranking_misses,
        "parent_complete_but_winning_passages_incomplete": unseen_evidence,
        "focus": focus,
        "negative_observations": negatives,
        "final_and_full_rerank_provenance": traces,
        "candidate_pools_and_scores": candidates,
        "original_dense_rankings": cache["rankings"],
        "decision": decision,
        "validation": {
            "frozen_hashes_match": True,
            "dense_top10_match_stage281": "32/32 each",
            "index_point_counts_unchanged": True,
            "negative_scores_finite_and_in_range": True,
        },
        "code_sha256": {
            p: sha256((ROOT / p).read_bytes()).hexdigest()
            for p in [
                "scripts/stage282_reranking.py",
                "src/accelerator_rag/retrieval/reranker.py",
                "src/accelerator_rag/retrieval/dense_reranked.py",
            ]
        },
    }
    REPORT.with_suffix(".json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    render(result)
    print(
        json.dumps(
            {
                "candidate_ceiling": parent_ceiling,
                "actual_passage_ceiling": passage_ceiling,
                "metrics": evaluation["metrics"],
                "changes": changes,
                "misses": misses,
                "ranking_misses": ranking_misses,
                "focus": focus[label],
                "decision": decision,
                "timing": result["timing"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def render(r):
    lines = [
        "# Stage 2.8.2：双模型候选重排",
        "",
        "| Method | Hit@1 | Hit@3 | Hit@5 | MRR@5 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, e in r["evaluations"].items():
        lines.append(
            "| "
            + name
            + " | "
            + " | ".join(
                f"{e['metrics'][k]:.4f}" for k in ("Hit@1", "Hit@3", "Hit@5", "MRR@5")
            )
            + " |"
        )
    c = r["candidate_coverage"]
    hits = 21 - len(r["misses"])
    lines += [
        "",
        f"状态：EXECUTED。Top-10 + Top-10 canonical parent candidate coverage：{c['canonical_parent_complete_count']}/21；实际 winning passage coverage：{c['actual_retrieved_passage_complete_count']}/21；final reranked Hit@5：{hits}/21。候选覆盖率不是正式 Top-5 指标。",
        "",
        "## 方法与模型",
        "",
        "复用 E5 和 Qwen3-Embedding-0.6B 既有签名索引，对每条原始 query 各取 Top-10 canonical parents。两路 Top-10 parent IDs 与 Stage 2.8.1 均为 32/32 一致。按 parent ID 去重，只将各模型实际 winning passage text 送入本地 reranker；同 parent 的不同 passage 分别评分，完全相同文本合并并保留来源。parent 取 child 最大分数，最终按 reranker 分数排序，返回 Top-5 canonical KnowledgeChunk。未混加 cosine score。",
        "",
        "采用下载版本的[官方模型说明](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)中的 Transformers contract：固定默认 instruction、system/user/assistant 前后缀、末 token 的 yes/no logits 归一化概率。CPU FP32，左填充，固定 batch size 4、max length 8192；无截断。只计算末位置 logits，不生成答案。所有 benchmark 推理离线执行。",
        "",
        f"模型 revision：`{r['reranker']['resolved_revision']}`。本地大小：{r['reranker']['local_model_bytes'] / 1024**3:.3f} GiB。完整 weights/config/tokenizer SHA256、prompt 和配置见 JSON。",
        "",
        "## 命中变化",
        "",
    ]
    for base, delta in r["changes"].items():
        lines += [
            f"相对 {base}：",
            "",
            "- 新增完整命中："
            + ("、".join(f"`{x}`" for x in delta["gains"]) or "无")
            + "。",
            "- 丢失完整命中："
            + ("、".join(f"`{x}`" for x in delta["losses"]) or "无")
            + "。",
            "",
        ]
    lines += [
        "## 重点问题",
        "",
        "| Method | normal-energy | ioc-startup | main-linac | cryo-interlock |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, cells in r["focus"].items():
        values = [
            "complete"
            if cell["first_complete_rank"] is not None
            else f"{cell['groups_at5']}/{cell['required_groups']} groups"
            for cell in cells.values()
        ]
        lines.append("| " + name + " | " + " | ".join(values) + " |")
    lines += [
        "",
        "候选完整但 final Top-5 仍 miss："
        + ("、".join(f"`{x}`" for x in r["candidate_complete_but_final_miss"]) or "无")
        + "。",
        "",
        "parent 完整、实际 winning passages 不完整："
        + (
            "、".join(
                f"`{x}`" for x in r["parent_complete_but_winning_passages_incomplete"]
            )
            or "无"
        )
        + "。canonical parent coverage 不能证明重排器已看到这些证据。正式指标仍按冻结 canonical parent evidence contract 计算；即使 parent 最终命中，也须区分是否由已评分 passage 支持。",
        "",
        "最终 miss：" + ("、".join(f"`{x}`" for x in r["misses"]) or "无") + "。",
        "",
        f"最终 Top-5 winning passages 的证据覆盖：{r['final_winning_passage_coverage']['complete_count']}/21。这是来源诊断，不替代冻结的 canonical parent 指标。",
        "",
        "IOC startup 的候选缺失与重排失败分别记录在 JSON。若候选仍为 1/2 groups，重排无法补齐缺失证据。未为任何 query 改写、扩 Top-K 或特判。",
        "",
        "## 性能与完整性",
        "",
    ]
    t = r["timing"]
    lines += [
        f"CPU threads：{t['cpu_threads']}；model load：{t['model_load_seconds']:.2f} s；32 条 query 总 rerank：{t['total_rerank_seconds']:.2f} s。平均每条 query：{t['average_candidate_parents']:.2f} 个 parents、{t['average_candidate_passages']:.2f} 个 passages；共评分 {t['scored_pairs']} 对。最大输入 {t['max_observed_pair_tokens']} tokens，无截断。",
        "",
        "冻结 evidence-contract-v2、21 条可回答问题、11 条负例、13 份 PDF、4532 个 eligible parents。11 条负例均得到 5 条结果，score 有限且位于 0～1；没有阈值或拒答结论。document embedding 为 0，未重建索引；冻结文件/PDF/parent 哈希和索引点数核对通过。",
        "",
        "补充：Qwen3 single Hit@5 为 17/21。主表历史指标直接复用。每个最终结果的来源、两路原始 rank、winning passage ID/text/source 和全部候选评分见 JSON。",
        "",
        "## 决定",
        "",
        f"**{r['decision']['choice']}**：{r['decision']['reason']}",
        "",
        "未新增测试或运行 pytest，未修改 Agent、benchmark、evidence、chunking 或 eligibility，未调用 qwen3-vl，未 commit 或 push。本轮结束，不自动进入下一阶段。",
        "",
    ]
    REPORT.with_suffix(".md").write_text("\n".join(lines))


if __name__ == "__main__":
    if sys.argv[1:] == ["--prepare"]:
        prepare()
    elif not sys.argv[1:]:
        run()
    else:
        raise SystemExit(
            "use --prepare to collect candidates, then no arguments to rerank"
        )
