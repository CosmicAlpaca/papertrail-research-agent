import hashlib
import json
import re
import time
from threading import Lock
import httpx
from sqlalchemy.exc import IntegrityError
from server.config import settings
from server.db import Session, Cache

_rate_lock = Lock()
_last_semantic = 0.0
FIELDS = 'id,title,doi,publication_year,authorships,primary_location,open_access,best_oa_location,cited_by_count,abstract_inverted_index,referenced_works,type,is_retracted'

def abstract_text(index):
    if not isinstance(index, dict): return ''
    words = {}
    for word, positions in index.items():
        if not isinstance(word, str) or not isinstance(positions, list): continue
        for p in positions:
            if isinstance(p, int) and not isinstance(p, bool) and 0 <= p < 10000:
                words[p] = word
    return ' '.join(words[i] for i in sorted(words))

def paper_from_openalex(item):
    location = item.get('primary_location') or {}
    best = item.get('best_oa_location') or {}
    source = location.get('source') or {}
    return {'id': item['id'], 'title': item.get('title') or 'Untitled', 'doi': item.get('doi'),
            'year': item.get('publication_year'), 'abstract': abstract_text(item.get('abstract_inverted_index')),
            'authors': [a.get('author', {}).get('display_name', '') for a in item.get('authorships', [])[:15]],
            'venue': source.get('display_name'), 'citations': item.get('cited_by_count', 0),
            'open_access': bool((item.get('open_access') or {}).get('is_oa')),
            'url': item.get('doi') or location.get('landing_page_url') or item['id'],
            'pdf_url': best.get('pdf_url'), 'references': item.get('referenced_works', [])[:40],
            'retracted': bool(item.get('is_retracted')), 'provenance': [], 'criteria': []}

def request_openalex(params):
    global _last_semantic
    key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    with Session() as db:
        cached = db.get(Cache, key)
        if cached and time.time() - cached.created_at < 86400:
            return cached.payload, True
    if 'search.semantic' in params:
        with _rate_lock:
            delay = 1.05 - (time.monotonic() - _last_semantic)
            if delay > 0: time.sleep(delay)
            _last_semantic = time.monotonic()
    headers = {'User-Agent': 'PaperTrail/0.1 scholarly research prototype'}
    if settings.openalex_api_key: headers['Authorization'] = 'Bearer ' + settings.openalex_api_key
    with httpx.Client(timeout=35) as client:
        response = client.get('https://api.openalex.org/works', params=params, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(f'OpenAlex returned HTTP {response.status_code}')
        payload = response.json()
    with Session() as db:
        cached = db.get(Cache, key)
        if cached:
            cached.payload = payload; cached.created_at = time.time()
        else: db.add(Cache(key=key, payload=payload))
        try: db.commit()
        except IntegrityError:
            # Another search may have filled this cache key concurrently.
            db.rollback()
    return payload, False

def search(query, plan, semantic=False):
    filters = ['is_retracted:false']
    if plan.get('year_from') and plan.get('year_to'):
        filters.append(f"publication_year:{plan['year_from']}-{plan['year_to']}")
    elif plan.get('year_from'): filters.append(f"publication_year:>{plan['year_from']-1}")
    elif plan.get('year_to'): filters.append(f"publication_year:<{plan['year_to']+1}")
    if plan.get('open_access'): filters.append('open_access.is_oa:true')
    params = {'search.semantic' if semantic else 'search': query, 'per-page': 40, 'filter': ','.join(filters), 'select': FIELDS}
    payload, hit = request_openalex(params)
    return [paper_from_openalex(x) for x in payload.get('results', [])], hit

def citation_neighbors(ids):
    normalized = [x.rsplit('/', 1)[-1] for x in ids if re.fullmatch(r'https://openalex.org/W\d+', x)][:20]
    if not normalized: return [], False
    payload, hit = request_openalex({'filter': 'openalex:' + '|'.join(normalized) + ',is_retracted:false', 'per-page': 20, 'select': FIELDS})
    return [paper_from_openalex(x) for x in payload.get('results', [])], hit
