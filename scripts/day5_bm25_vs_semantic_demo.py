from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from accelerator_rag.embedding import BgeSmallZhEmbedder
from accelerator_rag.retrieval.bm25_baseline import BM25BaselineRetriever
from accelerator_rag.retrieval.semantic_search import (
    DocumentChunk,
    InMemorySemanticRetriever,
    load_chunks,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = PROJECT_ROOT / "data" / "day4_chunks.json"
TOP_K = 3


@dataclass(frozen=True)
class ComparisonCase:
    """一个可评分问题或语料覆盖诊断问题。"""

    question: str
    expected_id: str | None
    category: str


COMPARISON_CASES = [
    ComparisonCase(
        question="PV 是什么？",
        expected_id="epics-pv",
        category="缩写与原词",
    ),
    ComparisonCase(
        question="什么叫过程变量？",
        expected_id="epics-pv",
        category="中文同义表达",
    ),
    ComparisonCase(
        question="BPM 是什么？",
        expected_id="bpm-position",
        category="技术缩写",
    ),
    ComparisonCase(
        question="哪个设备用来测量束流位置？",
        expected_id="bpm-position",
        category="自然语言改写",
    ),
    ComparisonCase(
        question="SR:BPM01:X",
        expected_id=None,
        category="语料覆盖诊断",
    ),
    ComparisonCase(
        question="IOC 有什么作用？",
        expected_id="epics-ioc",
        category="自然语言改写",
    ),
    ComparisonCase(
        question="操作员使用什么界面控制系统？",
        expected_id="epics-opi",
        category="自然语言改写",
    ),
    ComparisonCase(
        question="什么装置可以监视粒子束在管道中的横向位置？",
        expected_id="bpm-position",
        category="长语义改写",
    ),
    ComparisonCase(
        question="camonitor",
        expected_id="epics-ca",
        category="精确技术词",
    ),
    ComparisonCase(
        question="Process Variable",
        expected_id="epics-pv",
        category="精确英文术语",
    ),
]


class RankedResult(Protocol):
    """两个检索器结果共有的最小输出接口。"""

    chunk: DocumentChunk
    score: float


def print_results(
    label: str,
    results: Sequence[RankedResult],
) -> None:
    print(f"{label}:")

    if not results:
        print("  无正分结果")
        return

    for rank, result in enumerate(results, start=1):
        print(
            f"  {rank}. score={result.score:.4f} "
            f"id={result.chunk.id} title={result.chunk.title}"
        )


def find_rank(
    results: Sequence[RankedResult],
    expected_id: str,
) -> int | None:
    for rank, result in enumerate(results, start=1):
        if result.chunk.id == expected_id:
            return rank

    return None


def corpus_contains_literal(
    chunks: Sequence[DocumentChunk],
    literal: str,
) -> bool:
    normalized_literal = literal.casefold()

    return any(
        normalized_literal
        in f"{chunk.title}\n{chunk.text}".casefold()
        for chunk in chunks
    )


def describe_rank(rank: int | None) -> str:
    if rank is None:
        return "未命中"

    return f"第 {rank} 名"


def decide_winner(
    semantic_rank: int | None,
    bm25_rank: int | None,
) -> str:
    if semantic_rank is None and bm25_rank is None:
        return "双方均未命中"
    if semantic_rank is None:
        return "BM25"
    if bm25_rank is None:
        return "Semantic"
    if semantic_rank < bm25_rank:
        return "Semantic"
    if bm25_rank < semantic_rank:
        return "BM25"

    return "并列"


def print_summary(
    scored_case_count: int,
    semantic_top1: int,
    semantic_top3: int,
    bm25_top1: int,
    bm25_top3: int,
    winner_counts: dict[str, int],
    diagnostic_case_count: int,
) -> None:
    print()
    print("=" * 78)
    print("汇总（只统计具有 expected_id 的问题）")
    print(f"可评分问题：{scored_case_count}")
    print(
        "Semantic："
        f"Top-1 {semantic_top1}/{scored_case_count}，"
        f"Top-3 {semantic_top3}/{scored_case_count}"
    )
    print(
        "BM25："
        f"Top-1 {bm25_top1}/{scored_case_count}，"
        f"Top-3 {bm25_top3}/{scored_case_count}"
    )
    print(
        "逐题排名胜负："
        f"Semantic {winner_counts['Semantic']}，"
        f"BM25 {winner_counts['BM25']}，"
        f"并列 {winner_counts['并列']}，"
        f"双方均未命中 {winner_counts['双方均未命中']}"
    )
    print(f"不计分的语料覆盖诊断：{diagnostic_case_count}")
    print("注意：Semantic 与 BM25 的 score 尺度不同，不能直接比较绝对值。")


def main() -> int:
    print("正在读取 Day 4 演示语料……")
    chunks = load_chunks(CORPUS_PATH)
    print(f"共读取 {len(chunks)} 个文本块：{CORPUS_PATH}")

    print("正在加载 Embedding 模型……")
    embedder = BgeSmallZhEmbedder(device="cpu")

    print("正在建立 Semantic 和 BM25 检索器……")
    semantic_retriever = InMemorySemanticRetriever(
        chunks=chunks,
        embedder=embedder,
    )
    bm25_retriever = BM25BaselineRetriever(
        chunks=chunks,
    )

    semantic_top1 = 0
    semantic_top3 = 0
    bm25_top1 = 0
    bm25_top3 = 0
    scored_case_count = 0
    diagnostic_case_count = 0
    winner_counts = {
        "Semantic": 0,
        "BM25": 0,
        "并列": 0,
        "双方均未命中": 0,
    }

    for number, case in enumerate(COMPARISON_CASES, start=1):
        semantic_results = semantic_retriever.search(
            query=case.question,
            top_k=TOP_K,
        )
        bm25_results = bm25_retriever.search(
            query=case.question,
            top_k=TOP_K,
        )

        print()
        print("=" * 78)
        print(f"问题 {number} [{case.category}]：{case.question}")
        print_results("Semantic", semantic_results)
        print_results("BM25", bm25_results)

        if case.expected_id is None:
            diagnostic_case_count += 1
            is_present = corpus_contains_literal(
                chunks=chunks,
                literal=case.question,
            )
            print("评估：不计分（没有指定 expected_id）")
            print(
                "查询原文是否存在于 Day 4 标题或正文："
                f"{'是' if is_present else '否'}"
            )
            if not is_present:
                print("结论：这是语料覆盖问题，不能据此判断检索算法胜负。")
            continue

        scored_case_count += 1
        semantic_rank = find_rank(
            semantic_results,
            case.expected_id,
        )
        bm25_rank = find_rank(
            bm25_results,
            case.expected_id,
        )

        semantic_top1 += semantic_rank == 1
        semantic_top3 += semantic_rank is not None
        bm25_top1 += bm25_rank == 1
        bm25_top3 += bm25_rank is not None

        winner = decide_winner(
            semantic_rank=semantic_rank,
            bm25_rank=bm25_rank,
        )
        winner_counts[winner] += 1

        print(f"期望文本块：{case.expected_id}")
        print(
            "评估："
            f"Semantic {describe_rank(semantic_rank)}；"
            f"BM25 {describe_rank(bm25_rank)}；"
            f"本题排名胜者：{winner}"
        )

    print_summary(
        scored_case_count=scored_case_count,
        semantic_top1=semantic_top1,
        semantic_top3=semantic_top3,
        bm25_top1=bm25_top1,
        bm25_top3=bm25_top3,
        winner_counts=winner_counts,
        diagnostic_case_count=diagnostic_case_count,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
