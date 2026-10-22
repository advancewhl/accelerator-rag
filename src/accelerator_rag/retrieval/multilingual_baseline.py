"""Stage 2.8: frozen corpus, local-only strong multilingual dense comparison."""
import gc
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from time import perf_counter

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from qdrant_client import QdrantClient
from accelerator_rag.embedding import EmbeddingModel, document_embedding_text
from accelerator_rag.ingestion import IngestionService
from accelerator_rag.corpus.eligibility import eligibility_audit
from accelerator_rag.evaluation.retrieval import evaluate, load_queries, target_matches
from accelerator_rag.retrieval.dense import DenseRetriever
from accelerator_rag.retrieval.index_contract import DenseIndexContract
from accelerator_rag.retrieval.passages import PassageBuilder, passage_statistics
from accelerator_rag.storage.qdrant_passages import QdrantPassageStore

MODELS = ['BAAI/bge-m3', 'Qwen/Qwen3-Embedding-0.6B']
FOCUS = ['xfel-normal-energy', 'shine-ioc-startup', 'cryo-interlock']
E5 = 'intfloat/multilingual-e5-base'
REPORT = 'rag-stage-two-eight-multilingual-retrieval'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def diagnose(retriever, queries):
    rows = []
    for q in queries:
        if q.id not in FOCUS:
            continue
        hits = retriever.search(q.query, top_k=10)
        satisfied, ranks, first = set(), {}, None
        details = []
        for r in hits:
            groups = [i+1 for i, g in enumerate(q.evidence_groups)
                      if any(target_matches(r.chunk, t) for t in g.alternatives)]
            satisfied.update(groups)
            if len(satisfied) == len(q.evidence_groups) and first is None:
                first = r.rank
            ranks[r.rank] = len(satisfied)
            details.append({'rank': r.rank, 'document': r.chunk.document_id,
                            'title': r.chunk.document_title,
                            'physical_page_start': r.chunk.page_start,
                            'physical_page_end': r.chunk.page_end,
                            'score': r.score, 'parent_id': r.chunk.chunk_id,
                            'matched_evidence_groups': groups})
        rows.append({'id': q.id, 'required_groups': len(q.evidence_groups),
                     'groups_at5': ranks.get(5, len(satisfied)),
                     'groups_at10': len(satisfied), 'first_complete_rank': first,
                     'complete_at5': first is not None and first <= 5,
                     'top10': details})
    return rows


def render(result, root):
    lines = ['# Stage 2.8：多语言 Dense 检索实验', '',
             '状态：' + result['status'] + '。冻结 evidence-contract-v2，Top-5 正式评估。', '',
             '| Method | Hit@1 | Hit@3 | Hit@5 | MRR@5 |',
             '| --- | ---: | ---: | ---: | ---: |']
    for name, row in result['models'].items():
        m = row['evaluation']['metrics']
        lines.append('| ' + name + ' | ' + ' | '.join(f'{m[k]:.4f}' for k in ['Hit@1','Hit@3','Hit@5','MRR@5']) + ' |')
    lines += ['', '| Method | normal-energy | ioc-startup | cryo-interlock |', '| --- | --- | --- | --- |']
    for name, row in result['models'].items():
        cells = []
        for ident in FOCUS:
            c = next(c for c in row['evaluation']['cases'] if c['id'] == ident)
            cells.append('complete' if c['first_complete_rank'] else f"{c['groups_satisfied_at_k']['5']}/{len(c['evidence_groups'])} groups")
        lines.append('| ' + name + ' | ' + ' | '.join(cells) + ' |')
    if result.get('decision'):
        lines += ['', result['decision']]
    for exc in result['failures']:
        lines += ['', f"执行失败：{exc['model']}，{exc['error']}。"]
    for name, row in result['models'].items():
        if 'fingerprint' not in row:
            continue
        fp, stats = row['fingerprint'], row['passage_statistics']
        lines += ['', f"## {name}", '',
                  f"本地 revision：`{row['resolved_revision']}`。模型文件：{fp['local_model_bytes']} bytes。",
                  f"上下文：{fp['max_seq_length']} tokens。Passage：{stats['embedding_passages']}。静默截断：0。",
                  f"权重清单 SHA256：`{fp['weights_manifest_sha256']}`。完整文件哈希见 JSON。",
                  f"编码耗时：{row['timing']['embedding_seconds']:.1f} s。", '',
                  f"[官方模型卡](https://huggingface.co/{name})。本次使用下载到本地的模型卡与 pooling 配置。"]
        for d in row['cross_language_diagnosis']:
            lines += ['', f"### {d['id']}", '',
                      f"证据组：Top-5 为 {d['groups_at5']}/{d['required_groups']}，Top-10 为 {d['groups_at10']}/{d['required_groups']}。首次完整排名：{d['first_complete_rank']}。", '',
                      '| Rank | Document | Physical page | Score | Groups |', '| ---: | --- | --- | ---: | --- |']
            for h in d['top10']:
                lines.append(f"| {h['rank']} | {h['document']} | {h['physical_page_start']}–{h['physical_page_end']} | {h['score']:.6f} | {h['matched_evidence_groups']} |")
    (root/'reports'/f'{REPORT}.md').write_text('\n'.join(lines)+'\n')
    write(root/'reports'/f'{REPORT}.json', result)


