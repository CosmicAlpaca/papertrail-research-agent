"""Replay a candidate-model comparison with cached records, no new inference API.

Development comparison: these queries have been inspected during implementation.
Does not rerun the LLM assessor or establish an independent test-set advantage.
"""
import json
import math
import time
from pathlib import Path
from server.db import Session, Cache
from server.providers import paper_from_openalex
from server.reranker import OnnxReranker
from evaluation.metrics import score

def main():
    root=Path(__file__).parent
    model=OnnxReranker('Alibaba-NLP/gte-reranker-modernbert-base')
    snapshot = root/'replay-candidates.json'
    lookup=json.loads(snapshot.read_text(encoding='utf8')) if snapshot.exists() else {}
    if not lookup:
        with Session() as db:
            for cache in db.query(Cache).all():
                for raw in cache.payload.get('results', []):
                    row=paper_from_openalex(raw)
                    if row['id'] not in lookup or len(row['abstract'])>len(lookup[row['id']]['abstract']): lookup[row['id']]=row
    results=[]
    for path in sorted((root/'results').glob('*.json')):
        row=json.loads(path.read_text(encoding='utf8')); result=row['result']; a=result['ablations']; index=result['candidate_index']
        ids=list(dict.fromkeys(a.get('rrf',[])[:60]+a.get('single_semantic',[])[:20]))
        papers=[lookup.get(id,{'title':index.get(id,{}).get('title',''),'abstract':''}) for id in ids]
        started=time.monotonic()
        values=model.predict([(row['task']['question'],p['title']+'\n'+p['abstract']) for p in papers])
        neural={id:float(value) for id,value in zip(ids,values)}
        ranks={id:rank for rank,id in enumerate(a.get('rrf',[]),1)}
        # Reconstruct RRF magnitudes from stored retrieved records where available.
        # The new-model-only control avoids assuming unavailable legacy RRF values.
        order=sorted(ids,key=lambda id:neural[id],reverse=True)
        order60=[id for id in order if id in set(a.get('rrf',[])[:60])]
        fused={}
        for sequence,weight in [(a.get('single_semantic',[]),2),(a.get('rrf',[]),1),(order,1)]:
            for rank,id in enumerate(sequence,1): fused[id]=fused.get(id,0)+weight/(20+rank)
        fusion=sorted(fused,key=fused.get,reverse=True)
        def titles(sequence): return [lookup.get(id,{}).get('title',index.get(id,{}).get('title','')) for id in sequence]
        item={'id':row['task']['id'],'model':'Alibaba-NLP/gte-reranker-modernbert-base','backend':'ONNX int8 CPU',
              'seconds':round(time.monotonic()-started,2),'candidates':len(ids),
              'same60_neural':score(titles(order60),row['task']['gold_titles']),
              'protected_pool_neural':score(titles(order),row['task']['gold_titles']),
              'rank_fusion':score(titles(fusion),row['task']['gold_titles']),
              'top10':titles(order)[:10]}
        results.append(item)
        (root/'onnx-model-replay.json').write_text(json.dumps(results,indent=2),encoding='utf8')
        print(item['id'],item['same60_neural'],item['protected_pool_neural'],item['seconds'],flush=True)

if __name__=='__main__':main()
