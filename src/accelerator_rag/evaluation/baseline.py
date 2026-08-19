from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from accelerator_rag.retrieval.semantic_search import (
    DocumentChunk,
)


@dataclass(frozen=True)
class EvaluationCase:
    """一个固定的检索评测问题。"""

    id: str
    question: str
    expected_ids: tuple[str, ...]
    category: str
    scored: bool


class RankedResult(Protocol):
    """不同检索器结果共有的最小接口。"""

    chunk: DocumentChunk
    score: float


def load_evaluation_cases(
    path: Path,
) -> list[EvaluationCase]:
    """从 JSON 文件加载固定评测问题。"""

    raw_data = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(raw_data, list):
        raise ValueError(
            "评测文件最外层必须是 JSON 列表"
        )

    cases: list[EvaluationCase] = []

    for item in raw_data:
        if not isinstance(item, dict):
            raise ValueError(
                "每个评测问题必须是 JSON 对象"
            )

        raw_expected_ids = item.get(
            "expected_ids",
            [],
        )

        if not isinstance(raw_expected_ids, list):
            raise ValueError(
                "expected_ids 必须是列表"
            )

        expected_ids = tuple(
            str(expected_id)
            for expected_id in raw_expected_ids
        )

        scored = bool(
            item.get(
                "scored",
                True,
            )
        )

        if scored and not expected_ids:
            raise ValueError(
                "计分问题必须至少有一个 expected_id"
            )

        case = EvaluationCase(
            id=str(item["id"]),
            question=str(item["question"]),
            expected_ids=expected_ids,
            category=str(item["category"]),
            scored=scored,
        )

        if not case.id.strip():
            raise ValueError(
                "评测问题 id 不能为空"
            )

        if not case.question.strip():
            raise ValueError(
                "评测问题 question 不能为空"
            )

        cases.append(case)

    if not cases:
        raise ValueError(
            "评测文件中没有问题"
        )

    return cases

def validate_evaluation_cases(
    cases: Sequence[EvaluationCase],
    chunks: Sequence[DocumentChunk],
) -> None:
    """检查评测数据和语料之间的一致性。"""

    chunk_ids = {
        chunk.id
        for chunk in chunks
    }

    if len(chunk_ids) != len(chunks):
        raise ValueError(
            "语料中存在重复 chunk id"
        )

    seen_case_ids: set[str] = set()

    for case in cases:
        if case.id in seen_case_ids:
            raise ValueError(
                f"评测问题 id 重复：{case.id}"
            )

        seen_case_ids.add(case.id)

        missing_ids = (
            set(case.expected_ids)
            - chunk_ids
        )

        if missing_ids:
            missing_text = ", ".join(
                sorted(missing_ids)
            )

            raise ValueError(
                f"评测问题 {case.id} "
                "引用了不存在的 Ground Truth："
                f"{missing_text}"
            )


def find_best_rank(
    results: Sequence[RankedResult],
    expected_ids: Sequence[str],
) -> int | None:
    """返回任意正确文本块在检索结果中的最高排名。"""

    expected_id_set = set(expected_ids)

    for rank, result in enumerate(
        results,
        start=1,
    ):
        if result.chunk.id in expected_id_set:
            return rank

    return None


def describe_rank(
    rank: int | None,
) -> str:
    """把排名转换成人类可读字符串。"""

    if rank is None:
        return "未命中"

    return f"第 {rank} 名"


def decide_winner(
    dense_rank: int | None,
    bm25_rank: int | None,
) -> str:
    """根据正确证据排名判断本题哪个检索器更优。"""

    if dense_rank is None and bm25_rank is None:
        return "双方均未命中"

    if dense_rank is None:
        return "BM25"

    if bm25_rank is None:
        return "Dense"

    if dense_rank < bm25_rank:
        return "Dense"

    if bm25_rank < dense_rank:
        return "BM25"

    return "并列"