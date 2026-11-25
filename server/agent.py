"""Bounded, observable LangGraph paper-finding workflow."""
import math
import re
import time
from collections import defaultdict
from threading import Lock, Thread
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from server.config import settings
from server.db import event, update_run
from server import providers, llm

_model = None
_model_lock = Lock()
_inference_lock = Lock()
_warming = False

def warm_reranker():
    global _warming
    if not settings.reranker_enabled or _model is not None or _warming: return
    _warming = True
    def load():
        global _model, _warming
        try:
            if settings.reranker_backend == 'onnx':
                from server.reranker import OnnxReranker
                with _model_lock: _model = OnnxReranker(settings.reranker_model, settings.reranker_revision)
            else:
                from sentence_transformers import CrossEncoder
                with _model_lock: _model = CrossEncoder(settings.reranker_model, max_length=512, device='cpu')
        except Exception:
            pass
        finally: _warming = False
    Thread(target=load, daemon=True).start()

def neural_scores(query, papers):
    if _model is None:
        warm_reranker()
        return None
    with _inference_lock:
        values = _model.predict([(query, p['title'] + '\n' + p.get('abstract', '')) for p in papers], batch_size=4)
    values = [float(x) for x in values]
    return values if len(values) == len(papers) and all(math.isfinite(x) for x in values) else None

def normalize_title(title):
    return re.sub(r'[^\w]+', ' ', title.casefold()).strip()

def merge_papers(lists):
    merged, doi_map, title_map = {}, {}, {}
    for label, papers in lists:
        for rank, p in enumerate(papers, 1):
            doi = (p.get('doi') or '').lower().replace('https://doi.org/', '').strip()
            title = normalize_title(p['title'])
            canonical = doi_map.get(doi) if doi else None
            canonical = canonical or (title_map.get(title) if len(title) > 20 else None) or p['id']
            if canonical not in merged:
                merged[canonical] = {**p, 'rrf': 0.0, 'provenance': [], 'aliases': []}
            row = merged[canonical]
            row['rrf'] += 1 / (60 + rank)
            if label not in row['provenance']: row['provenance'].append(label)
            if p['id'] not in row['aliases']: row['aliases'].append(p['id'])
            if len(p.get('abstract', '')) > len(row.get('abstract', '')): row['abstract'] = p['abstract']
            if doi: doi_map[doi] = canonical
            if len(title) > 20: title_map[title] = canonical
    return sorted(merged.values(), key=lambda p: p['rrf'], reverse=True)

def metadata_allowed(paper, plan):
    year = paper.get('year')
    if plan.get('year_from') and (year is None or year < plan['year_from']): return False
    if plan.get('year_to') and (year is None or year > plan['year_to']): return False
    return not paper.get('retracted') and (not plan.get('open_access') or paper.get('open_access'))

def validate_judgments(papers, criteria, raw):
    """A model cannot manufacture evidence. Quote presence is checked independently.

    Quote presence validates attribution, not logical entailment; UI says so.
    """
    judgments = raw.get('judgments')
    if not isinstance(judgments, list): judgments = []
    lookup = {(x.get('paper_id'), x.get('criterion_id')): x for x in judgments if isinstance(x, dict) and isinstance(x.get('paper_id'), str) and isinstance(x.get('criterion_id'), str)}
    for paper in papers:
        evidence = re.sub(r'\s+', ' ', paper['title'] + ' ' + paper.get('abstract', '')).strip()
        paper['criteria'] = []
        for criterion in criteria:
            row = lookup.get((paper['id'], criterion['id']), {})
            status = row.get('status', 'uncertain')
            quote = re.sub(r'\s+', ' ', str(row.get('quote') or '')).strip()[:700]
            verified = len(quote) >= 15 and quote.casefold() in evidence.casefold()
            if status not in {'supported', 'contradicted', 'uncertain'} or (status != 'uncertain' and not verified):
                status = 'uncertain'
            paper['criteria'].append({'criterion_id': criterion['id'], 'status': status,
                'quote': quote if verified else '', 'quote_verified': verified,
                'reason': str(row.get('reason', 'No sufficient evidence assessed in the available metadata.'))[:350]
                          if verified else 'Insufficient source evidence; full-paper verification may be needed.'})
    return papers

class State(TypedDict, total=False):
    run_id: str
    request: dict
    lists: list
    papers: list
    usage: dict
    warnings: list
    repaired: bool
    ranker: str
    gaps: list
    ablations: dict
    joint_gap: bool
    candidate_index: dict

