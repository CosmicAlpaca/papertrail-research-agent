"""Known-target retrieval metrics. Unjudged results are not labelled irrelevant.

Matches canonicalized full titles only, not fuzzy/LLM relevance judgments.
This is a diagnostic OpenAlex transfer pilot, not an official LitSearch score.
"""
import json
import re
import statistics
import unicodedata
from pathlib import Path

def canonical(title):
    return re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode().lower())

def score(titles, targets, k=10):
    wanted = {canonical(t) for t in targets}
    seen = set()
    ranks = []
    for rank, title in enumerate(titles[:k], 1):
        name = canonical(title)
        if name in wanted and name not in seen: ranks.append(rank); seen.add(name)
    return {'hit_at_10': int(bool(ranks)), 'target_recall_at_10': len(seen)/len(wanted) if wanted else None,
            'mrr_at_10': 1/min(ranks) if ranks else 0}

def main():
    root = Path(__file__).parent
    rows = []
    for path in sorted((root/'results').glob('*.json')):
        r = json.loads(path.read_text(encoding='utf8'))
        if r['status'] != 'complete': continue
        result = r['result']; index = result.get('candidate_index', {})
        for stage in ['single_semantic', 'rrf', 'rerank', 'final']:
            titles = [p['title'] for p in result['papers']] if stage == 'final' else [index.get(id, {}).get('title', '') for id in result.get('ablations', {}).get(stage, [])]
            rows.append({'task_id': r['task']['id'], 'stage': stage, **score(titles, r['task']['gold_titles']),
                         'seconds': r['end_to_end_seconds'], 'top10': titles[:10]})
    summary = {}
    for stage in ['single_semantic', 'rrf', 'rerank', 'final']:
        group = [r for r in rows if r['stage']==stage]
        if group: summary[stage] = {k: round(statistics.mean(r[k] for r in group), 4) for k in ['hit_at_10','target_recall_at_10','mrr_at_10']}
    report = {'n_completed_queries': len({r['task_id'] for r in rows}), 'selection': 'fixed 8-query pilot; first100 eligible rows, seed20261125',
              'not_claimed': 'Not official LitSearch evaluation. Not precision, nDCG, exhaustive recall, or independent human relevance evaluation.',
              'summary': summary, 'rows': rows}
    (root/'pilot-metrics.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps({k: v for k,v in report.items() if k!='rows'},indent=2))

if __name__ == '__main__': main()
