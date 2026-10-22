"""Two fixed Top-10 parent rankings, scored through their actual winning passages."""

from dataclasses import asdict
from time import perf_counter
import math
from accelerator_rag.domain.knowledge import RetrievalResult


class DenseRerankedRetriever:
    def __init__(self, e5, qwen, reranker):
        self.retrievers = {"E5": e5, "Qwen3": qwen}
        self.reranker = reranker
        self.traces = {}
        self.candidates = {}
        self.rerank_seconds = 0.0

    def search(self, query: str, *, top_k: int) -> list[RetrievalResult]:
        if type(top_k) is not int or not 1 <= top_k <= 5:
            raise ValueError("reranked retrieval returns one to five parents")
        parents, children = {}, {}
        for model, dense in self.retrievers.items():
            hits = dense.search(query, top_k=10)
            traces = dense.last_passage_trace
            if len(hits) != len(traces):
                raise ValueError("missing actual retrieved passage trace")
            seen = set()
            for hit, trace in zip(hits, traces, strict=True):
                pid = hit.chunk.chunk_id
                if pid in seen or trace['parent_chunk_id'] != pid:
                    raise ValueError("invalid canonical parent / winning passage alignment")
                seen.add(pid)
                if pid in parents and parents[pid]['chunk'] != hit.chunk:
                    raise ValueError("parent payload mismatch across models")
                parent = parents.setdefault(pid, {'chunk':hit.chunk, 'original_ranks':{}})
                parent['original_ranks'][model] = hit.rank
                text = trace['passage_excerpt']
                if not text.strip():
                    raise ValueError("empty retrieved passage")
                child = children.setdefault((pid, text), {
                    'parent_chunk_id':pid, 'passage_text':text, 'sources':[]
                })
                child['sources'].append({'model':model, 'original_rank':hit.rank,
                                         'passage_id':trace['passage_id']})
        assert len(parents) <= 20 and len(children) <= 20
        ordered = sorted(children.values(), key=lambda c:(c['parent_chunk_id'], c['passage_text']))
        started = perf_counter()
        scores = self.reranker.score(query, [c['passage_text'] for c in ordered])
        elapsed = perf_counter() - started
        self.rerank_seconds += elapsed
        if len(scores) != len(ordered) or any(not math.isfinite(s) for s in scores):
            raise ValueError("invalid reranker scores")
        winners = {}
        for child, score in zip(ordered, scores, strict=True):
            child['rerank_score'] = score
            pid = child['parent_chunk_id']
            if pid not in winners or score > winners[pid]['rerank_score']:
                winners[pid] = child
        ranked = sorted(parents, key=lambda pid:(-winners[pid]['rerank_score'], pid))
        trace = []
        for rank, pid in enumerate(ranked, 1):
            child = winners[pid]
            ranks = parents[pid]['original_ranks']
            trace.append({'rank':rank, 'parent_chunk_id':pid,
                'rerank_score':child['rerank_score'],
                'source_retrievers':'both' if len(ranks)==2 else next(iter(ranks)),
                'E5_original_rank':ranks.get('E5'), 'Qwen3_original_rank':ranks.get('Qwen3'),
                'winning_passage_id':child['sources'][0]['passage_id'],
                'winning_passage_source_model':('both' if len(child['sources'])==2 else child['sources'][0]['model']),
                'winning_passage_text':child['passage_text'],
                'winning_passage_sources':child['sources']})
        self.traces[query] = trace
        self.candidates[query] = {'parents':[asdict(parents[p]['chunk']) for p in sorted(parents)],
            'passages':ordered, 'parent_count':len(parents), 'passage_count':len(ordered),
            'rerank_seconds':elapsed}
        return [RetrievalResult(i,winners[p]['rerank_score'],parents[p]['chunk'],
                                'dual-dense-qwen3-reranker')
                for i,p in enumerate(ranked[:top_k],1)]