def retrieve(state: State):
    plan = state['request']['plan']
    state.update(lists=[], papers=[], usage={'api_calls': 0, 'cache_hits': 0, 'llm_calls': 0}, warnings=[], repaired=False, ablations={}, candidate_index={})
    for i, query in enumerate(plan['queries']):
        for semantic in [False, True]:
            if state['usage']['api_calls'] >= settings.max_api_calls: break
            try:
                search_query = plan['question'] if semantic and i == 0 else query
                rows, hit = providers.search(search_query, plan, semantic)
                state['usage']['cache_hits' if hit else 'api_calls'] += 1
                label = f"{'semantic' if semantic else 'keyword'}: {search_query}"
                state['lists'].append((label, rows))
                if semantic and i == 0:
                    state['ablations']['single_semantic'] = [p['id'] for p in rows]
                state['candidate_index'].update({p['id']: {'title': p['title'], 'year': p.get('year')} for p in rows})
                event(state['run_id'], 'retrieve', f"{len(rows)} candidates from {'semantic' if semantic else 'keyword'} search", query=search_query, cache_hit=hit)
            except Exception as exc:
                state['usage']['api_calls'] += 1
                state['warnings'].append(str(exc))
                event(state['run_id'], 'retrieve', 'Provider call failed; other searches will continue', error=str(exc))
    return state

def rank(state: State):
    plan = state['request']['plan']
    papers = [p for p in merge_papers(state['lists']) if metadata_allowed(p, plan)]
    bounded = papers[:60]
    # Protect the semantic channel from being truncated away by repeated keyword
    # hits, while keeping the expensive cross-encoder stage at <=80 candidates.
    semantic_ids = set(state['ablations'].get('single_semantic', [])[:20])
    present = {p['id'] for p in bounded}
    bounded.extend(p for p in papers if p['id'] not in present and semantic_ids.intersection(p.get('aliases', [p['id']])))
    try: scores = neural_scores(plan['question'], bounded) if state['request']['rerank'] and bounded else None
    except Exception: scores = None
    highest = max((p['rrf'] for p in bounded), default=1)
    for i, p in enumerate(bounded):
        p['neural_score'] = round(scores[i], 5) if scores else None
        # RRF selects candidates; raw neural logits order them. Mixing an
        # uncalibrated sigmoid with a different score scale can reverse relevance.
        p['score'] = round(scores[i], 5) if scores else round(p['rrf'] / highest, 5)
    state['ranker'] = 'cross-encoder + RRF candidates' if scores else 'RRF only (neural model warming or unavailable)'
    state['papers'] = sorted(bounded, key=lambda p: (p['score'], p['rrf']), reverse=True)
    if not state['repaired']:
        state['ablations'].update(rrf=[p['id'] for p in bounded], rerank=[p['id'] for p in state['papers']])
    state['candidate_index'].update({p['id']: {'title': p['title'], 'year': p.get('year')} for p in bounded})
    event(state['run_id'], 'rank', f"Ranked {len(bounded)} unique candidates", ranker=state['ranker'])
    return state

def explore(state: State):
    if state['request']['plan']['mode'] == 'fast' or not state['papers'] or state['usage']['api_calls'] >= settings.max_api_calls: return state
    refs = []
    for p in state['papers'][:3]: refs.extend(p.get('references', [])[:6])
    try:
        rows, hit = providers.citation_neighbors(list(dict.fromkeys(refs)))
        state['usage']['cache_hits' if hit else 'api_calls'] += 1
        state['lists'].append(('citation neighbors of top-ranked papers', rows))
        event(state['run_id'], 'citations', f'Explored {len(rows)} cited works; metadata constraints remain enforced')
        rank(state)
    except Exception as exc:
        state['usage']['api_calls'] += 1; state['warnings'].append(str(exc))
    return state

def assess(state: State):
    criteria = state['request']['plan']['criteria']
    papers = state['papers'][:15]
    if criteria and settings.llm_api_key:
        for start in range(0, len(papers), 5):
            try:
                event(state['run_id'], 'evidence', f'Checking source evidence for candidates {start+1}–{min(start+5, len(papers))}')
                batch = [{**p, 'abstract': p.get('abstract', '')[:2400]} for p in papers[start:start+5]]
                raw = llm.judge(batch, criteria)
                state['usage']['llm_calls'] += raw.get('_attempts', 1)
                models = state['usage'].setdefault('models_used', [])
                if raw.get('_model') and raw['_model'] not in models: models.append(raw['_model'])
                validate_judgments(papers[start:start+5], criteria, raw)
            except llm.LLMUnavailable as exc:
                state['usage']['llm_calls'] += exc.attempts
                state['warnings'].append(str(exc))
                validate_judgments(papers[start:start+5], criteria, {})
    else:
        validate_judgments(papers, criteria, {})
        if criteria: state['warnings'].append('Hosted LLM unavailable: content criteria remain uncertain, not automatically satisfied.')
    gaps = [c for c in criteria if not any(any(j['criterion_id'] == c['id'] and j['status'] == 'supported' for j in p['criteria']) for p in papers)]
    state['gaps'] = gaps
    state['joint_gap'] = bool(criteria) and not any(all(j['status'] == 'supported' for j in p['criteria']) for p in papers)
    event(state['run_id'], 'evidence', f"Assessed top {len(papers)} papers; {len(gaps)} criteria have no supported match", evidence_basis='title and abstract only')
    return state

