from collections.abc import Sequence
from time import perf_counter

import numpy as np

from accelerator_rag.domain.knowledge import KnowledgeChunk, RetrievalResult
from accelerator_rag.embedding import TextEmbedder, document_embedding_text
from accelerator_rag.storage import QdrantVectorStore


class DirectChunkDenseRetriever:
    """Historical direct-chunk comparator. Stage 2.6 uses DenseRetriever below."""

    def __init__(self, embedder: TextEmbedder, vector_store: QdrantVectorStore) -> None:
        self._embedder = embedder
        self._vector_store = vector_store

    def index_document(
        self,
        document_id: str,
        chunks: Sequence[KnowledgeChunk],
    ) -> None:
        if not chunks:
            raise ValueError("cannot index a document without text chunks")
        if any(c.document_id != document_id for c in chunks):
            raise ValueError("chunks do not belong to document_id")
        self._vector_store.ensure_collection()
        vectors = self._embedder.embed_documents(
            [document_embedding_text(c) for c in chunks]
        )
        self._vector_store.replace_document(document_id, chunks, vectors)

    def search(self, query: str, top_k: int = 3) -> list[RetrievalResult]:
        if not query.strip():
            raise ValueError("query cannot be empty")
        if type(top_k) is not int or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        return self._vector_store.search(
            np.asarray(self._embedder.embed_query(query), dtype=np.float32),
            top_k,
        )

    def index_corpus(
        self,
        chunks: Sequence[KnowledgeChunk],
        *,
        document_ids: Sequence[str],
        batch_size: int = 32,
    ) -> dict[str, float | int]:
        """Embed every final chunk exactly once in bounded batches per run.

        New writes precede stale-ID pruning. Failed runs must be retried; neither
        this batch nor document replacement is a multi-document transaction.
        """
        if not chunks or batch_size <= 0:
            raise ValueError("nonempty corpus and positive batch_size required")
        ids = set(document_ids)
        if len(ids) != len(document_ids) or not ids or any(not d.strip() for d in ids):
            raise ValueError("document_ids must be unique and nonempty")
        if any(c.document_id not in ids for c in chunks):
            raise ValueError("chunk does not belong to the specified corpus")
        if len({c.chunk_id for c in chunks}) != len(chunks):
            raise ValueError("duplicate corpus chunk IDs")
        existing = self._vector_store.document_ids()
        if existing - ids:
            raise ValueError(
                f"refusing to overwrite a collection with unrelated documents: {sorted(existing - ids)}"
            )
        embedding_seconds = indexing_seconds = 0.0
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            before = perf_counter()
            vectors = self._embedder.embed_documents(
                [document_embedding_text(c) for c in batch]
            )
            embedding_seconds += perf_counter() - before
            before = perf_counter()
            self._vector_store.upsert_chunks(batch, vectors)
            indexing_seconds += perf_counter() - before
        before = perf_counter()
        for document_id in document_ids:
            self._vector_store.prune_document(
                document_id,
                [c.chunk_id for c in chunks if c.document_id == document_id],
            )
        indexing_seconds += perf_counter() - before
        count = self._vector_store.point_count()
        if count != len(chunks):
            raise RuntimeError(
                f"index point count {count} differs from corpus size {len(chunks)}"
            )
        return {
            "embedding_seconds": embedding_seconds,
            "qdrant_indexing_seconds": indexing_seconds,
            "embedded_chunk_count": len(chunks),
            "point_count": count,
        }


