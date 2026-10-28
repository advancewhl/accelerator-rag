"""Fetch authoritative bibliographic metadata; keep an inspectable local receipt."""
from __future__ import annotations
import concurrent.futures
import html
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request

OUT=Path(__file__).resolve().parents[1]
DOIS={
 'dpr':'10.18653/v1/2020.emnlp-main.550',
 'fid':'10.18653/v1/2021.eacl-main.74',
 'colbert':'10.1145/3397271.3401075',
 'monot5':'10.18653/v1/2020.findings-emnlp.63',
 'bm25':'10.1561/1500000019',
 'rrf':'10.1145/1571941.1572114',
 'alce':'10.18653/v1/2023.emnlp-main.398',
 'ais':'10.1162/coli_a_00486',
 'ragas':'10.18653/v1/2024.eacl-demo.16',
 'ares':'10.18653/v1/2024.naacl-long.20',
 'factscore':'10.18653/v1/2023.emnlp-main.741',
 'lostmiddle':'10.1162/tacl_a_00638',
 'mteb':'10.18653/v1/2023.eacl-main.148',
 'smucker':'10.1145/1321440.1321528',
 'sakai':'10.1145/2911451.2911492',
 'sandve':'10.1371/journal.pcbi.1003285',
 'mcnemar':'10.1007/BF02295996',
 'efron':'10.1214/aos/1176344552',
 'epics':'10.1016/0168-9002(94)91493-1',
 'xfel':'10.3204/DESY_06-097',
 'shinecontrol':'10.18429/JACoW-ICALEPCS2019-WEPHA167',
 'shineioc':'10.18429/JACoW-PCaPAC2022-FRO21',
 'shinecryo':'10.1140/epjti/s40485-021-00066-7',
 'shinefast':'10.11889/j.0253-3219.2024.hjs.47.120203',
 'shinetiming':'10.18429/JACoW-IPAC2022-THIYGD1',
}
ARXIV={
 'rag':('2005.11401','Advances in Neural Information Processing Systems',2020),
 'realm':('2002.08909','Proceedings of the 37th International Conference on Machine Learning',2020),
 'atlas':('2208.03299','Journal of Machine Learning Research',2023),
 'selfrag':('2310.11511','The Twelfth International Conference on Learning Representations',2024),
 'e5':('2402.05672','arXiv',2024),
 'bge':('2309.07597','Proceedings of the 47th International ACM SIGIR Conference on Research and Development in Information Retrieval',2024),
 'bgem3':('2402.03216','arXiv',2024),
 'qwen':('2506.05176','arXiv',2025),
 'hybrid':('2210.11934','arXiv',2022),
 'beir':('2104.08663','Proceedings of the Neural Information Processing Systems Track on Datasets and Benchmarks',2021),
 'attributedqa':('2212.08037','arXiv',2022),
 'hyde':('2212.10496','Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics',2023),
 'query2doc':('2303.07678','Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing',2023),
}
PUBLISHER_RECORDS={
 'xfel':dict(title='XFEL: The European X-Ray Free-Electron Laser -- Technical Design Report',author=['Rafael Abela','A. Aghababyan','Massimo Altarelli','others'],year=2006,venue='DESY',type='report',pages='1--646',source_url='https://bib-pubdb1.desy.de/record/77248'),
 'shinecontrol':dict(title='Status of the SHINE Control System',author=['Yingbing Yan','Jianguo Ding','J. F. Chen','Guanghua Chen','others'],year=2019,venue='Proceedings of the 17th International Conference on Accelerator and Large Experimental Physics Control Systems',type='proceedings-article',pages='1481--1484',source_url='https://proceedings.jacow.org/icalepcs2019/papers/wepha167.pdf'),
 'shineioc':dict(title='EPICS IOC and PVs Information Management System for SHINE',author=['Huihui Lv','Yingbing Yan','Qingru Mi','Guanghua Chen'],year=2023,venue='Proceedings of the 13th International Workshop on Emerging Technologies and Scientific Facilities Controls',type='proceedings-article',pages='107--109',source_url='https://proceedings.jacow.org/pcapac2022/papers/fro21.pdf'),
 'shinetiming':dict(title='White Rabbit Based Beam-Synchronous Timing Systems for SHINE',author=['Yingbing Yan','P. X. Yu','Guanghua Chen','Qingwen Xiao','others'],year=2022,venue='Proceedings of the 13th International Particle Accelerator Conference',type='proceedings-article',pages='2415--2419',source_url='https://proceedings.jacow.org/ipac2022/papers/thiygd1.pdf'),
 'shinefast':dict(title='SHINE加速器快联锁系统设计与开发',author=['于春蕾','陈广花','丁建国','李明','肖庆雯','阎映炳'],year=2024,venue='核技术',type='journal-article',volume='47',number='12',pages='120203',source_url='https://doi.org/10.11889/j.0253-3219.2024.hjs.47.120203'),
}