def repair_route(state):
    return 'repair' if state['request']['repair'] and state['request']['plan']['mode'] == 'diligent' and (state.get('gaps') or state.get('joint_gap')) and not state['repaired'] and state['usage']['api_calls'] < settings.max_api_calls else 'finish'

def repair(state):
    state['repaired'] = True
    plan = state['request']['plan']
    targets = state['gaps'][:2] or [{'id': 'joint', 'text': 'a single paper satisfying all reviewed criteria together'}]
    for criterion in targets:
        if state['usage']['api_calls'] >= settings.max_api_calls: break
        query = (plan['queries'][0] + ' ' + (' '.join(c['text'] for c in plan['criteria']) if criterion['id'] == 'joint' else criterion['text']))[:300]
        try:
            rows, hit = providers.search(query, plan, True)
            state['usage']['cache_hits' if hit else 'api_calls'] += 1
            state['lists'].append((f"coverage repair: {criterion['text']}", rows))
            event(state['run_id'], 'repair', f"Targeted a criterion with no supported match: {criterion['text']}", query=query, candidates=len(rows))
        except Exception as exc:
            state['usage']['api_calls'] += 1; state['warnings'].append(str(exc))
    rank(state)
    return state

def finish(state):
    ranked = state['papers']
    # Explicit counter-evidence should not be hidden beneath a similarity score.
    # Missing evidence stays separate from a supported match; none are excluded.
    def evidence_group(p):
        rows = p.get('criteria', [])
        if any(c['status'] == 'contradicted' for c in rows): return 2
        if rows and all(c['status'] == 'supported' for c in rows): return 0
        return 1
    if state['request']['plan']['criteria']:
        ranked = sorted(ranked, key=evidence_group)
    papers = ranked[:30]
    alias_map = {alias: p['id'] for p in papers for alias in p.get('aliases', [p['id']])}
    edges = []
    for p in papers:
        for ref in p.get('references', []):
            if ref in alias_map and alias_map[ref] != p['id']:
                edges.append({'source': p['id'], 'target': alias_map[ref]})
    result = {'papers': papers, 'usage': state['usage'], 'ranker': state['ranker'], 'gaps': state['gaps'],
              'repaired': state['repaired'], 'warnings': list(dict.fromkeys(state['warnings'])),
              'citation_edges': edges, 'evidence_basis': 'Title and abstract; no full text read',
              'ablations': state['ablations'],
              'candidate_index': state['candidate_index'],
              'ordering': 'All criteria supported, then incomplete evidence, then explicit counter-evidence; similarity breaks ties',
              'joint_gap': state.get('joint_gap', False),
              'model': settings.llm_model if settings.llm_api_key else None,
              'reranker_model': settings.reranker_model, 'reranker_backend': settings.reranker_backend}
    update_run(state['run_id'], status='complete', result=result)
    event(state['run_id'], 'complete', f"Returned {len(papers)} papers with provenance and exportable evidence")
    return state

builder = StateGraph(State)
for name, node in [('retrieve', retrieve), ('rank', rank), ('explore', explore), ('assess', assess), ('repair', repair), ('finish', finish)]:
    builder.add_node(name, node)
builder.add_edge(START, 'retrieve'); builder.add_edge('retrieve', 'rank'); builder.add_edge('rank', 'explore')
builder.add_edge('explore', 'assess'); builder.add_conditional_edges('assess', repair_route)
builder.add_edge('repair', 'assess'); builder.add_edge('finish', END)
graph = builder.compile()

def execute(run_id, request):
    update_run(run_id, status='running')
    started = time.monotonic()
    try:
        graph.invoke({'run_id': run_id, 'request': request}, {'recursion_limit': 20})
        event(run_id, 'timing', 'Search finished', elapsed_seconds=round(time.monotonic()-started, 2))
    except Exception as exc:
        update_run(run_id, status='failed', result={'error': 'Search did not finish. Please retry or narrow the query.'})
        event(run_id, 'failed', 'Search failed', error=type(exc).__name__)