def run():
    import torch
    torch.set_num_threads(6)
    root = Path.cwd()
    work = root/'tmp/stage-two-eight'
    baseline = json.loads((root/'reports/rag-stage-two-seven-one-evidence-audit.json').read_text())
    query_path = root/'data/evaluation/retrieval_baseline.json'
    frozen_paths = [query_path] + [root/'src/accelerator_rag'/p for p in [
        'corpus/chunking.py','corpus/cleaning.py','corpus/eligibility.py',
        'domain/knowledge.py','retrieval/passages.py','retrieval/dense.py',
        'retrieval/index_contract.py','evaluation/retrieval.py']]
    hashes = {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest() for p in frozen_paths}
    docs = IngestionService(root).ingest_all_registered_pdfs()
    eligible, policy = eligibility_audit([c for d in docs for c in d.chunks])
    assert len(docs) == 13 and len(eligible) == 4532
    assert json.loads(query_path.read_text())['judgment_revision'] == 'evidence-contract-v2'
    queries = load_queries(query_path, docs, eligible_chunks=eligible)
    history = json.loads((root/'reports/rag-stage-two-seven-embedding-comparison.json').read_text())
    sources = {d.record.source_path: sha256((root/d.record.source_path).read_bytes()).hexdigest() for d in docs}
    assert sources == history['metadata']['source_sha256']
    parent_hash = sha256(json.dumps([asdict(c) for c in eligible], sort_keys=True).encode()).hexdigest()
    assert parent_hash == history['metadata']['canonical_parent_sha256']
    result = {'status':'RUNNING','started_at': datetime.now(timezone.utc).isoformat(),
              'judgment_revision':'evidence-contract-v2','frozen_sha256':hashes,
              'source_sha256':sources,'canonical_parent_sha256':parent_hash,
              'eligible_parents':len(eligible),'pdf_count':len(docs),
              'distance':'cosine','aggregation':'max-child','device':'cpu',
              'models':{E5:{'evaluation':baseline['rejudged'][E5], 'reused_stage271':True}},'failures':[]}
    previous_path = root/'reports'/f'{REPORT}.json'
    if previous_path.exists():
        previous = json.loads(previous_path.read_text())
        assert previous['frozen_sha256'] == hashes
        assert previous['canonical_parent_sha256'] == parent_hash
        for name, row in previous['models'].items():
            if name != E5 and row.get('evaluation'):
                result['models'][name] = row
    render(result, root)
    for name in MODELS:
        if name in result['models']:
            print('REUSE COMPLETED EVALUATION',name,flush=True)
            continue
        client = embedder = dense = builder = store = passages = expected = existing = None
        try:
            print('LOAD', name, flush=True)
            local = work/'models'/name.replace('/','--')
            embedder = EmbeddingModel(name, model_path=str(local), batch_size=8)
            fp = embedder.fingerprint()
            builder = PassageBuilder(embedder)
            passages = builder.build(eligible)
            stats = passage_statistics(passages, builder)
            print('PASSAGES', name, stats['embedding_passages'], stats['model_max_seq_length'], flush=True)
            contract = DenseIndexContract.from_fingerprint(fp,builder.contract)
            slug = 'bge_m3' if name == MODELS[0] else 'qwen3_embedding_0_6b_fp32'
            path = work/slug
            path.mkdir(exist_ok=True)
            provenance = json.loads((local/'weights-download-provenance.json').read_text())
            receipt = local/'.cache/huggingface/download/config.json.metadata'
            assert provenance['revision'] == receipt.read_text().splitlines()[0]
            assert provenance['sha256'] in fp['weights_files'].values()
            write(path/'model-identity.json', {'fingerprint':fp,
                  'download':provenance,'passage_contract':builder.contract})
            client = QdrantClient(path=str(path/'qdrant'))
            store = QdrantPassageStore(client, 'knowledge_stage28_'+slug, contract)
            dense = DenseRetriever(embedder, store, passage_builder=builder)
            # Durable per-batch vectors allow interrupted experiments to resume without re-embedding.
            started = perf_counter()
            existing = {p.passage_id:p for p in store.all_passages()}
            expected = {p.passage_id:p for p in passages}
            if any(expected.get(k) != v for k,v in existing.items()):
                raise ValueError('existing index passage mismatch')
            remaining = sorted((p for p in passages if p.passage_id not in existing),
                               key=lambda p:(p.token_count,p.passage_id))
            embedding_seconds = indexing_seconds = 0.0
            for start in range(0,len(remaining),8):
                batch = remaining[start:start+8]
                before = perf_counter()
                vectors = embedder.embed_token_safe_documents([document_embedding_text(p) for p in batch])
                embedding_seconds += perf_counter()-before
                before = perf_counter()
                store.upsert_passages(batch,vectors)
                indexing_seconds += perf_counter()-before
                if start % 96 == 0:
                    print('INDEX',name,len(existing)+start+len(batch),'/',len(passages),'seconds',round(perf_counter()-started,1),flush=True)
            assert {p.passage_id:p for p in store.all_passages()} == expected
            timing = {'embedding_seconds':embedding_seconds,
                      'qdrant_indexing_seconds':indexing_seconds,
                      'index_wall_seconds':perf_counter()-started,
                      'previously_indexed':len(existing),'batch_size':8,'torch_threads':6}
            client.close()
            client = QdrantClient(path=str(path/'qdrant'))
            store = QdrantPassageStore(client,'knowledge_stage28_'+slug,contract)
            dense = DenseRetriever(embedder,store,passage_builder=builder)
            ev = evaluate(dense,queries)
            diag = diagnose(dense,queries)
            receipt = local/'.cache/huggingface/download/config.json.metadata'
            row = {'fingerprint':fp,'resolved_revision':receipt.read_text().splitlines()[0],
                   'download_provenance':provenance,
                   'runtime_dtype':str(next(embedder._model.parameters()).dtype),
                   'encoding_contract_source':{'url':'https://huggingface.co/'+name,
                       'local_card_sha256':sha256((local/'README.md').read_bytes()).hexdigest(),
                       'pooling_config':json.loads((local/'1_Pooling/config.json').read_text())},
                   'passage_statistics':stats,'collection':store.collection_name if hasattr(store,'collection_name') else 'knowledge_stage28_'+slug,
                   'index_path':str(path/'qdrant'),'timing':timing,'evaluation':ev,'cross_language_diagnosis':diag}
            result['models'][name] = row
            print('RESULT',name,ev['metrics'],diag and [(d['id'],d['groups_at5']) for d in diag],flush=True)
            render(result,root)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            result['failures'].append({'model':name,'error':str(exc),'type':type(exc).__name__})
            render(result,root)
        finally:
            if client:
                client.close()
            client = embedder = dense = builder = store = passages = expected = existing = None
            gc.collect()
    for p in frozen_paths:
        assert hashes[str(p.relative_to(root))] == sha256(p.read_bytes()).hexdigest()
    candidates = {n:r for n,r in result['models'].items() if n != E5}
    successful = [n for n,r in candidates.items() if sum(d['complete_at5'] for d in r['cross_language_diagnosis']) >= 2 and r['evaluation']['metrics']['Hit@5'] >= 18/21]
    if successful:
        best = max(successful,key=lambda n:(candidates[n]['evaluation']['metrics']['Hit@5'],candidates[n]['evaluation']['metrics']['MRR@5']))
        result['decision'] = f'推荐 Dense 模型：{best}。达到预定升级标准，停止 decomposition。下一步：A，进入 RAG answer generation。'
    else:
        result['multi_query_required'] = len(candidates)==2 and all(sum(d['complete_at5'] for d in r['cross_language_diagnosis']) < 2 for r in candidates.values())
    result['status'] = 'EXECUTED' if len(candidates)==2 else 'PARTIAL'
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    render(result,root)
    return result

if __name__ == '__main__':
    run()
