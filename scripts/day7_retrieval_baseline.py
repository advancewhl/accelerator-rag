from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from qdrant_client import QdrantClient

from accelerator_rag.config import load_settings
from accelerator_rag.embedding import BgeSmallZhEmbedder
from accelerator_rag.evaluation.baseline import (
    EvaluationCase,
    RankedResult,
    decide_winner,
    validate_evaluation_cases,
    describe_rank,
    find_best_rank,
    load_evaluation_cases,
)
from accelerator_rag.retrieval.bm25_baseline import (
    BM25BaselineRetriever,
)
from accelerator_rag.retrieval.qdrant_semantic_search import (
    QdrantSemanticRetriever,
)
from accelerator_rag.retrieval.semantic_search import (
    DocumentChunk,
    load_chunks,
)
from accelerator_rag.storage import QdrantVectorStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CORPUS_PATH = (
    PROJECT_ROOT
    / "data"
    / "day4_chunks.json"
)

EVALUATION_PATH = (
    PROJECT_ROOT
    / "data"
    / "evaluation"
    / "day7_questions.json"
)

CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "settings.json"
)

REPORT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "day7_baseline.md"
)

TOP_K = 3


def format_results(
    results: Sequence[RankedResult],
) -> list[str]:
    """把 Top-K 检索结果转换成 Markdown。"""

    if not results:
        return ["- 无结果"]

    lines: list[str] = []

    for rank, result in enumerate(
        results,
        start=1,
    ):
        lines.append(
            f"- {rank}. `{result.chunk.id}` "
            f"score={result.score:.4f} "
            f"— {result.chunk.title}"
        )

    return lines


def evaluate_case(
    case: EvaluationCase,
    dense_retriever: QdrantSemanticRetriever,
    bm25_retriever: BM25BaselineRetriever,
) -> tuple[list[str], int | None, int | None]:
    """执行一个问题并生成对应的 Markdown 内容。"""

    dense_results = dense_retriever.search(
        query=case.question,
        top_k=TOP_K,
    )

    bm25_results = bm25_retriever.search(
        query=case.question,
        top_k=TOP_K,
    )

    lines = [
        f"## {case.id} [{case.category}]",
        "",
        f"**Question:** {case.question}",
        "",
    ]

    if not case.scored:
        lines.extend(
            [
                "**Ground truth:** 不计分，"
                "用于语料覆盖诊断。",
                "",
                "### Dense Top-K",
                "",
                *format_results(dense_results),
                "",
                "### BM25 Top-K",
                "",
                *format_results(bm25_results),
                "",
                "**Evaluation:** "
                "该问题没有标注 Ground Truth，"
                "不用于检索器排名统计。",
                "",
            ]
        )

        return lines, None, None

    dense_rank = find_best_rank(
        results=dense_results,
        expected_ids=case.expected_ids,
    )

    bm25_rank = find_best_rank(
        results=bm25_results,
        expected_ids=case.expected_ids,
    )

    winner = decide_winner(
        dense_rank=dense_rank,
        bm25_rank=bm25_rank,
    )

    expected_text = ", ".join(
        f"`{expected_id}`"
        for expected_id in case.expected_ids
    )

    lines.extend(
        [
            f"**Ground truth:** {expected_text}",
            "",
            "### Dense Top-K",
            "",
            *format_results(dense_results),
            "",
            "### BM25 Top-K",
            "",
            *format_results(bm25_results),
            "",
            "**Evaluation:** "
            f"Dense {describe_rank(dense_rank)}；"
            f"BM25 {describe_rank(bm25_rank)}；"
            f"本题排名结果：{winner}",
            "",
        ]
    )

    return lines, dense_rank, bm25_rank


