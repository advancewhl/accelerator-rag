"""Run frozen Stage 2.8.1 using local weights and existing signed indexes only."""

import os

os.environ.update(
    HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false"
)
from pathlib import Path
from dataclasses import asdict
from hashlib import sha256
from datetime import datetime, timezone
import json
from time import perf_counter

import torch
from qdrant_client import QdrantClient
from accelerator_rag.embedding import EmbeddingModel
from accelerator_rag.ingestion import IngestionService
from accelerator_rag.corpus.eligibility import eligibility_audit
from accelerator_rag.evaluation.retrieval import evaluate, load_queries, target_matches
from accelerator_rag.retrieval.composition import (
    query_language,
    LanguageRoutedDenseRetriever,
    DualDenseRRFRetriever,
)
from accelerator_rag.retrieval.dense import DenseRetriever
from accelerator_rag.retrieval.passages import PassageBuilder
from accelerator_rag.retrieval.index_contract import DenseIndexContract
from accelerator_rag.storage.qdrant_passages import QdrantPassageStore

root = Path(__file__).resolve().parents[1]
torch.set_num_threads(6)
source_path = root / "reports/rag-stage-two-eight-multilingual-retrieval.json"
source_digest = sha256(source_path.read_bytes()).hexdigest()
history = json.loads(source_path.read_text())
e5_name, qwen_name = "intfloat/multilingual-e5-base", "Qwen/Qwen3-Embedding-0.6B"
focus = ["xfel-normal-energy", "shine-ioc-startup", "cryo-interlock"]
report_path = root / "reports/rag-stage-two-eight-one-dense-composition"


def verify_frozen():
    for path, digest in history["frozen_sha256"].items():
        assert sha256((root / path).read_bytes()).hexdigest() == digest, path
    for path, digest in history["source_sha256"].items():
        assert sha256((root / path).read_bytes()).hexdigest() == digest, path


class CachedTop10:
    """Experiment-only cache: both methods consume identical original-query searches."""

    def __init__(self, dense, name):
        self.dense, self.name, self.rows = dense, name, {}
        self.seconds = 0.0

    def search(self, query, *, top_k):
        assert 1 <= top_k <= 10
        if query not in self.rows:
            start = perf_counter()
            self.rows[query] = self.dense.search(query, top_k=10)
            self.seconds += perf_counter() - start
            print("SEARCH", self.name, len(self.rows), flush=True)
        return self.rows[query][:top_k]


def cases(evaluation):
    return {c["id"]: c for c in evaluation["cases"]}


