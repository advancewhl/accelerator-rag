"""Optional dense channel adapter for E5/Qwen3 embeddings.

The offline pipeline does not ship an embedding service.  ``EmbeddingDenseChannel``
accepts any injected query embedder and pre-computed chunk vectors, so phase 4
can supply the frozen E5/Qwen3 indexes without changing the recall contract.
``HashingEmbedder`` is a deterministic stand-in used only to test the channel.
"""

from __future__ import annotations

import hashlib
import math

from accelerator_rag.retrieval.bm25 import tokenize


class HashingEmbedder:
    """Deterministic lexical hashing; a test stand-in, not E5/Qwen3."""

    def __init__(self, dimensions: int = 256):
        if type(dimensions) is not int or dimensions < 8:
            raise ValueError("dimensions must be an integer >= 8")
        self.dimensions = dimensions

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dimensions
            sign = 1.0 if value >> 63 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return tuple(vector)
        return tuple(value / norm for value in vector)


def _cosine(left, right) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


class EmbeddingDenseChannel:
    """Dense recall over pre-computed chunk vectors.

    ``embedder.embed(query)`` must match the vectors' embedding space.  The
    channel never embeds documents and never writes an index.
    """

    name = "dense"
    available = True

    def __init__(self, *, chunk_ids, vectors, embedder):
        if len(chunk_ids) != len(vectors):
            raise ValueError("chunk ids and vectors must have equal length")
        if not chunk_ids:
            raise ValueError("dense channel needs at least one chunk")
        self.chunk_ids = tuple(chunk_ids)
        self.vectors = tuple(tuple(float(value) for value in row) for row in vectors)
        self.embedder = embedder
        if any(len(row) != len(self.vectors[0]) for row in self.vectors):
            raise ValueError("inconsistent vector dimensions")

    @classmethod
    def hashing(cls, chunks, *, dimensions: int = 256):
        embedder = HashingEmbedder(dimensions)
        return cls(
            chunk_ids=[chunk.chunk_id for chunk in chunks],
            vectors=[embedder.embed(chunk.text) for chunk in chunks],
            embedder=embedder,
        )

    def search(self, query: str, chunk_ids, top_k: int):
        allowed = set(chunk_ids)
        query_vector = self.embedder.embed(query)
        scored = [
            (chunk_id, _cosine(query_vector, vector))
            for chunk_id, vector in zip(self.chunk_ids, self.vectors, strict=True)
            if chunk_id in allowed
        ]
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:top_k]
