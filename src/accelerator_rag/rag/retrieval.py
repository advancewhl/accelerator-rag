"""Requirement queries, lexical/dense recall and same-page context expansion."""

from collections import defaultdict
from dataclasses import replace
import math
from time import perf_counter

from accelerator_rag.domain.knowledge import RetrievalResult
from accelerator_rag.retrieval.bm25 import BM25Retriever
from accelerator_rag.retrieval.scope import RetrievalScope


class RequirementRetriever:
    def __init__(
        self,
        dense,
        chunks,
        reranker,
        *,
        candidate_limit=20,
        structured_index=None,
    ):
        if type(candidate_limit) is not int or not 1 <= candidate_limit <= 20:
            raise ValueError("invalid candidate limit")
        self.dense = dense
        self.reranker = reranker
        self.candidate_limit = candidate_limit
        self.structured_index = structured_index
        self.chunks = {c.chunk_id: c for c in chunks}
        self.lexical = BM25Retriever(list(self.chunks.values()))
        self.by_page = defaultdict(list)
        self.by_document = defaultdict(list)
        for chunk in self.chunks.values():
            key = (
                chunk.document_id,
                chunk.document_version,
                chunk.effective_position_kind,
            )
            self.by_document[key].append(chunk)
            for page in range(chunk.page_start, chunk.page_end + 1):
                self.by_page[key + (page,)].append(chunk)
        for group in self.by_document.values():
            group.sort(key=self._order_key)

    @staticmethod
    def _order_key(chunk):
        """Explicit block ordinal first; legacy evidence falls back to position."""

        return (
            getattr(chunk, "document_ordinal", 0),
            chunk.page_start,
            chunk.page_end,
            chunk.chunk_id,
        )

    def _neighbors(self, anchor, scope):
        """Reading-order and same-position context, never another revision."""

        key = (
            anchor.chunk.document_id,
            anchor.chunk.document_version,
            anchor.chunk.effective_position_kind,
        )
        candidates = []
        for page in range(anchor.chunk.page_start, anchor.chunk.page_end + 1):
            ordered = sorted(self.by_page[key + (page,)], key=self._order_key)
            if anchor.chunk in ordered:
                index = ordered.index(anchor.chunk)
                candidates.extend(ordered[max(0, index - 2) : index + 3])
            else:
                candidates.extend(ordered[:6])
        # Word paragraphs and spreadsheet rows do not share a page number;
        # adjacent evidence must come from the document's reading order.
        if anchor.chunk.effective_position_kind in {
            "paragraph",
            "section",
            "cell_range",
        }:
            ordered = self.by_document[key]
            if anchor.chunk in ordered:
                index = ordered.index(anchor.chunk)
                candidates.extend(ordered[max(0, index - 2) : index + 3])
            else:
                candidates.extend(ordered[:6])
        selected = []
        for candidate in candidates:
            if candidate.chunk_id == anchor.chunk.chunk_id:
                continue
            if candidate.chunk_id in {item.chunk_id for item in selected}:
                continue
            if scope is not None and not scope.allows(candidate):
                continue
            selected.append(candidate)
            if len(selected) == 6:
                break
        return selected

    def retrieve(
        self,
        query,
        queries,
        *,
        anchors=(),
        scope: RetrievalScope | None = None,
    ):
        """Scores are fused by rank; BM25 scores never mix with dense scores."""
        hits, scores, origins, searches = {}, {}, defaultdict(list), []
        exact_ids: set[str] = set()
        rerank_seconds = 0.0
        revision_ids = scope.revision_ids if scope is not None else None
        for text in dict.fromkeys(queries):
            # Retain dense ranks 6-10: the dual-dense reranker cuts to its own
            # Top-N, and dropping them here would remove parents before rank
            # fusion can consider them.  BM25 stays at five to bound the
            # lexical fan-out; the final candidate_limit is unchanged.
            if scope is None:
                dense_hits, trace, candidates = self.dense.search_with_trace(
                    text, top_k=10
                )
            else:
                dense_hits, trace, candidates = self.dense.search_with_trace(
                    text, top_k=10, scope=scope
                )
            rerank_seconds += candidates["rerank_seconds"]
            lexical = self.lexical.search(text, top_k=5, scope=scope)
            searches.append(
                {
                    "query": text,
                    "dense_trace": trace,
                    "bm25": [h.chunk.chunk_id for h in lexical],
                }
            )
            for channel, results in (("dense", dense_hits), ("bm25", lexical)):
                for hit in results:
                    if scope is not None and not scope.allows(hit.chunk):
                        continue
                    cid = hit.chunk.chunk_id
                    if cid in hits and hits[cid].chunk != hit.chunk:
                        raise ValueError("inconsistent canonical parent")
                    hits[cid] = hit
                    scores[cid] = scores.get(cid, 0) + 1 / (60 + hit.rank)
                    origins[cid].append(
                        {"channel": channel, "query": text, "rank": hit.rank}
                    )
            if self.structured_index is not None:
                for record in self.structured_index.lookup_in_text(
                    text, revision_ids=revision_ids
                ):
                    chunk = self.chunks.get(record.chunk_id)
                    if chunk is None:
                        continue
                    if scope is not None and not scope.allows(chunk):
                        continue
                    cid = chunk.chunk_id
                    if cid not in hits:
                        hits[cid] = RetrievalResult(
                            1, 1.0, chunk, "structured-exact"
                        )
                    # Exact identifier rows must survive the 48-candidate cut;
                    # the reranker still decides final order among them.
                    scores[cid] = max(scores.get(cid, 0.0), 2.0)
                    exact_ids.add(cid)
                    origins[cid].append(
                        {
                            "channel": "structured-exact",
                            "query": text,
                            "record_id": record.record_id,
                        }
                    )
        # A section boundary must not sever the explanation on the same page.
        ranked = sorted(hits, key=lambda cid: (-scores[cid], cid))
        seed_hits = [
            anchor
            for anchor in anchors
            if scope is None or scope.allows(anchor.chunk)
        ][:3] + [hits[cid] for cid in ranked[:3]]
        for anchor in seed_hits:
            chunk = anchor.chunk
            for neighbor in self._neighbors(anchor, scope):
                cid = neighbor.chunk_id
                if cid not in hits:
                    hits[cid] = replace(anchor, chunk=neighbor)
                    scores[cid] = 0.0
                    origins[cid].append(
                        {
                            "channel": "neighbor",
                            "anchor": chunk.chunk_id,
                        }
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
        # Exact identifier rows are the user's target; keep all of them within
        # the candidate budget rather than an arbitrary five.
        exact_ranked = [
            item for item in ranked if item[0] in exact_ids
        ][: self.candidate_limit]
        chosen_ids = {cid for cid, _score in exact_ranked}
        chosen = (
            exact_ranked
            + [
                item
                for item in ranked
                if item[0] not in chosen_ids
            ][: max(0, self.candidate_limit - len(exact_ranked))]
        )
        return (
            [
                replace(hits[cid], rank=i, score=score, retriever="requirement-hybrid")
                for i, (cid, score) in enumerate(chosen, 1)
            ],
            {
                "searches": searches,
                "scope": scope.describe() if scope is not None else None,
                "structured_exact": sorted(exact_ids),
                "chosen": [
                    {
                        "chunk_id": cid,
                        "score": score,
                        "rank": index,
                        "exact": cid in exact_ids,
                    }
                    for index, (cid, score) in enumerate(chosen, 1)
                ],
                "candidate_count": len(hits),
                "ranked": [
                    {"chunk_id": cid, "score": score, "origins": origins[cid]}
                    for cid, score in ranked
                ],
                "rerank_seconds": rerank_seconds,
            },
        )
