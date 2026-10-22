from collections.abc import Sequence
from dataclasses import asdict
import numpy as np
from qdrant_client import models
from accelerator_rag.domain.knowledge import KnowledgeChunk, RetrievalResult
from accelerator_rag.embedding import FloatArray
from accelerator_rag.storage.qdrant_collection import QdrantCollection


class QdrantVectorStore(QdrantCollection):
    """Canonical KnowledgeChunk payload writes and cosine retrieval."""

    def _validate_vectors(
        self,
        chunks: Sequence[KnowledgeChunk],
        vectors: FloatArray,
    ) -> FloatArray:
        array = np.asarray(vectors, dtype=np.float32)
        if array.ndim != 2 or array.shape != (len(chunks), self._vector_size):
            raise ValueError("vectors must have shape (chunk count, vector_size)")
        if not np.isfinite(array).all() or np.any(np.linalg.norm(array, axis=1) == 0):
            raise ValueError("vectors must be finite and nonzero for cosine search")
        if len({c.chunk_id for c in chunks}) != len(chunks):
            raise ValueError("duplicate chunk_id in batch")
        return array

    def upsert_chunks(
        self,
        chunks: Sequence[KnowledgeChunk],
        vectors: FloatArray,
    ) -> None:
        if not chunks:
            raise ValueError("chunks cannot be empty")
        vectors = self._validate_vectors(chunks, vectors)
        self.ensure_collection()
        self._client.upsert(
            self._collection_name,
            wait=True,
            points=[
                models.PointStruct(
                    id=self._point_id(c.chunk_id),
                    vector=v.tolist(),
                    payload=asdict(c),
                )
                for c, v in zip(chunks, vectors, strict=True)
            ],
        )

    def replace_document(
        self,
        document_id: str,
        chunks: Sequence[KnowledgeChunk],
        vectors: FloatArray,
    ) -> None:
        """Upsert new evidence then delete stale IDs for this document only.

        Not transactional: interrupted writes can leave old and new chunks until
        retry. Empty chunks explicitly clear the document. Validate before mutation.
        """
        if not document_id.strip() or any(c.document_id != document_id for c in chunks):
            raise ValueError("all chunks must belong to the specified document_id")
        self._validate_vectors(chunks, vectors)
        self.ensure_collection()
        if chunks:
            self.upsert_chunks(chunks, vectors)
        self.prune_document(document_id, [c.chunk_id for c in chunks])

    def search(
        self,
        query_vector: FloatArray,
        top_k: int = 3,
    ) -> list[RetrievalResult]:
        if type(top_k) is not int or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        vector = np.asarray(query_vector, dtype=np.float32)
        if vector.shape != (self._vector_size,):
            raise ValueError("query_vector dimension must match vector_size")
        if not np.isfinite(vector).all() or np.linalg.norm(vector) == 0:
            raise ValueError("query_vector must be finite and nonzero")
        self.ensure_collection()
        response = self._client.query_points(
            self._collection_name,
            query=vector.tolist(),
            limit=top_k,
            with_payload=True,
        )
        results = []
        for rank, point in enumerate(response.points, start=1):
            try:
                chunk = KnowledgeChunk(**(point.payload or {}))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"invalid KnowledgeChunk payload at {point.id}: {exc}"
                ) from exc
            results.append(RetrievalResult(rank, float(point.score), chunk, "qdrant"))
        return results

    def delete_chunks(self, chunk_ids: Sequence[str]) -> None:
        if chunk_ids:
            self.ensure_collection()
            self._client.delete(
                self._collection_name,
                wait=True,
                points_selector=models.PointIdsList(
                    points=[self._point_id(c) for c in chunk_ids],
                ),
            )

    def document_ids(self) -> set[str]:
        """Inspect provenance before reusing a dedicated corpus collection."""
        self.ensure_collection()
        result = set()
        offset = None
        while True:
            points, offset = self._client.scroll(
                self._collection_name,
                limit=256,
                offset=offset,
                with_payload=["document_id"],
                with_vectors=False,
            )
            for point in points:
                document_id = (point.payload or {}).get("document_id")
                if not isinstance(document_id, str):
                    raise ValueError(
                        "existing collection contains points without document identity"
                    )
                result.add(document_id)
            if offset is None:
                return result
