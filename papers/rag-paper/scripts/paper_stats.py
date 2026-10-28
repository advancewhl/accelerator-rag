"""Deterministic new analyses for the system paper. Inputs are read-only.

Bootstrap: 1,000 paired query resamples, PCG64 seed 20261027,
percentile interval with NumPy's linear quantile convention.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
DATA = ROOT / "papers/rag-thesis/data"
SEED, REPLICATES = 20261027, 1000
SOURCE_HASHES = {}


def load(path):
    path = Path(path)
    SOURCE_HASHES[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if path.suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    return json.loads(path.read_text())


def interval(values):
    return np.quantile(values, [.025, .975], method="linear").tolist()


def normalize(text):
    text=unicodedata.normalize('NFKC',text).replace('\x00','')
    text=re.sub(r'(?<=[A-Za-z])-\s+(?=[a-z])','',text)
    return re.sub(r'\s+','',text).casefold()


def evidence_matches(chunk,target):
    return (chunk['document_id']==target['document_id']
            and chunk['page_start']<=target['page']<=chunk['page_end']
            and normalize(target['excerpt']) in normalize(chunk['text']))


def calculate():
    ranks = load(DATA / "query-ranks-v2.csv")
    published = load(DATA / "retrieval-metrics-v2.csv")
    benchmark = load(DATA / "benchmark.csv")
    latency = load(DATA / "production-latency-20261026.csv")
    corpus = load(DATA / "corpus.csv")
    historical = load(DATA / "historical-ablations.csv")
    snapshot = load(DATA / "evidence-snapshot.json")
    multi = load(ROOT / "reports/rag-stage-two-eight-multilingual-retrieval.json")
    pairwise_old = load(ROOT / "reports/rag-stage-two-seven-embedding-comparison.json")
    candidates = load(ROOT / "tmp/stage-two-eight-two/original-query-candidates.json")
    rerank = load(ROOT / "reports/rag-stage-two-eight-two-reranking.json")
    frozen = load(ROOT / "data/evaluation/retrieval_baseline.json")
    production = load(ROOT / "reports/rag-production-readiness-20261026.json")
    ids = [r["query_id"] for r in benchmark if r["answerable"] == "True"]
    assert len(ids) == 21 and len(benchmark) == 32 and len(ranks) == 231
    qmeta = {r["query_id"]: r for r in benchmark}
    lookup = {(r["method"], r["query_id"]): r for r in ranks}
    methods = [r["method"] for r in published]
    arrays = {}
    for method in methods:
        first = np.array([int(lookup[method, q]["first_complete_rank"]) if lookup[method, q]["first_complete_rank"] else 0 for q in ids])
        arrays[method] = {"hit": (first > 0).astype(float), "rr": np.divide(1.,first,out=np.zeros(21),where=first>0), "rank":first}
    resamples = np.random.default_rng(SEED).integers(0, 21, size=(REPLICATES, 21))
    main = {}
    for m in methods:
        a = arrays[m]
        main[m] = {"n":21,"Hit@1":float(np.mean(a["rank"]==1)),
                   "Hit@3":float(np.mean((a["rank"]>0)&(a["rank"]<=3))),
                   "Hit@5":float(a["hit"].mean()),"MRR@5":float(a["rr"].mean()),
                   "hit_count":int(a["hit"].sum())}
        old = next(r for r in published if r["method"]==m)
        for k in ["Hit@1","Hit@3","Hit@5","MRR@5"]:assert abs(main[m][k]-float(old[k]))<1e-12
        if m in ["BM25","E5","Qwen3","Dual + reranker"]:
            main[m]["hit_ci95"] = interval(a["hit"][resamples].mean(axis=1))
            main[m]["mrr_ci95"] = interval(a["rr"][resamples].mean(axis=1))
    a,b=arrays["E5"],arrays["Dual + reranker"]
    gain=[q for i,q in enumerate(ids) if a["hit"][i]==0 and b["hit"][i]==1]
    loss=[q for i,q in enumerate(ids) if a["hit"][i]==1 and b["hit"][i]==0]
    discordant=len(gain)+len(loss)
    exact=min(1.,2*sum(math.comb(discordant,k) for k in range(min(len(gain),len(loss))+1))/2**discordant) if discordant else 1.
    paired={"n":21,"gain_query_ids":gain,"loss_query_ids":loss,
            "both_hit":int(np.sum((a["hit"]==1)&(b["hit"]==1))),"both_miss":int(np.sum((a["hit"]==0)&(b["hit"]==0))),
            "hit_difference":float((b["hit"]-a["hit"]).mean()),
            "hit_difference_ci95":interval((b["hit"]-a["hit"])[resamples].mean(axis=1)),
            "mrr_difference":float((b["rr"]-a["rr"]).mean()),
            "mrr_difference_ci95":interval((b["rr"]-a["rr"])[resamples].mean(axis=1)),
            "mcnemar_exact_two_sided_p":exact,"discordant":discordant}
    assert gain==["xfel-normal-energy","cryo-interlock"] and not loss and exact==.5
    language={}
    for group in ["en","zh","cross_language"]:
        mask=np.array([lookup["E5",q]["language_relation"]==group if group=="cross_language" else qmeta[q]["language"]==group for q in ids])
        language[group]={"n":int(mask.sum()),"methods":{m:{"hits":int(arrays[m]["hit"][mask].sum()),"Hit@5":float(arrays[m]["hit"][mask].mean())} for m in ["BM25","E5","Qwen3","Dual + reranker"]}}
    timing={}
    for cohort in ["all","answerable","negative"]:
        selected=[r for r in latency if cohort=="all" or (r["answerable"]=="True")== (cohort=="answerable")]
        totals=np.array([float(r["total_seconds"]) for r in selected]);n=len(totals)
        means={k:float(np.mean([float(r[k]) for r in selected])) for k in ["retrieval_seconds","rerank_seconds","generation_seconds","total_seconds"]}
        shares={k:means[k]/means["total_seconds"] for k in means if k!="total_seconds"}
        shares["orchestration"] = 1-sum(shares.values())
        timing[cohort]={"n":n,"mean":float(totals.mean()),"p50":float(np.quantile(totals,.5,method="linear")),
                        "p95":float(np.quantile(totals,.95,method="linear")),"max":float(totals.max()),"component_means":means,"component_shares":shares}
    calls={}
    for m,key in [("E5","intfloat/multilingual-e5-base + multi-query"),("Qwen3","Qwen/Qwen3-Embedding-0.6B + multi-query")]:
        entry=multi["models"][key]; plans=entry["query_candidates"]
        total=sum(len(v) for v in plans.values());positive=sum(len(plans[qmeta[q]["query"]]) for q in ids)
        calls[m]={"queries_all":32,"queries_answerable":21,"original_calls":32,"multi_query_calls":total,
                  "call_multiplier":total/32,"answerable_calls":positive,"answerable_call_multiplier":positive/21,
                  "calls_per_query_distribution":dict(sorted(Counter(map(len,plans.values())).items())),
                  "measured_evaluation_seconds":entry["evaluation_seconds"],
                  "measured_evaluation_seconds_per_query":entry["evaluation_seconds"]/32,
                  "planning_time_seconds":None,"matched_single_latency_seconds":None,
                  "hit_delta":main[m+" + multi-query"]["Hit@5"]-main[m]["Hit@5"],
                  "mrr_delta":main[m+" + multi-query"]["MRR@5"]-main[m]["MRR@5"]}
    # Record actual raw candidates, including exact quotations. No new retrieval.
    failures={}
    for qid in ["shine-ioc-startup","cryo-interlock","xfel-normal-energy"]:
        q=next(x for x in frozen["queries"] if x["id"]==qid);case={"query":q["query"],"evidence_groups":q["evidence_groups"],"models":{}}
        for m in ["E5","Qwen3"]:
            r=candidates["rankings"][m][q["query"]]; rows=[]
            for hit,trace in zip(r["results"][:3],r["passage_trace"][:3],strict=True):
                rows.append({"rank":hit["rank"],"cosine_score":hit["score"],"document":hit["chunk"]["document_title"],
                             "document_id":hit["chunk"]["document_id"],"page":hit["chunk"]["page_start"],
                             "chunk_id":hit["chunk"]["chunk_id"],"passage_id":trace["passage_id"],
                             "passage_excerpt":trace["passage_excerpt"],"canonical_text":hit["chunk"]["text"]})
            matched_ranks=[[hit['rank'] for hit in r['results'] if any(evidence_matches(hit['chunk'],t) for t in g['alternatives'])] for g in q['evidence_groups']]
            case["models"][m]={"top3":rows,"groups_at_5":int(lookup[m,qid]["groups_at_5"]),"required_groups":int(lookup[m,qid]["required_groups"]),
                               'candidate_depth':len(r['results']),'matched_candidate_ranks_by_group':matched_ranks,
                               'complete_in_candidates':all(bool(v) for v in matched_ranks) if q['judgment_mode']=='all' else any(bool(v) for v in matched_ranks)}
        case["reranked_first_complete_rank"]=int(lookup["Dual + reranker",qid]["first_complete_rank"] or 0)
        failures[qid]=case
    for qid in gain:
        assert not failures[qid]['models']['E5']['complete_in_candidates']
        assert all(not r for r in failures[qid]['models']['E5']['matched_candidate_ranks_by_group'])
        assert failures[qid]['models']['Qwen3']['complete_in_candidates']
    complement={}
    e,q=arrays["E5"]["hit"],arrays["Qwen3"]["hit"]
    for name,mask in {"both_hit":(e==1)&(q==1),"E5_only":(e==1)&(q==0),"Qwen3_only":(e==0)&(q==1),"both_miss":(e==0)&(q==0)}.items():
        complement[name]={"n":int(mask.sum()),"query_ids":[qid for qid,keep in zip(ids,mask) if keep]}
    ioc=next(c for c in production['cases'] if c.get('id')=='shine-ioc-startup')
    aliases={'启动时间':['启动时间','startup time'],
             'CA server端口':['server port','服务端口','服务器端口'],
             'CA repeater端口':['repeater port','repeater端口','中继端口']}
    missing=[field for field,variants in aliases.items() if not any(v.casefold() in ioc['response']['answer'].casefold() for v in variants)]
    assert len(missing)==3 and ioc['response']['status']=='answered'
    answered=sum(c.get('answerable',False) and c['response']['status']=='answered' for c in production['cases'])
    internal={'supported':production['requirement_coverage']['supported'],'requirements':production['requirement_coverage']['total'],
              'answered':answered,'audited_counterexample':'shine-ioc-startup','observed_overcomplete_count':1,
              'observed_overcomplete_lower_bound':1/answered,'missing_fields':missing,
              'stored_answer':ioc['response']['answer'],'criterion':'Frozen v2 field inventory; one identified counterexample, not a blind-review prevalence estimate.'}
    grouped={}
    for name,prefix in [('EPICS','epics-'),('European XFEL','european-xfel-'),('SHINE','shine-')]:
        selected=[r for r in corpus if r['document_id'].startswith(prefix)]
        grouped[name]={'documents':len(selected),**{k:sum(int(r[k]) for r in selected) for k in ['pages','canonical_chunks','eligible_chunks']}}
    # Fingerprint every user-specified input, including immutable vector assets.
    for p in sorted((ROOT/"papers/rag-thesis").rglob("*")):
        if p.is_file() and (p.suffix in [".csv",".json",".md",".tex",".latex"] or p.parent.name=="figures"):
            SOURCE_HASHES[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    return {"seed":SEED,"bootstrap_replicates":REPLICATES,"quantile_method":"linear","bootstrap_unit":"paired query",
            "methods":main,"paired":paired,"language":language,"latency":timing,"multi_query_cost":calls,
            "complementarity":complement,"failures":failures,
            "internal_review":internal,"corpus_groups":grouped,
            "annotation":snapshot["audit_summary"],"historical":historical,
            "coverage":{"candidate_parent":rerank['candidate_coverage']['canonical_parent_complete_count'],
                        "scored_passage":rerank['candidate_coverage']['actual_retrieved_passage_complete_count'],
                        "final_parent":rerank['evaluations']['E5 + Qwen3 + Reranker']['metrics']['Hit@5']*len(ids),
                        "final_winning_passage":rerank['final_winning_passage_coverage']['complete_count'],"n":len(ids)},
            "traceability":{"documents":len(corpus),"pages":sum(int(r["pages"]) for r in corpus),"eligible_chunks":sum(int(r["eligible_chunks"]) for r in corpus)},
            "old_pairwise_scope":{"models":[m for m in pairwise_old['models']],"note":"Stage 2.7 has no Qwen3 reranker. E5-vs-reranker pairing uses frozen v2 CSV, not earlier model pairwise counts."},
            "input_sha256":SOURCE_HASHES}


def tex_tables(s):
    names={"BM25":"BM25","BGE-small-zh":"BGE-small-zh","BGE-base-zh":"BGE-base-zh","E5":"E5", "BGE-M3":"BGE-M3", "Qwen3":"Qwen3", "Language router":"语言路由", "Dual RRF":"双模型 RRF", "Dual + reranker":"双模型重排", "E5 + multi-query":"E5 多查询", "Qwen3 + multi-query":"Qwen3 多查询"}
    main=[]
    for name,m in s["methods"].items():
        main.append(names[name]+" & "+" & ".join(f'{m[k]:.3f}' for k in ['Hit@1','Hit@3','Hit@5','MRR@5'])+f" & {m['hit_count']}/21 "+r"\\")
    ci=[]
    for name in ["BM25","E5","Qwen3","Dual + reranker"]:
        m=s['methods'][name];ci.append(names[name]+f" & [{m['hit_ci95'][0]:.3f}, {m['hit_ci95'][1]:.3f}] & [{m['mrr_ci95'][0]:.3f}, {m['mrr_ci95'][1]:.3f}] "+r"\\")
    lang=[]
    for group,label in [('en','英文'),('zh','中文'),('cross_language','跨语言目标')]:
        g=s['language'][group];lang.append(f"{label}（n={g['n']}） & "+' & '.join(f"{g['methods'][m]['hits']}/{g['n']}（{g['methods'][m]['Hit@5']:.3f}）" for m in ['BM25','E5','Qwen3','Dual + reranker'])+r" \\")
    timing=[]
    for group,label in [('all','全部'),('answerable','可回答'),('negative','负例')]:
        t=s['latency'][group];timing.append(f"{label}（n={t['n']}） & "+' & '.join(f'{t[k]:.3f}' for k in ['mean','p50','p95','max'])+r" \\")
    return {name:'\n'.join(rows)+'\n'+r'\bottomrule'+'\n' for name,rows in [
        ('main-results.tex',main),('confidence-intervals.tex',ci),('language.tex',lang),('latency.tex',timing)]}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    s=calculate();serialized=json.dumps(s,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    path=HERE/'data/paper-statistics.json';tables=tex_tables(s)
    if args.check:
        assert path.read_text()==serialized,'Stored analyses differ; run paper_stats.py first'
        for name,value in tables.items():assert (HERE/'tables'/name).read_text()==value,name
        print('PASS: 11 methods, 231 paired rankings, 32 latencies, input hashes unchanged.')
        print(f"PASS: bootstrap B={REPLICATES}, seed={SEED}; McNemar exact p={s['paired']['mcnemar_exact_two_sided_p']:.3f}.")
        print('PASS: paper statistics and four generated LaTeX tables reproduce exactly.')
    else:
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(serialized)
        (HERE/'tables').mkdir(exist_ok=True)
        for name,value in tables.items():(HERE/'tables'/name).write_text(value)
        print(json.dumps({k:s[k] for k in ['paired','language','latency','multi_query_cost']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
