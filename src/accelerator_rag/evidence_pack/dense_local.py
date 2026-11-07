"""Read-only dense channels backed by locally computed E5/Qwen3 vectors.

The vectors are built by ``scripts/research/build_dense_vectors.py`` with the
production-identical model contracts.  Passage-level E5 scores are reduced to
the parent chunk by maximum cosine, matching the production passage-to-parent
lookup; Qwen3 has one passage per parent.  Query vectors are precomputed and
looked up by the exact question text, so a replay never loads a model.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


def _dot(left, right) -> float:
    return float(np.dot(left, right))


@dataclass
class CachedPassageDenseChannel:
    name: str
    passage_parents: tuple[str, ...]
    passage_vectors: np.ndarray
    query_vectors: dict[str, np.ndarray]
    available: bool = True

    def search(self, query: str, chunk_ids, top_k: int):
        query_vector = self.query_vectors.get(query)
        if query_vector is None:
            raise KeyError(f"no precomputed query vector for: {query[:40]}")
        allowed = set(chunk_ids)
        best: dict[str, float] = {}
        scores = self.passage_vectors @ query_vector
        for parent, score in zip(self.passage_parents, scores, strict=True):
            if parent not in allowed:
                continue
            value = float(score)
            if value > best.get(parent, -math.inf):
                best[parent] = value
        ranked = sorted(best.items(), key=lambda item: (-item[1], item[0]))
        return ranked[:top_k]


@dataclass
class FusedDenseChannel:
    channels: tuple
    name: str = "dense"
    available: bool = True

    def search(self, query: str, chunk_ids, top_k: int):
        allowed = set(chunk_ids)
        fused: dict[str, float] = {}
        for channel in self.channels:
            for rank, (chunk_id, _score) in enumerate(
                channel.search(query, allowed, top_k), 1
            ):
                fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (60 + rank)
        ranked = sorted(fused.items(), key=lambda item: (-item[1], item[0]))
        return ranked[:top_k]
