"""Passage vectors with self-contained canonical parent reconstruction."""

from dataclasses import asdict, dataclass, fields
import numpy as np
from qdrant_client import models
from accelerator_rag.domain.knowledge import KnowledgeChunk
from accelerator_rag.retrieval.passages import EmbeddingPassage, PASSAGE_ALGORITHM
from accelerator_rag.storage.qdrant_collection import QdrantCollection
from accelerator_rag.retrieval.index_contract import DenseIndexContract


@dataclass(frozen=True)
class PassageHit:
    score: float
    passage: EmbeddingPassage


class QdrantPassageStore(QdrantCollection):
    def __init__(self, client, collection_name, contract: DenseIndexContract):
        if not isinstance(contract, DenseIndexContract):
            raise TypeError("QdrantPassageStore requires DenseIndexContract")
        if contract.distance != "cosine":
            raise ValueError("this passage store supports cosine distance only")
        super().__init__(client, collection_name, contract.dimension)
        self.contract = contract
        self._read_only = False

    def freeze_read_only(self):
        """Verify once under exclusive local-index ownership, then prohibit writes."""
        self.verify_contract()
        self._read_only = True

    def verify_contract(self):
        """Full scan: unsigned or mixed collections are rejected before use."""
        if self._read_only:
            return
        super().ensure_collection()
        offset = None
        while True:
            rows, offset = self._client.scroll(
                self._collection_name,
                limit=256,
                offset=offset,
                with_payload=["dense_index_contract_id", "contract_id", "payload_type"],
                with_vectors=False,
            )
            for row in rows:
                p = row.payload or {}
                if (
                    p.get("dense_index_contract_id") != self.contract.contract_id
                    or p.get("contract_id") != self.contract.passage_contract_id
                    or p.get("payload_type") != PASSAGE_ALGORITHM
                ):
                    raise ValueError(
                        "Dense index contract mismatch or unsigned payload; use a new collection or rebuild the full collection"
                    )
            if offset is None:
                return

    def prune_document(self, document_id, current_ids):
        if self._read_only:
            raise ValueError("runtime index is immutable")
        self.verify_contract()
        return super().prune_document(document_id, current_ids)

    def payload(self, p):
        parent = asdict(p.parent)
        parent.pop("chunk_id")
        parent.pop("text")
        return {
            **parent,
            "payload_type": PASSAGE_ALGORITHM,
            "dense_index_contract_id": self.contract.contract_id,
            "dense_index_contract": asdict(self.contract),
            "passage_id": p.passage_id,
            "parent_chunk_id": p.parent_chunk_id,
            "passage_ordinal": p.passage_ordinal,
            "passage_text": p.text,
            "parent_text": p.parent.text,
            "char_start": p.char_start,
            "char_end": p.char_end,
            "token_count": p.token_count,
            "contract_id": p.contract_id,
        }

    @staticmethod
    def decode(payload):
        try:
            if payload.get("payload_type") != PASSAGE_ALGORITHM:
                raise ValueError("unrelated payload owner/type")
            parent = KnowledgeChunk(
                **{
                    f.name: payload["parent_chunk_id"]
                    if f.name == "chunk_id"
                    else payload["parent_text"]
                    if f.name == "text"
                    else payload[f.name]
                    for f in fields(KnowledgeChunk)
                }
            )
            return EmbeddingPassage(
                payload["passage_id"],
                parent,
                payload["passage_ordinal"],
                payload["passage_text"],
                payload["char_start"],
                payload["char_end"],
                payload["token_count"],
                payload["contract_id"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid passage payload: {exc}") from exc

    def upsert_passages(self, passages, vectors):
        if self._read_only:
            raise ValueError("runtime index is immutable")
        array = np.asarray(vectors, dtype=np.float32)
        if (
            not passages
            or array.shape != (len(passages), self._vector_size)
            or not np.isfinite(array).all()
            or np.any(np.linalg.norm(array, axis=1) == 0)
        ):
            raise ValueError(
                "passage vectors must be finite nonzero (count, vector_size)"
            )
        if len({p.passage_id for p in passages}) != len(passages):
            raise ValueError("duplicate passage_id")
        if any(p.contract_id != self.contract.passage_contract_id for p in passages):
            raise ValueError("passage contract differs from DenseIndexContract")
        self.verify_contract()
        self._client.upsert(
            self._collection_name,
            wait=True,
            points=[
                models.PointStruct(
                    id=self._point_id(p.passage_id),
                    vector=v.tolist(),
                    payload=self.payload(p),
                )
                for p, v in zip(passages, array, strict=True)
            ],
        )

    def search_passages(self, vector, limit):
        vector = np.asarray(vector, dtype=np.float32)
        if (
            type(limit) is not int
            or limit <= 0
            or vector.shape != (self._vector_size,)
            or not np.isfinite(vector).all()
            or np.linalg.norm(vector) == 0
        ):
            raise ValueError("invalid passage search vector/limit")
        self.verify_contract()
        rows = self._client.query_points(
            self._collection_name, query=vector.tolist(), limit=limit, with_payload=True
        ).points
        return [
            PassageHit(float(row.score), self.decode(row.payload or {})) for row in rows
        ]

    def all_passages(self):
        self.verify_contract()
        offset = None
        while True:
            rows, offset = self._client.scroll(
                self._collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for row in rows:
                p = self.decode(row.payload or {})
                if str(row.id) != self._point_id(p.passage_id):
                    raise ValueError("passage point ID mismatch")
                yield p
            if offset is None:
                break

    def document_ids(self):
        return {p.parent.document_id for p in self.all_passages()}