def coverage(q, hits):
    groups = [
        i + 1
        for i, group in enumerate(q.evidence_groups)
        if any(
            target_matches(h.chunk, target)
            for h in hits
            for target in group.alternatives
        )
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


verify_frozen()
docs = IngestionService(root).ingest_all_registered_pdfs()
eligible, _ = eligibility_audit([c for d in docs for c in d.chunks])
assert len(docs) == 13 and len(eligible) == 4532
assert (
    sha256(
        json.dumps([asdict(c) for c in eligible], sort_keys=True).encode()
    ).hexdigest()
    == history["canonical_parent_sha256"]
)
queries = load_queries(
    root / "data/evaluation/retrieval_baseline.json", docs, eligible_chunks=eligible
)
assert len(queries) == 32 and sum(q.answerable for q in queries) == 21
clients, stores, retrievers, indexes = [], {}, {}, {}
try:
    for name in (e5_name, qwen_name):
        # Metadata only: no plans or multi-query rankings are read or used.
        metadata = history["models"][name + " + multi-query"]
        fp = metadata["fingerprint_used"]
        print("LOAD", name, flush=True)
        embedder = EmbeddingModel(
            name, model_path=fp["resolved_local_model_path"], batch_size=8
        )
        assert embedder.fingerprint() == fp
        builder = PassageBuilder(embedder)
        contract = DenseIndexContract.from_fingerprint(fp, builder.contract)
        assert contract.contract_id == metadata["dense_index_contract_id"]
        client = QdrantClient(path=metadata["index_path"])
        clients.append(client)
        store = QdrantPassageStore(client, metadata["collection"], contract)
        store.verify_contract()
        stores[name] = store
        indexes[name] = {
            k: metadata[k]
            for k in ("index_path", "collection", "dense_index_contract_id")
        }
        indexes[name].update(point_count_before=store.point_count(), fingerprint=fp)
        retrievers[name] = CachedTop10(
            DenseRetriever(embedder, store, passage_builder=builder), name
        )
    router = LanguageRoutedDenseRetriever(retrievers[e5_name], retrievers[qwen_name])
    rrf = DualDenseRRFRetriever(retrievers[e5_name], retrievers[qwen_name])
    evaluations = {
        label: history["models"][name]["evaluation"]
        for label, name in [("E5 single", e5_name), ("Qwen3 single", qwen_name)]
    }
    print("EVALUATE ROUTER", flush=True)
    evaluations["Language Router"] = evaluate(router, queries)
    print("EVALUATE RRF", flush=True)
    evaluations["E5 + Qwen3 RRF"] = evaluate(rrf, queries)
    rows = {label: cases(e) for label, e in evaluations.items()}
    consistency = {}
    for label, name in [("E5 single", e5_name), ("Qwen3 single", qwen_name)]:
        consistency[name] = {
            q.id: [h.chunk.chunk_id for h in retrievers[name].rows[q.query][:5]]
            == [r["chunk"]["chunk_id"] for r in rows[label][q.id]["results"]]
            for q in queries
        }
        assert all(consistency[name].values()), consistency[name]
        assert len(retrievers[name].rows) == 32
        indexes[name].update(
            point_count_after=stores[name].point_count(),
            query_encoding_search_count=32,
            search_seconds=retrievers[name].seconds,
        )
        assert indexes[name]["point_count_after"] == indexes[name]["point_count_before"]
    complementarity = {
        key: [] for key in ("E5_only", "Qwen3_only", "both_hit", "both_miss")
    }
    union = []
    selections = []
    chinese = []
    for q in queries:
        selected = qwen_name if query_language(q.query) == "zh" else e5_name
        selections.append(
            {
                "query_id": q.id,
                "query": q.query,
                "detected_language": query_language(q.query),
                "selected_model": selected,
            }
        )
        if not q.answerable:
            continue
        e5_hit = rows["E5 single"][q.id]["first_complete_rank"] is not None
        qwen_hit = rows["Qwen3 single"][q.id]["first_complete_rank"] is not None
        key = (
            "both_hit"
            if e5_hit and qwen_hit
            else "E5_only"
            if e5_hit
            else "Qwen3_only"
            if qwen_hit
            else "both_miss"
        )
        complementarity[key].append(q.id)
        candidates = {
            h.chunk.chunk_id: h
            for name in (e5_name, qwen_name)
            for h in retrievers[name].rows[q.query][:5]
        }
        union.append(
            {
                "query_id": q.id,
                "candidate_count": len(candidates),
                **coverage(q, list(candidates.values())),
            }
        )
        if query_language(q.query) == "zh":
            chinese.append(
                {
                    "query_id": q.id,
                    "selected_model": selected,
                    **{
                        label: rows[label][q.id]["first_complete_rank"]
                        for label in ("E5 single", "Qwen3 single", "Language Router")
                    },
                }
            )
    assert len(chinese) == 8
    cross = {
        label: {
            qid: (
                "complete"
                if rows[label][qid]["first_complete_rank"] is not None
                else f"{rows[label][qid]['groups_satisfied_at_k']['5']}/{len(rows[label][qid]['evidence_groups'])} groups"
            )
            for qid in focus
        }
        for label in evaluations
    }
    misses = {
        label: [
            q.id
            for q in queries
            if q.answerable and rows[label][q.id]["first_complete_rank"] is None
        ]
        for label in evaluations
    }
    hits = {label: 21 - len(ids) for label, ids in misses.items()}
    # Selection is descriptive; no production default is changed by this experiment.
    if hits["Language Router"] >= 20:
        choice, reason = (
            "A",
            "Language Router 达到 20/21，优先采用一次 query encoding/search 的简单策略。",
        )
    elif hits["E5 + Qwen3 RRF"] >= 20:
        choice, reason = (
            "B",
            "Dual Dense RRF 达到 20/21，采用两次 query encoding/search 的互补策略。",
        )
    elif hits["Language Router"] <= 18 and hits["E5 + Qwen3 RRF"] <= 18:
        choice, reason = (
            "C",
            "两个组合均未超过 18/21，下一阶段比较 Qwen3-Embedding-4B。",
        )
    else:
        choice = "A" if hits["Language Router"] >= hits["E5 + Qwen3 RRF"] else "B"
        reason = "实测落入原决策规则未覆盖的 19/21 分支。两种组合 Hit@5 相同，Language Router 的 MRR@5 更高（0.6048 对 0.5786），每条 query 仅需一次 encoding/search，因此下一步选择 A：固化 Language Router。它仍有 IOC startup 和 main linac 两条 miss，尚未达到 20/21；本轮不修改生产默认配置。"
    verify_frozen()
    assert sha256(source_path.read_bytes()).hexdigest() == source_digest
    result = {
        "status": "EXECUTED",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "judgment_revision": history["judgment_revision"],
        "frozen_sha256": history["frozen_sha256"],
        "source_sha256": history["source_sha256"],
        "canonical_parent_sha256": history["canonical_parent_sha256"],
        "pdf_count": 13,
        "eligible_parents": 4532,
        "answerable": 21,
        "negatives": 11,
        "configuration": {
            "router": "CJK U+3400–U+9FFF / U+F900–U+FAFF → Qwen3; otherwise E5",
            "rrf_k": 60,
            "weights": {"E5": 1, "Qwen3": 1},
            "per_model_parent_depth": 10,
            "final_depth": 5,
            "tie_break": "canonical parent ID ascending",
            "raw_query_only": True,
        },
        "indexes": indexes,
        "document_embeddings_computed": 0,
        "query_encodings_total": 64,
        "llm_requests": 0,
        "baseline_top5_parent_consistency": consistency,
        "evaluations": evaluations,
        "complementarity": complementarity,
        "success_set_union_count": 21 - len(complementarity["both_miss"]),
        "candidate_union": {
            "description": "E5 Top-5 ∪ Qwen3 Top-5 evidence coverage; not a formal Top-5 metric",
            "complete_count": sum(r["complete"] for r in union),
            "count": 21,
            "cases": union,
        },
        "query_selections": selections,
        "chinese_answerable": chinese,
        "focus": cross,
        "misses": misses,
        "rrf_trace": rrf.traces,
        "original_query_top10": {
            name: {q.id: [asdict(h) for h in r.rows[q.query]] for q in queries}
            for name, r in retrievers.items()
        },
        "decision": {"choice": choice, "reason": reason, "hit_counts": hits},
        "limits": [
            "固定小样本的描述性结果；未验证统计显著性。",
            "11 条 negatives 仅保留检索观察；没有拒答阈值，不能据此证明拒答能力。",
        ],
        "code_sha256": {
            p: sha256((root / p).read_bytes()).hexdigest()
            for p in [
                "src/accelerator_rag/retrieval/composition.py",
                "scripts/stage281_dense_composition.py",
            ]
        },
    }
    report_path.with_suffix(".json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    lines = [
        "# Stage 2.8.1：双模型检索组合",
        "",
        "状态：EXECUTED。冻结 evidence-contract-v2、21 条可回答问题、11 条负例、13 份 PDF 和 4532 个 eligible parents。只编码原始 query，复用现有签名索引；document embedding、LLM 请求均为 0。",
        "",
        "| Method | Hit@1 | Hit@3 | Hit@5 | MRR@5 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label, e in evaluations.items():
        m = e["metrics"]
        lines.append(
            "| "
            + label
            + " | "
            + " | ".join(f"{m[k]:.4f}" for k in ("Hit@1", "Hit@3", "Hit@5", "MRR@5"))
            + " |"
        )
    lines += [
        "",
        f"Language Router：{hits['Language Router']}/21；Dual Dense RRF：{hits['E5 + Qwen3 RRF']}/21。单模型历史指标直接复用；本轮重新检索的两路 Top-5 parent IDs 均与历史 32/32 一致。",
        "",
        "## 固定方法与成本",
        "",
        "路由仅根据原始 query 是否含明显 CJK 字符选择模型。英文走 E5，中文走 Qwen3。每条 query 一次 encoding/search；部署需能加载两套本地模型。",
        "",
        "RRF 对原始 query 分别取两模型 Top-10 canonical parents，按 rank 等权融合，固定 k=60，按 canonical parent ID 去重并返回 Top-5；同分按 parent ID 排序。没有跨模型相加 cosine score。每条 query 两次 encoding/search，不增加 document indexing。本实验共享原始检索缓存，合计 64 次 query encoding/search。",
        "",
        "## 精确互补性",
        "",
    ]
    for key, ids in complementarity.items():
        lines.append(
            f"- {key}（{len(ids)}）：" + "、".join(f"`{i}`" for i in ids) + "。"
        )
    lines += [
        "",
        f"成功集合并集：{result['success_set_union_count']}/21。Qwen3 相对 E5 的 3 条 Top-5 回退即 E5_only 列表。",
        "",
        f"候选并集 evidence coverage：{result['candidate_union']['complete_count']}/21。它最多包含 10 个 parent，只表示候选池覆盖上界，不是正式 Hit@5。",
        "",
        "## 重点问题",
        "",
        "| Method | normal-energy | ioc-startup | cryo-interlock |",
        "| --- | --- | --- | --- |",
    ]
    for label, cells in cross.items():
        lines.append("| " + label + " | " + " | ".join(cells[i] for i in focus) + " |")
    lines += [
        "",
        "## 8 条中文可回答问题",
        "",
        "| query_id | selected model | E5 rank | Qwen3 rank | router rank |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in chinese:
        lines.append(
            "| "
            + row["query_id"]
            + " | Qwen3-Embedding-0.6B | "
            + " | ".join(
                str(row[k]) if row[k] is not None else "miss"
                for k in ("E5 single", "Qwen3 single", "Language Router")
            )
            + " |"
        )
    lines += [
        "",
        "## 所有 query 的模型选择",
        "",
        "| query_id | detected language | selected model |",
        "| --- | --- | --- |",
    ]
    for row in selections:
        lines.append(
            f"| {row['query_id']} | {row['detected_language']} | {'Qwen3-Embedding-0.6B' if row['selected_model'] == qwen_name else 'E5-base'} |"
        )
    lines += ["", "## 结论", "", f"下一步选择 **{choice}**。{reason}", ""]
    for label, ids in misses.items():
        lines.append(f"- {label} miss：" + "、".join(f"`{i}`" for i in ids) + "。")
    lines += [
        "",
        "当前所有已验证 embedding retrieval strategy 均无法在 Top-5 完整覆盖 `shine-ioc-startup` 的 multi-evidence query。候选并集的唯一 miss 与实际组合的 miss 列表须分别解读。",
        "",
        "以上为固定小样本的描述性结果。11 条负例保留在 JSON 中，但没有校准拒答阈值。索引点数、冻结源码、benchmark、PDF 和 canonical parent 哈希已核对；未修改 Agent，未新增测试、运行 pytest、commit 或 push。完整排名、融合贡献和索引签名见同名 JSON。",
        "",
    ]
    report_path.with_suffix(".md").write_text("\n".join(lines))
    print(
        json.dumps(
            {
                "metrics": {k: v["metrics"] for k, v in evaluations.items()},
                "focus": cross,
                "misses": misses,
                "decision": result["decision"],
                "union": result["candidate_union"]["complete_count"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
finally:
    for client in clients:
        client.close()
