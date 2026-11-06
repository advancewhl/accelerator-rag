"""Passage vectors with self-contained canonical parent reconstruction."""

from dataclasses import MISSING, asdict, dataclass, fields
from threading import Lock
import numpy as np
from qdrant_client import models
from accelerator_rag.domain.knowledge import KnowledgeChunk
from accelerator_rag.retrieval.passages import EmbeddingPassage, PASSAGE_ALGORITHM
from accelerator_rag.retrieval.scope import LEGACY_FAMILY_TAGS, RetrievalScope
from accelerator_rag.storage.qdrant_collection import QdrantCollection
from accelerator_rag.retrieval.index_contract import DenseIndexContract


@dataclass(frozen=True)
class PassageHit:
    score: float
    passage: EmbeddingPassage


def _match_any(key: str, values) -> models.FieldCondition:
    return models.FieldCondition(key=key, match=models.MatchAny(any=sorted(values)))


def _unknown_conditions(key: str) -> list:
    """Match legacy payloads where ``key`` is absent or empty.

    ``IsEmptyCondition`` matches only missing/null fields, not written empty
    strings, so both representations must be listed explicitly.
    """

    return [
        models.IsEmptyCondition(is_empty=models.PayloadField(key=key)),
        models.FieldCondition(key=key, match=models.MatchValue(value="")),
        models.FieldCondition(key=key, match=models.MatchValue(value="unknown")),
    ]


def _usage_condition(scope: RetrievalScope):
    should = [_match_any("usage_status", scope.usage_statuses)]
    if scope.allow_unknown_usage:
        should.extend(_unknown_conditions("usage_status"))
    return models.Filter(should=should)


def _access_condition(scope: RetrievalScope):
    should = [_match_any("access_scope", scope.access_scopes)]
    if scope.allow_unknown_access:
        should.extend(_unknown_conditions("access_scope"))
    return models.Filter(should=should)


def _family_condition(scope: RetrievalScope):
    """Payload ``family_id`` with the same fallback as ``effective_family_id``.

    Legacy payloads have no family field; their logical family is the revision
    ``document_id``.  Match that fallback instead of silently dropping them.
    """

    values = sorted(scope.family_ids)
    missing_family = models.Filter(
        should=[
            models.IsEmptyCondition(is_empty=models.PayloadField(key="family_id")),
            models.FieldCondition(key="family_id", match=models.MatchValue(value="")),
        ]
    )
    should = [
        _match_any("family_id", values),
        models.Filter(must=[missing_family, _match_any("document_id", values)]),
    ]
    # A split family keeps its old name as a ``series:`` tag.  RetrievalScope
    # admits those parents, so the vector prefilter must as well or BM25 and
    # dense see different material.  Text match is a superset (substring);
    # every dense hit is re-checked with ``RetrievalScope.allows``.
    for family_id in values:
        tag = LEGACY_FAMILY_TAGS.get(family_id)
        if tag:
            should.append(
                models.FieldCondition(key="tags", match=models.MatchText(text=tag))
            )
    return models.Filter(should=should)


def _approval_condition(scope: RetrievalScope):
    values = set(scope.approval_statuses)
    should = [_match_any("approval_status", values - {"unknown"})] if (
        values - {"unknown"}
    ) else []
    if "unknown" in values:
        should.extend(_unknown_conditions("approval_status"))
    return models.Filter(should=should)


def _tags_condition(scope: RetrievalScope):
    return models.Filter(
        should=[
            models.FieldCondition(key="tags", match=models.MatchText(text=tag))
            for tag in sorted(scope.tags)
        ]
    )


def build_scope_filter(scope: RetrievalScope | None):
    """Build the Qdrant payload filter for one request-wide scope.

    ``None`` is returned only when the caller passes no scope at all (historical
    direct-retriever compatibility).  Every scope, including the default policy,
    is expressed server-side so ineligible passages are removed before candidate
    limits or max-child aggregation.  Legacy v1 payloads carry no Schema v2
    fields and are admitted by the explicit unknown-field OR branches.
    """

    if scope is None:
        return None
    must = []
    if scope.revision_ids is not None:
        must.append(_match_any("document_id", scope.revision_ids))
    if scope.family_ids is not None:
        must.append(_family_condition(scope))
    if scope.document_kinds is not None:
        must.append(_match_any("document_kind", scope.document_kinds))
    if scope.evidence_roles is not None:
        must.append(_match_any("evidence_role", scope.evidence_roles))
    if scope.topics is not None:
        must.append(_match_any("topic", scope.topics))
    if scope.approval_statuses is not None and scope.approval_statuses:
        must.append(_approval_condition(scope))
    if scope.tags is not None and scope.tags:
        must.append(_tags_condition(scope))
    must.append(_usage_condition(scope))
    must.append(_access_condition(scope))
    return models.Filter(must=must)