def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'RAG-paper-reference-audit/1.0'})
    with urllib.request.urlopen(req,timeout=35) as r:return r.read().decode('utf8')


def fetch(item):
    key,kind,value=item;cache=OUT/'data/reference-metadata'/f'{key}.json'
    if cache.exists():return key,json.loads(cache.read_text())
    if key in PUBLISHER_RECORDS:
        record=dict(PUBLISHER_RECORDS[key],key=key,kind=kind,doi=value,
                    verification='Publisher primary record / original PDF; not registered in Crossref')
    elif kind=='doi':
        url='https://api.crossref.org/works/'+urllib.parse.quote(value,safe='')
        x=json.loads(get(url))['message']
        year=(x.get('published',x.get('issued',{})).get('date-parts') or [[0]])[0][0]
        title=': '.join(x['title'][:1]+x.get('subtitle',[])[:1])
        record={'key':key,'kind':kind,'doi':value,'title':html.unescape(re.sub('<[^>]+>','',title)),
                'author':[a.get('given','')+' '+a.get('family',a.get('name','')) for a in x.get('author',[])],
                'year':year,'venue':(x.get('container-title') or [''])[0],
                'volume':x.get('volume',''),'number':x.get('issue',''),'pages':x.get('page',x.get('article-number','')),
                'type':x.get('type'),'source_url':url,'landing_url':x.get('URL','')}
    else:
        arxiv,venue,year=value;url='https://arxiv.org/abs/'+arxiv;page=get(url)
        def tags(name):return [html.unescape(t) for t in re.findall(r'<meta\s+name="'+name+r'"\s+content="([^"]+)"',page)]
        record={'key':key,'kind':kind,'arxiv':arxiv,'doi':'10.48550/arXiv.'+arxiv,
                'title':tags('citation_title')[0],'author':tags('citation_author'),'year':year,
                'venue':venue,'source_url':url,'landing_url':url}
    assert record['title'] and record['author'],record
    cache.parent.mkdir(parents=True,exist_ok=True);cache.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    return key,record


def esc(s):
    return str(s).replace('&',r'\&').replace('%',r'\%').replace('_',r'\_').replace('#',r'\#')


def main():
    items=[(k,'doi',v) for k,v in DOIS.items()]+[(k,'arxiv',v) for k,v in ARXIV.items()]
    records={};errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(fetch,i):i[0] for i in items}
        for f in concurrent.futures.as_completed(futures):
            try:k,r=f.result();records[k]=r;print(k,r['year'],r['title'][:90],flush=True)
            except Exception as e:errors.append((futures[f],str(e)));print('FAILED',futures[f],str(e),flush=True)
    if errors:raise RuntimeError(errors)
    entries=[]
    for key in [i[0] for i in items]:
        r=records[key]
        if r['kind']=='arxiv':kind='article' if r['venue'] in ['arXiv','Journal of Machine Learning Research'] else 'inproceedings'
        else:kind='inproceedings' if r['type']=='proceedings-article' else 'techreport' if key=='xfel' else 'article'
        fields={'author':' and '.join(r['author']), 'title':'{'+r['title']+'}', 'year':r['year'],
                'booktitle' if kind=='inproceedings' else 'institution' if kind=='techreport' else 'journal':r['venue'] or ('DESY' if key=='xfel' else 'arXiv'),
                'doi':r['doi']}
        if r.get('arxiv'):fields.update(eprint=r['arxiv'],archivePrefix='arXiv',url=r['landing_url'])
        for f in ['volume','number','pages']:
            if r.get(f):fields[f]=r[f]
        if key=='atlas':fields.update(volume='24',number='251',pages='1--43')
        entries.append('@'+kind+'{'+key+',\n'+',\n'.join('  '+k+' = {'+(v if k in ['doi','url'] else esc(v))+'}' for k,v in fields.items())+'\n}')
    entries.append('@manual{epicsdocs,\n  author = {{EPICS Collaboration}},\n  title = {{EPICS Application Developer\'s Guide, Release 3.16.2}},\n  year = {2018},\n  url = {https://epics.anl.gov/base/R3-16/2-docs/AppDevGuide.pdf},\n  note = {Accessed 2026-10-27}\n}')
    records['epicsdocs']={'kind':'manual','source_url':'https://epics.anl.gov/base/R3-16/2-docs/AppDevGuide.pdf','verification':'Official EPICS URL and locally registered PDF; release identity R3.16.2'}
    (OUT/'refs.bib').write_text('\n\n'.join(entries)+'\n')
    (OUT/'data/reference-verification.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    print('TOTAL',len(entries))


if __name__=='__main__':main()
