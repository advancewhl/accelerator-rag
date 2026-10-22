"""Original-query dense composition; runtime has no benchmark metadata."""

import re

from accelerator_rag.domain.knowledge import RetrievalResult


def query_language(query: str) -> str:
    return "zh" if re.search(r"[\u3400-\u9fff\uf900-\ufaff]", query) else "en"


class LanguageRoutedDenseRetriever:
    def __init__(self, e5, qwen):
        self.retrievers = {"en": e5, "zh": qwen}

    def search(self, query: str, *, top_k: int) -> list[RetrievalResult]:
        return self.retrievers[query_language(query)].search(query, top_k=top_k)


class DualDenseRRFRetriever:
    """Equal-weight RRF with fixed k=60 and ten canonical parents per model."""

    def __init__(self, e5, qwen):
        self.retrievers = {"E5": e5, "Qwen3": qwen}
        self.traces = {}

    def search(self, query: str, *, top_k: int) -> list[RetrievalResult]:
        if type(top_k) is not int or not 1 <= top_k <= 5:
            raise ValueError("dual dense returns between one and five parents")
        parents, scores, sources = {}, {}, {}
        for name, retriever in self.retrievers.items():
            seen = set()
            for rank, hit in enumerate(retriever.search(query, top_k=10), 1):
                parent_id = hit.chunk.chunk_id
                if parent_id in seen:
                    raise ValueError("input ranking contains duplicate canonical parents")
                seen.add(parent_id)
                if parent_id in parents and parents[parent_id] != hit.chunk:
                    raise ValueError("canonical parent payload differs across models")
                parents[parent_id] = hit.chunk
                contribution = 1.0 / (60 + rank)
                scores[parent_id] = scores.get(parent_id, 0.0) + contribution
                sources.setdefault(parent_id, []).append(
                    {"model": name, "rank": rank, "rrf_contribution": contribution}
                )
        order = sorted(parents, key=lambda parent_id: (-scores[parent_id], parent_id))
        self.traces[query] = [
            {"parent_id": parent_id, "score": scores[parent_id], "sources": sources[parent_id]}
            for parent_id in order
        ]
        return [RetrievalResult(rank, scores[p], parents[p], "dual-dense-rrf")
                for rank, p in enumerate(order[:top_k], 1)]