def build_report(
    cases: Sequence[EvaluationCase],
    chunks: Sequence[DocumentChunk],
    dense_retriever: QdrantSemanticRetriever,
    bm25_retriever: BM25BaselineRetriever,
) -> str:
    """运行全部问题并生成 Day7 Markdown 报告。"""

    lines = [
        "# Day 7 Retrieval Baseline",
        "",
        "## Experiment Setup",
        "",
        f"- Corpus chunks: {len(chunks)}",
        f"- Evaluation cases: {len(cases)}",
        f"- Top-K: {TOP_K}",
        "- Dense retriever: "
        "BGE-small-zh-v1.5 + Qdrant cosine search",
        "- Sparse retriever: BM25 baseline",
        "",
        "# Case Results",
        "",
    ]

    scored_count = 0

    dense_top1 = 0
    dense_top3 = 0

    bm25_top1 = 0
    bm25_top3 = 0

    winner_counts = {
        "Dense": 0,
        "BM25": 0,
        "并列": 0,
        "双方均未命中": 0,
    }

    for case in cases:
        case_lines, dense_rank, bm25_rank = (
            evaluate_case(
                case=case,
                dense_retriever=dense_retriever,
                bm25_retriever=bm25_retriever,
            )
        )

        lines.extend(case_lines)

        if not case.scored:
            continue

        scored_count += 1

        dense_top1 += dense_rank == 1
        dense_top3 += dense_rank is not None

        bm25_top1 += bm25_rank == 1
        bm25_top3 += bm25_rank is not None

        winner = decide_winner(
            dense_rank=dense_rank,
            bm25_rank=bm25_rank,
        )

        winner_counts[winner] += 1

    lines.extend(
        [
            "# Summary",
            "",
            f"- Scored cases: {scored_count}",
            (
                "- Dense: "
                f"Top-1 {dense_top1}/{scored_count}, "
                f"Top-{TOP_K} {dense_top3}/{scored_count}"
            ),
            (
                "- BM25: "
                f"Top-1 {bm25_top1}/{scored_count}, "
                f"Top-{TOP_K} {bm25_top3}/{scored_count}"
            ),
            (
                "- Per-case ranking: "
                f"Dense {winner_counts['Dense']}, "
                f"BM25 {winner_counts['BM25']}, "
                f"tie {winner_counts['并列']}, "
                "both missed "
                f"{winner_counts['双方均未命中']}"
            ),
            "",
            "Dense 与 BM25 的 score 不在同一尺度，"
            "不能直接比较绝对分数。",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    settings = load_settings(CONFIG_PATH)

    print("读取 Day4 corpus...")
    chunks = load_chunks(CORPUS_PATH)

    print("读取 Day7 evaluation set...")
    cases = load_evaluation_cases(
        EVALUATION_PATH
    )
    validate_evaluation_cases(
    cases=cases,
    chunks=chunks,
    )

    print(
        f"Corpus: {len(chunks)} chunks; "
        f"Evaluation: {len(cases)} cases"
    )

    print("加载 BGE Embedding 模型...")
    embedder = BgeSmallZhEmbedder(
        device="cpu"
    )

    probe_vector = embedder.embed_query(
        "Day7 vector dimension probe"
    )

    vector_size = int(
        probe_vector.shape[0]
    )

    client = QdrantClient(
        url=settings.qdrant_url
    )

    collection_name = (
        f"{settings.collection_name}"
        "_day7_baseline"
    )

    try:
        if client.collection_exists(
            collection_name
        ):
            print(
                "删除已有 Day7 baseline "
                "collection..."
            )

            client.delete_collection(
                collection_name
            )

        store = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            vector_size=vector_size,
        )

        dense_retriever = (
            QdrantSemanticRetriever(
                embedder=embedder,
                vector_store=store,
            )
        )

        bm25_retriever = (
            BM25BaselineRetriever(
                chunks=chunks
            )
        )

        print("写入 Qdrant...")
        dense_retriever.index_chunks(
            chunks
        )

        print("运行 20 题 baseline...")
        report = build_report(
            cases=cases,
            chunks=chunks,
            dense_retriever=dense_retriever,
            bm25_retriever=bm25_retriever,
        )

        REPORT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        REPORT_PATH.write_text(
            report,
            encoding="utf-8",
        )

        print(
            "报告已生成："
            f"{REPORT_PATH}"
        )

    finally:
        client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())