class DenseRetriever:
    """Token-safe passage indexing, max-child scoring, canonical parent results."""

    def __init__(
        self, embedder, vector_store, *, passage_builder=None, oversample_factor=4
    ):
        from accelerator_rag.retrieval.passages import PassageBuilder
        from accelerator_rag.storage.qdrant_passages import QdrantPassageStore

        if not isinstance(vector_store, QdrantPassageStore):
            raise ValueError("DenseRetriever requires QdrantPassageStore")
        if type(oversample_factor) is not int or oversample_factor < 1:
            raise ValueError("invalid oversample_factor")
        self._embedder, self._vector_store = embedder, vector_store
        self.builder = passage_builder or PassageBuilder(embedder)
        from accelerator_rag.retrieval.index_contract import DenseIndexContract

        self.contract = DenseIndexContract.from_fingerprint(
            embedder.fingerprint(), self.builder.contract
        )
        if self.contract != vector_store.contract:
            raise ValueError(
                "embedder/passage builder differs from store DenseIndexContract; use a new collection or rebuild the full collection"
            )
        self.oversample_factor = oversample_factor
        self.last_passage_trace = []
        self.last_candidate_limits = []

    def index_document(self, document_id, chunks):
        if not document_id.strip() or not chunks:
            raise ValueError("nonempty document/chunks required")
        if any(c.document_id != document_id for c in chunks):
            raise ValueError("chunks do not belong to document_id")
        # Validate existing payload ownership before any mutation.
        existing = list(self._vector_store.all_passages())
        parent_ids = {c.chunk_id for c in chunks}
        if any(
            p.parent.document_id != document_id and p.parent_chunk_id in parent_ids
            for p in existing
        ):
            raise ValueError("parent ID belongs to another document")
        return self._index_passages(chunks, document_ids=[document_id])

    def index_corpus(self, chunks, *, document_ids, batch_size=32, passages=None):
        if not chunks or batch_size <= 0:
            raise ValueError("nonempty corpus and positive batch_size required")
        parents = {c.chunk_id: c for c in chunks}
        ids = set(document_ids)
        if (
            len(parents) != len(chunks)
            or len(ids) != len(document_ids)
            or not ids
            or any(not d.strip() for d in ids)
            or any(c.document_id not in ids for c in chunks)
        ):
            raise ValueError("invalid parent/document identity")
        existing = self._vector_store.document_ids()
        if existing - ids:
            raise ValueError("refusing collection with unrelated documents")
        result = self._index_passages(
            chunks, document_ids=document_ids, batch_size=batch_size, passages=passages
        )
        if result["point_count"] != result["embedded_passage_count"]:
            raise RuntimeError("Qdrant passage point count mismatch")
        return result

    def _index_passages(self, chunks, *, document_ids, batch_size=32, passages=None):
        parents = {c.chunk_id: c for c in chunks}
        if len(parents) != len(chunks):
            raise ValueError("duplicate parent IDs")
        passages = self.builder.build(chunks) if passages is None else passages
        if (
            not passages
            or len({p.passage_id for p in passages}) != len(passages)
            or {p.parent_chunk_id for p in passages} != set(parents)
            or any(
                p.parent != parents.get(p.parent_chunk_id)
                or p.contract_id != self.builder.contract_id
                for p in passages
            )
        ):
            raise ValueError("invalid passage parent/contract integrity")
        # Audit every final input before the first embedding/write; also assert
        # immediately before each actual encode through the embedder adapter.
        rows = self._embedder.audit_inputs(
            [document_embedding_text(p) for p in passages]
        )
        if any(r["token_count"] > self.builder.limit for r in rows):
            raise ValueError("passage exceeds token budget before indexing")
        embedding_seconds = indexing_seconds = 0.0
        for start in range(0, len(passages), batch_size):
            batch = passages[start : start + batch_size]
            before = perf_counter()
            vectors = self._embedder.embed_token_safe_documents(
                [document_embedding_text(p) for p in batch]
            )
            embedding_seconds += perf_counter() - before
            before = perf_counter()
            self._vector_store.upsert_passages(batch, vectors)
            indexing_seconds += perf_counter() - before
        before = perf_counter()
        for doc in document_ids:
            self._vector_store.prune_document(
                doc, [p.passage_id for p in passages if p.parent.document_id == doc]
            )
        indexing_seconds += perf_counter() - before
        count = self._vector_store.point_count()
        return {
            "embedding_seconds": embedding_seconds,
            "qdrant_indexing_seconds": indexing_seconds,
            "embedded_passage_count": len(passages),
            "point_count": count,
            "unique_parent_count": len(parents),
        }

    def search(self, query, top_k=3):
        hits, trace, limits = self.search_with_trace(query, top_k)
        self.last_passage_trace, self.last_candidate_limits = trace, limits
        return hits

    def search_with_trace(self, query, top_k=3):
        if not query.strip() or type(top_k) is not int or top_k <= 0:
            raise ValueError("invalid search query/top_k")
        self._vector_store.verify_contract()
        vector = self._embedder.embed_query(query)
        total = self._vector_store.point_count()
        candidate_limits = []
        best = {}
        limit = min(total, top_k * self.oversample_factor)
        while limit:
            candidate_limits.append(limit)
            hits = self._vector_store.search_passages(vector, limit)
            best = {}
            for hit in hits:
                key = hit.passage.parent_chunk_id
                if key in best and best[key].passage.parent != hit.passage.parent:
                    raise ValueError("inconsistent canonical parent payload")
                if key not in best or hit.score > best[key].score:
                    best[key] = hit
            if len(best) >= top_k or limit >= total:
                break
            limit = min(total, max(limit + 1, limit * 2))
        ranked = sorted(
            best.values(), key=lambda h: (-h.score, h.passage.parent_chunk_id)
        )[:top_k]
        trace = [
            {
                "parent_chunk_id": h.passage.parent_chunk_id,
                "passage_id": h.passage.passage_id,
                "passage_ordinal": h.passage.passage_ordinal,
                "passage_excerpt": h.passage.text,
                "passage_score": h.score,
                "candidate_limits": candidate_limits,
            }
            for h in ranked
        ]
        return (
            [
                RetrievalResult(i, h.score, h.passage.parent, "qdrant")
                for i, h in enumerate(ranked, 1)
            ],
            trace,
            candidate_limits,
        )
