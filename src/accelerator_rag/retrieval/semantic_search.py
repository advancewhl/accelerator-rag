from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from numpy.typing import NDArray


FloatArray = NDArray[np.float32]


class TextEmbedder(Protocol):
    """检索器所需要的 Embedding 接口。"""

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> FloatArray:
        ...

    def embed_query(
        self,
        text: str,
    ) -> FloatArray:
        ...


@dataclass(frozen=True)
class DocumentChunk:
    """知识库中的一个文本块。"""

    id: str
    title: str
    text: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class SearchResult:
    """一次检索返回的单条结果。"""

    rank: int
    score: float
    chunk: DocumentChunk


def load_chunks(
    path: Path,
) -> list[DocumentChunk]:
    """从 JSON 文件读取文本块。"""

    raw_data = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(raw_data, list):
        raise ValueError("语料文件最外层必须是 JSON 列表")

    chunks: list[DocumentChunk] = []

    for item in raw_data:
        if not isinstance(item, dict):
            raise ValueError("每个文本块必须是 JSON 对象")

        chunk = DocumentChunk(
            id=str(item["id"]),
            title=str(item["title"]),
            text=str(item["text"]),
            metadata={
                str(key): str(value)
                for key, value in item.get(
                    "metadata",
                    {},
                ).items()
            },
        )

        chunks.append(chunk)

    if not chunks:
        raise ValueError("语料文件中没有文本块")

    return chunks


class InMemorySemanticRetriever:
    """使用 NumPy 矩阵保存向量的最小语义检索器。"""

    def __init__(
        self,
        chunks: Sequence[DocumentChunk],
        embedder: TextEmbedder,
    ) -> None:
        if not chunks:
            raise ValueError("文本块列表不能为空")

        self._chunks = list(chunks)
        self._embedder = embedder

        document_texts = [
            f"{chunk.title}\n{chunk.text}"
            for chunk in self._chunks
        ]

        self._document_embeddings = (
            self._embedder.embed_documents(
                document_texts
            )
        )

        self._validate_document_embeddings()

    def _validate_document_embeddings(self) -> None:
        if self._document_embeddings.ndim != 2:
            raise ValueError(
                "文档向量必须是二维矩阵"
            )

        document_count = (
            self._document_embeddings.shape[0]
        )

        if document_count != len(self._chunks):
            raise ValueError(
                "文档数量与向量数量不一致"
            )

    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[SearchResult]:
        """检索与问题最相似的 Top-K 文本块。"""

        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        query_embedding = (
            self._embedder.embed_query(query)
        )

        if query_embedding.ndim != 1:
            raise ValueError(
                "查询向量必须是一维向量"
            )

        document_dimension = (
            self._document_embeddings.shape[1]
        )

        if query_embedding.shape[0] != document_dimension:
            raise ValueError(
                "查询向量与文档向量维度不一致"
            )

        scores = (
            self._document_embeddings
            @ query_embedding
        )

        result_count = min(
            top_k,
            len(self._chunks),
        )

        ranked_indices = (
            np.argsort(scores)[::-1][:result_count]
        )

        results: list[SearchResult] = []

        for rank, index in enumerate(
            ranked_indices,
            start=1,
        ):
            result = SearchResult(
                rank=rank,
                score=float(scores[index]),
                chunk=self._chunks[index],
            )

            results.append(result)

        return results