class QdrantPassageStore(QdrantCollection):
    def __init__(self, client, collection_name, contract: DenseIndexContract):
        if not isinstance(contract, DenseIndexContract):
            raise TypeError("QdrantPassageStore requires DenseIndexContract")
        if contract.distance != "cosine":
            raise ValueError("this passage store supports cosine distance only")
        super().__init__(client, collection_name, contract.dimension)
        self.contract = contract
        self._read_only = False
        # Embedded Qdrant (local mode) has no ANN index: every query normalizes
        # and scores the whole collection in numpy, which costs minutes on a
        # loaded host.  A frozen runtime index is read once into one contiguous
        # matrix instead, so a query is a single BLAS matvec.
        self._memory_lock = Lock()
        self._memory = None
        # Scope objects are frozen dataclasses; the allowed index only changes
        # when a release is rebuilt, so one scan per distinct scope is enough.
        self._scope_index = {}

    def freeze_read_only(self):
        """Verify once under exclusive local-index ownership, then prohibit writes."""
        self.verify_contract()
        self._read_only = True
        self._memory_index()

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
            values = {}
            for field in fields(KnowledgeChunk):
                if field.name == "chunk_id":
                    values[field.name] = payload["parent_chunk_id"]
                elif field.name == "text":
                    values[field.name] = payload["parent_text"]
                elif field.name in payload:
                    values[field.name] = payload[field.name]
                elif field.default is not MISSING:
                    values[field.name] = field.default
                else:
                    raise KeyError(field.name)
            parent = KnowledgeChunk(**values)
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

    def _memory_index(self):
        """Load the frozen collection once: unit vectors, passages, parents."""

        if self._memory is not None:
            return self._memory
        with self._memory_lock:
            if self._memory is None:
                self._memory = self._build_memory_index()
        return self._memory

    def _build_memory_index(self):
        passages, vectors = [], []
        offset = None
        while True:
            rows, offset = self._client.scroll(
                self._collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            for row in rows:
                passages.append(self.decode(row.payload or {}))
                vectors.append(np.asarray(row.vector, dtype=np.float32))
            if offset is None:
                break
        if not passages:
            raise ValueError("frozen passage index is empty")
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.shape != (len(passages), self._vector_size):
            raise ValueError("passage vector dimension mismatch")
        # Cosine on unit vectors is a plain dot product; normalizing once here
        # keeps every query allocation-free apart from the score vector.
        norms = np.sqrt(np.einsum("ij,ij->i", matrix, matrix))
        norms[norms == 0] = 1.0
        matrix /= norms[:, None]
        return matrix, passages, [p.parent for p in passages]

    def _allowed_positions(self, scope, parents):
        cached = self._scope_index.get(scope)
        if cached is None:
            allowed = [i for i, parent in enumerate(parents) if scope.allows(parent)]
            cached = np.asarray(allowed, dtype=np.int64)
            if len(self._scope_index) >= 8:
                self._scope_index.clear()
            self._scope_index[scope] = cached
        return cached

    def _memory_search(self, vector, limit, scope):
        matrix, passages, parents = self._memory_index()
        query = np.asarray(vector, dtype=np.float32)
        query = query / np.linalg.norm(query)
        scores = matrix @ query
        if scope is None:
            candidates = np.arange(scores.shape[0])
        else:
            candidates = self._allowed_positions(scope, parents)
            if candidates.size == 0:
                return []
        ranked = scores[candidates]
        take = min(limit, ranked.shape[0])
        if take < ranked.shape[0]:
            top = np.argpartition(-ranked, take - 1, kind="introselect")[:take]
        else:
            top = np.arange(ranked.shape[0])
        top = top[np.argsort(-ranked[top], kind="stable")]
        return [
            PassageHit(float(ranked[i]), passages[candidates[i]]) for i in top
        ]

    def search_passages(self, vector, limit, *, scope: RetrievalScope | None = None):
        vector = np.asarray(vector, dtype=np.float32)
        if (
            type(limit) is not int
            or limit <= 0
            or vector.shape != (self._vector_size,)
            or not np.isfinite(vector).all()
            or not np.linalg.norm(vector) > 0
        ):
            raise ValueError("invalid passage search vector/limit")
        self.verify_contract()
        if self._read_only:
            return self._memory_search(vector, limit, scope)
        rows = self._client.query_points(
            self._collection_name,
            query=vector.tolist(),
            limit=limit,
            query_filter=build_scope_filter(scope),
            with_payload=True,
        ).points
        return [
            PassageHit(float(row.score), self.decode(row.payload or {})) for row in rows
        ]

    def count_passages(self, *, scope: RetrievalScope | None = None) -> int:
        """Count eligible passages so candidate limits use the filtered pool."""

        self.ensure_collection()
        return self._client.count(
            self._collection_name,
            count_filter=build_scope_filter(scope),
            exact=True,
        ).count

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
