"""Requirement queries, lexical/dense recall and same-page context expansion."""

from collections import defaultdict
from dataclasses import replace
import math
from time import perf_counter

from accelerator_rag.retrieval.bm25 import BM25Retriever


class RequirementRetriever:
    def __init__(self, dense, chunks, reranker, *, candidate_limit=20):
        if type(candidate_limit) is not int or not 1 <= candidate_limit <= 20:
            raise ValueError("invalid candidate limit")
        self.dense = dense
        self.reranker = reranker
        self.candidate_limit = candidate_limit
        self.chunks = {c.chunk_id: c for c in chunks}
        self.lexical = BM25Retriever(list(self.chunks.values()))
        self.by_page = defaultdict(list)
        for chunk in self.chunks.values():
            for page in range(chunk.page_start, chunk.page_end + 1):
                self.by_page[(chunk.document_id, chunk.document_version, page)].append(
                    chunk
                )

    def retrieve(self, query, queries, *, anchors=()):
        """Scores are fused by rank; BM25 scores never mix with dense scores."""
        hits, scores, origins, searches = {}, {}, defaultdict(list), []
        rerank_seconds = 0.0
        for text in dict.fromkeys(queries):
            dense_hits, trace, candidates = self.dense.search_with_trace(text, top_k=5)
            rerank_seconds += candidates["rerank_seconds"]
            lexical = self.lexical.search(text, top_k=5)
            searches.append(
                {
                    "query": text,
                    "dense_trace": trace,
                    "bm25": [h.chunk.chunk_id for h in lexical],
                }
            )
            for channel, results in (("dense", dense_hits), ("bm25", lexical)):
                for hit in results:
                    cid = hit.chunk.chunk_id
                    if cid in hits and hits[cid].chunk != hit.chunk:
                        raise ValueError("inconsistent canonical parent")
                    hits[cid] = hit
                    scores[cid] = scores.get(cid, 0) + 1 / (60 + hit.rank)
                    origins[cid].append(
                        {"channel": channel, "query": text, "rank": hit.rank}
                    )
        # A section boundary must not sever the explanation on the same page.
        ranked = sorted(hits, key=lambda cid: (-scores[cid], cid))
        seed_hits = list(anchors)[:3] + [hits[cid] for cid in ranked[:3]]
        for anchor in seed_hits:
            chunk = anchor.chunk
            for page in range(chunk.page_start, chunk.page_end + 1):
                neighbors = self.by_page[
                    (chunk.document_id, chunk.document_version, page)
                ]
                for neighbor in sorted(neighbors, key=lambda c: c.chunk_id)[:6]:
                    cid = neighbor.chunk_id
                    if cid not in hits:
                        hits[cid] = replace(anchor, chunk=neighbor)
                        scores[cid] = 0.0
                        origins[cid].append(
                            {"channel": "same-page", "anchor": chunk.chunk_id}
                        )
        # Preserve expanded contexts even when a general query has many matches.
        ordered = sorted(hits, key=lambda cid: (-scores[cid], cid))[:48]
        started = perf_counter()
        values = self.reranker.score(query, [hits[cid].chunk.text for cid in ordered])
        rerank_seconds += perf_counter() - started
        if len(values) != len(ordered) or any(not math.isfinite(v) for v in values):
            raise ValueError("missing candidate reranker scores")
        ranked = sorted(
            zip(ordered, values, strict=True), key=lambda item: (-item[1], item[0])
        )
        chosen = ranked[: self.candidate_limit]
        return (
            [
                replace(hits[cid], rank=i, score=score, retriever="requirement-hybrid")
                for i, (cid, score) in enumerate(chosen, 1)
            ],
            {
                "searches": searches,
                "candidate_count": len(hits),
                "ranked": [
                    {"chunk_id": cid, "score": score, "origins": origins[cid]}
                    for cid, score in ranked
                ],
                "rerank_seconds": rerank_seconds,
            },
        )
