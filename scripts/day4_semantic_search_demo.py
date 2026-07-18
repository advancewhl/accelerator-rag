from __future__ import annotations

from pathlib import Path

from accelerator_rag.embedding import (
    BgeSmallZhEmbedder,
)
from accelerator_rag.retrieval.semantic_search import (
    InMemorySemanticRetriever,
    SearchResult,
    load_chunks,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CORPUS_PATH = PROJECT_ROOT / "data" / "day4_chunks.json"


EVALUATION_CASES = [
    (
        "EPICS 中的 PV 是什么？",
        "epics-pv",
    ),
    (
        "IOC 的主要职责是什么？",
        "epics-ioc",
    ),
    (
        "运行人员通过什么图形界面查看设备状态？",
        "epics-opi",
    ),
    (
        "EPICS 客户端通过什么协议访问过程变量？",
        "epics-ca",
    ),
    (
        "caget 和 caput 分别有什么作用？",
        "epics-cli",
    ),
    (
        "什么设备可以测量束流的横向位置？",
        "bpm-position",
    ),
    (
        "多个 BPM 的测量结果怎样形成束流轨道？",
        "bpm-orbit",
    ),
    (
        "MBA 晶格为什么能够降低电子束发射度？",
        "mba-emittance",
    ),
    (
        "高层应用可以完成哪些加速器任务？",
        "hla-role",
    ),
    (
        "这个 RAG 系统能不能自动执行调束命令？",
        "rag-boundary",
    ),
]


def print_result(
    result: SearchResult,
) -> None:
    print(f"{result.rank}. " f"score={result.score:.4f} " f"id={result.chunk.id}")
    print(f"   标题：{result.chunk.title}")
    print(f"   正文：{result.chunk.text}")
    print(f"   元数据：{result.chunk.metadata}")


def main() -> int:
    print("正在读取演示语料……")
    chunks = load_chunks(CORPUS_PATH)

    print(f"共读取 {len(chunks)} 个文本块")

    print("正在加载 Embedding 模型……")
    embedder = BgeSmallZhEmbedder(device="cpu")

    print("正在计算文档向量……")
    retriever = InMemorySemanticRetriever(
        chunks=chunks,
        embedder=embedder,
    )

    hit_count = 0

    for number, (
        question,
        expected_id,
    ) in enumerate(
        EVALUATION_CASES,
        start=1,
    ):
        print()
        print("=" * 70)
        print(f"问题 {number}：{question}")
        print(f"期望文本块：{expected_id}")

        results = retriever.search(
            query=question,
            top_k=3,
        )

        for result in results:
            print_result(result)

        is_hit = any(result.chunk.id == expected_id for result in results)

        if is_hit:
            hit_count += 1
            print("验收结果：Top-3 命中")
        else:
            print("验收结果：Top-3 未命中")

    print()
    print("=" * 70)
    print("最终 Top-3 命中：" f"{hit_count}/{len(EVALUATION_CASES)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
