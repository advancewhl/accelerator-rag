from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models


class QdrantCollection:
    """Shared cosine collection configuration and identity-based deletion."""

    def __init__(
        self,
        client: QdrantClient,
        collection_name: str,
        vector_size: int,
    ) -> None:
        if type(vector_size) is not int or vector_size <= 0:
            raise ValueError("vector_size must be a positive integer")
        if not collection_name.strip():
            raise ValueError("collection_name cannot be empty")
        self._client = client
        self._collection_name = collection_name
        self._vector_size = vector_size

    def ensure_collection(self) -> None:
        """Reject named vectors, wrong size or non-cosine distance before use."""
        if self._client.collection_exists(self._collection_name):
            config = self._client.get_collection(
                self._collection_name
            ).config.params.vectors
            if (
                not isinstance(config, models.VectorParams)
                or config.size != self._vector_size
                or config.distance != models.Distance.COSINE
            ):
                raise ValueError("incompatible Qdrant collection vector configuration")
            return
        self._client.create_collection(
            self._collection_name,
            vectors_config=models.VectorParams(
                size=self._vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    @staticmethod
    def _point_id(chunk_id: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"accelerator-rag:{chunk_id}"))

    def point_count(self) -> int:
        self.ensure_collection()
        return self._client.count(self._collection_name, exact=True).count

    def prune_document(self, document_id: str, current_ids: Sequence[str]) -> None:
        """Remove stale points only after a complete replacement has been written."""
        if not document_id.strip():
            raise ValueError("document_id cannot be empty")
        self.ensure_collection()
        self._client.delete(
            self._collection_name,
            wait=True,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ],
                    must_not=[
                        models.HasIdCondition(
                            has_id=[self._point_id(c) for c in current_ids]
                        )
                    ]
                    if current_ids
                    else None,
                )
            ),
        )
