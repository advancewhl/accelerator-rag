"""Generic bounded query transformation and same-model dense rank fusion."""
from dataclasses import dataclass, replace

PROMPT = '''Rewrite the user question into up to 3 independent retrieval intents.
Use English retrieval wording when the likely source is English, including for
Chinese technical questions. Preserve technical identifiers, numbers, acronyms,
and all distinct information needs. Do not answer the question. Do not invent
facts, values, identifiers, or documents. For an atomic question, a single
retrieval rewrite is sufficient. Return subqueries only; never include an answer.
'''
TOOL = {'type':'function','function':{'name':'plan_retrieval_queries',
    'description':'Produce bounded independent search intents, never answers.',
    'parameters':{'type':'object','properties':{'subqueries':{'type':'array',
        'items':{'type':'string'},'maxItems':3}},'required':['subqueries'],
        'additionalProperties':False}}}

@dataclass(frozen=True)
class QueryPlan:
    original_query: str
    subqueries: tuple[str, ...]




class MultiQueryRetriever:
    def __init__(self, dense, plans):
        self.dense, self.plans, self.traces = dense, plans, {}
        self.candidates = {}

    def search(self, query, *, top_k):
        plan = self.plans[query]
        scores, hits, trace = {}, {}, {}
        candidates = []
        for i,text in enumerate((plan.original_query,*plan.subqueries)):
            retrieved = self.dense.search(text,top_k=max(10,top_k))
            candidates.append({'query_index':i,'query':text,'results':[
                {'parent_id':h.chunk.chunk_id,'original_rank':h.rank,
                 'cosine_score':h.score} for h in retrieved]})
            for hit in retrieved:
                key = hit.chunk.chunk_id
                contribution = 1/(60+hit.rank)
                scores[key] = scores.get(key,0)+contribution
                hits[key] = hit
                trace.setdefault(key,[]).append({'query_index':i,'query':text,
                    'original_rank':hit.rank,'cosine_score':hit.score,
                    'fusion_contribution':contribution})
        keys = sorted(scores,key=lambda k:(-scores[k],k))[:top_k]
        self.traces[query] = [{'parent_id':k,'contributions':trace[k]} for k in keys]
        self.candidates[query] = candidates
        return [replace(hits[k],rank=i,score=scores[k],retriever='dense-multi-query-rrf')
                for i,k in enumerate(keys,1)]
