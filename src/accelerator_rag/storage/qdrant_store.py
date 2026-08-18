from __future__ import annotations

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import numpy as np
from numpy.typing import NDArray
from qdrant_client import QdrantClient, models

from accelerator_rag.retrieval.semantic_search import (
    DocumentChunk,
    SearchResult,
)


FloatArray = NDArray[np.float32]


class QdrantVectorStore:
    """负责 DocumentChunk 与 Qdrant 之间的持久化和向量查询。"""

    def __init__(
        self,
        client: QdrantClient,
        collection_name: str,
        vector_size: int,
        distance: models.Distance = models.Distance.COSINE,
    ) -> None:
        if vector_size <= 0:
            raise ValueError("vector_size 必须大于 0")

        if not collection_name.strip():
            raise ValueError("collection_name 不能为空")

        self._client = client
        self._collection_name = collection_name
        self._vector_size = vector_size
        self._distance = distance

    def ensure_collection(self) -> None:
        """确保目标 Collection 存在。"""

        if self._client.collection_exists(
            self._collection_name
        ):
            return

        self._client.create_collection(
            collection_name=self._collection_name,
            vectors_config=models.VectorParams(
                size=self._vector_size,
                distance=self._distance,
            ),
        )

    def upsert_chunks(
        self,
        chunks: Sequence[DocumentChunk],
        vectors: FloatArray,
    ) -> None:
        """把文本块及其向量写入 Qdrant。"""

        if not chunks:
            raise ValueError("chunks 不能为空")

        vectors = np.asarray(
            vectors,
            dtype=np.float32,
        )

        if vectors.ndim != 2:
            raise ValueError(
                "vectors 必须是二维矩阵"
            )

        if len(chunks) != vectors.shape[0]:
            raise ValueError(
                "chunks 数量必须与 vectors 行数一致"
            )

        if vectors.shape[1] != self._vector_size:
            raise ValueError(
                "vector 维数与 Collection 配置不一致"
            )

        points: list[models.PointStruct] = []

        for chunk, vector in zip(
            chunks,
            vectors,
            strict=True,
        ):
            points.append(
                models.PointStruct(
                    id=self._point_id(chunk.id),
                    vector=vector.tolist(),
                    payload={
                        "chunk_id": chunk.id,
                        "title": chunk.title,
                        "text": chunk.text,
                        "metadata": chunk.metadata,
                    },
                )
            )

        self._client.upsert(
            collection_name=self._collection_name,
            points=points,
            wait=True,
        )

    def search(
        self,
        query_vector: FloatArray,
        top_k: int = 3,
    ) -> list[SearchResult]:
        """使用一个查询向量搜索最相关的文本块。"""

        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        query_vector = np.asarray(
            query_vector,
            dtype=np.float32,
        )

        if query_vector.ndim != 1:
            raise ValueError(
                "query_vector 必须是一维向量"
            )

        if query_vector.shape[0] != self._vector_size:
            raise ValueError(
                "query_vector 维数与 Collection 配置不一致"
            )

        response = self._client.query_points(
            collection_name=self._collection_name,
            query=query_vector.tolist(),
            limit=top_k,
            with_payload=True,
        )

        results: list[SearchResult] = []

        for rank, point in enumerate(
            response.points,
            start=1,
        ):
            payload = point.payload

            if payload is None:
                raise RuntimeError(
                    "Qdrant Point 缺少 payload"
                )

            chunk_id = payload.get("chunk_id")
            title = payload.get("title")
            text = payload.get("text")
            metadata = payload.get(
                "metadata",
                {},
            )

            if not isinstance(chunk_id, str):
                raise RuntimeError(
                    "payload.chunk_id 无效"
                )

            if not isinstance(title, str):
                raise RuntimeError(
                    "payload.title 无效"
                )

            if not isinstance(text, str):
                raise RuntimeError(
                    "payload.text 无效"
                )

            if not isinstance(metadata, dict):
                raise RuntimeError(
                    "payload.metadata 无效"
                )

            normalized_metadata = {
                str(key): str(value)
                for key, value in metadata.items()
            }

            chunk = DocumentChunk(
                id=chunk_id,
                title=title,
                text=text,
                metadata=normalized_metadata,
            )

            results.append(
                SearchResult(
                    rank=rank,
                    score=float(point.score),
                    chunk=chunk,
                )
            )

        return results

    def delete_chunks(
        self,
        chunk_ids: Sequence[str],
    ) -> None:
        """根据业务 chunk_id 删除 Qdrant Points。"""

        if not chunk_ids:
            return

        point_ids = [
            self._point_id(chunk_id)
            for chunk_id in chunk_ids
        ]

        self._client.delete(
            collection_name=self._collection_name,
            points_selector=models.PointIdsList(
                points=point_ids,
            ),
            wait=True,
        )

    @staticmethod
    def _point_id(chunk_id: str) -> str:
        """把业务 chunk_id 稳定映射成 Qdrant UUID。"""

        return str(
            uuid5(
                NAMESPACE_URL,
                f"accelerator-rag:{chunk_id}",
            )
        )