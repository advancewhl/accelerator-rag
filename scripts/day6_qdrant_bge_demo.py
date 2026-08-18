from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient

from accelerator_rag.config import (
    load_settings,
)
from accelerator_rag.embedding import (
    BgeSmallZhEmbedder,
)
from accelerator_rag.retrieval.qdrant_semantic_search import (
    QdrantSemanticRetriever,
)
from accelerator_rag.retrieval.semantic_search import (
    DocumentChunk,
)
from accelerator_rag.storage import (
    QdrantVectorStore,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH = PROJECT_ROOT / "config" / "settings.json"


def build_demo_chunks() -> list[DocumentChunk]:
    """构造 Day 6 小规模测试语料。"""

    return [
        DocumentChunk(
            id="epics-demo",
            title="EPICS",
            text=("EPICS 示例资料，包含 " "IOC、OPI、PV 等术语。"),
            metadata={
                "system": "EPICS",
            },
        ),
        DocumentChunk(
            id="bpm-demo",
            title="BPM",
            text=("BPM 示例资料，" "属于束测相关主题。"),
            metadata={
                "system": "Beam Diagnostics",
            },
        ),
        DocumentChunk(
            id="mba-demo",
            title="MBA",
            text=("MBA 示例资料，" "属于光源物理相关主题。"),
            metadata={
                "system": "Accelerator Physics",
            },
        ),
    ]


def main() -> None:
    settings = load_settings(CONFIG_PATH)

    embedder = BgeSmallZhEmbedder()

    # 用真实模型自动确认向量维数。
    probe_vector = embedder.embed_query("向量维数检查")

    vector_size = int(probe_vector.shape[0])

    print(f"Embedding vector size: " f"{vector_size}")

    client = QdrantClient(url=settings.qdrant_url)

    collection_name = f"{settings.collection_name}_day6_demo"

    try:
        store = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            vector_size=vector_size,
        )

        retriever = QdrantSemanticRetriever(
            embedder=embedder,
            vector_store=store,
        )

        chunks = build_demo_chunks()

        retriever.index_chunks(chunks)

        queries = [
            "EPICS IOC PV",
            "束测 BPM",
            "MBA 光源物理",
        ]

        for query in queries:
            print(f"\nQuery: {query}")

            results = retriever.search(
                query=query,
                top_k=3,
            )

            for result in results:
                print(
                    f"{result.rank}. "
                    f"{result.chunk.title} "
                    f"score={result.score:.4f}"
                )

                print(f"   " f"{result.chunk.text}")

                print(f"   metadata=" f"{result.chunk.metadata}")

    finally:
        client.close()


if __name__ == "__main__":
    main()
