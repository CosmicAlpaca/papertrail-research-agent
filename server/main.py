import csv
import hmac
import io
import json
import re
import secrets
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from threading import Lock
from uuid import uuid4
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from server.config import ROOT, settings
from server.db import Base, engine, Session, Workspace, Run, token_hash
from server.schemas import PlanRequest, Plan, Criterion, SearchRequest, Feedback
from server import agent, llm
from server import grounded_chat

executor = ThreadPoolExecutor(max_workers=2)
limits = defaultdict(deque)
limit_lock = Lock()

def rate_limit(key, count=20, window=3600):
    with limit_lock:
        q = limits[key]; stamp = time.monotonic()
        while q and stamp-q[0] > window: q.popleft()
        if len(q) >= count: raise HTTPException(429, 'Research budget reached. Please try again later.')
        q.append(stamp)

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with Session() as db:
        for run in db.query(Run).filter(Run.status.in_(['queued', 'running'])).all():
            run.status = 'failed'; run.result = {'error': 'The server restarted during this run. Your search plan is preserved; run it again.'}
        db.commit()
    agent.warm_reranker()
    yield

app = FastAPI(title='PaperTrail', lifespan=lifespan)

def current_workspace(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith('Bearer '): raise HTTPException(401, 'Create or restore a workspace first.')
    with Session() as db:
        workspace = db.query(Workspace).filter_by(token_hash=token_hash(authorization[7:])).first()
        if not workspace: raise HTTPException(401, 'Workspace key is invalid.')
        return workspace.id

def owned_run(run_id, workspace_id):
    with Session() as db:
        run = db.get(Run, run_id)
        if not run or run.workspace_id != workspace_id: raise HTTPException(404, 'Search not found in this workspace.')
        return run

def run_json(row):
    return {'id': row.id, 'created_at': row.created_at, 'status': row.status, 'request': row.request,
            'result': row.result, 'events': row.events, 'feedback': row.feedback}

@app.get('/api/status')
def status():
    return {'app': 'PaperTrail', 'openalex_configured': bool(settings.openalex_api_key),
            'llm_configured': bool(settings.llm_api_key), 'llm_model': settings.llm_model if settings.llm_api_key else None,
            'reranker_ready': agent._model is not None, 'reranker_enabled': settings.reranker_enabled,
            'reranker_model': settings.reranker_model, 'reranker_backend': settings.reranker_backend,
            'database': 'PostgreSQL' if settings.database_url.startswith('postgres') else 'SQLite (local file)',
            'max_api_calls': settings.max_api_calls}

class WorkspaceRequest(BaseModel):
    access_code: str = ''

@app.post('/api/workspaces', status_code=201)
def create_workspace(payload: WorkspaceRequest, request: Request):
    rate_limit('workspace:' + (request.client.host if request.client else 'unknown'), count=10)
    if settings.access_code and not hmac.compare_digest(payload.access_code, settings.access_code):
        raise HTTPException(403, 'Enter the workspace access code.')
    token = secrets.token_urlsafe(32); workspace_id = str(uuid4())
    with Session() as db:
        db.add(Workspace(id=workspace_id, token_hash=token_hash(token))); db.commit()
    return {'id': workspace_id, 'token': token}

def fallback_plan(question):
    stop = {'find','papers','paper','published','from','that','introduce','methods','for','and','the','on','of','to','with','rather','than','only','about','looking','research','i','am','a','an','in','between','after','before'}
    tokens = [t for t in re.findall(r'[\w-]+', question) if t.lower() not in stop and not re.fullmatch(r'\d{4}', t)]
    years = [int(x) for x in re.findall(r'\b(?:19|20)\d{2}\b', question)]
    criteria = []
    # These are suggestions that must be reviewed, never silently imposed.
    for i, part in enumerate(re.split(r';|\n', question)):
        if len(part.strip()) > 8 and len(part.strip()) < 240 and len(criteria) < 5:
            criteria.append(Criterion(id=f'c{i+1}', text=part.strip()))
    return Plan(question=question, queries=[' '.join(tokens[:14]) or question[:250]], criteria=criteria,
                year_from=min(years) if len(years) >= 2 else None, year_to=max(years) if len(years) >= 2 else None,
                planner='reviewable rule-based plan; hosted model unavailable')

@app.post('/api/plan', response_model=Plan)
def plan_search(payload: PlanRequest, workspace_id: str = Depends(current_workspace)):
    rate_limit('plan:' + workspace_id, count=20)
    try:
        raw = llm.make_plan(payload.question)
        return Plan(question=payload.question, queries=raw['queries'],
                    criteria=[Criterion(id=f'c{i+1}', text=text) for i, text in enumerate(raw.get('criteria', []))],
                    year_from=raw.get('year_from'), year_to=raw.get('year_to'), open_access=raw.get('open_access', False), planner=raw.get('_model', settings.llm_model))
    except (llm.LLMUnavailable, ValueError, KeyError, TypeError):
        return fallback_plan(payload.question)

@app.post('/api/runs', status_code=202)
def create_run(payload: SearchRequest, workspace_id: str = Depends(current_workspace)):
    rate_limit('run:' + workspace_id, count=12)
    with Session() as db:
        pending = db.query(Run).filter(Run.status.in_(['queued', 'running'])).count()
        if pending >= 4: raise HTTPException(429, 'The research queue is full. Please wait for an active search to finish.')
        run_id = str(uuid4())
        db.add(Run(id=run_id, workspace_id=workspace_id, request=payload.model_dump(), result={}, events=[], feedback={}))
        db.commit()
    executor.submit(agent.execute, run_id, payload.model_dump())
    return {'id': run_id}

@app.get('/api/runs')
def list_runs(workspace_id: str = Depends(current_workspace)):
    with Session() as db:
        return [{'id': r.id, 'question': r.request['plan']['question'], 'created_at': r.created_at, 'status': r.status}
                for r in db.query(Run).filter_by(workspace_id=workspace_id).order_by(Run.created_at.desc()).limit(50)]

@app.get('/api/runs/{run_id}')
def read_run(run_id: str, workspace_id: str = Depends(current_workspace)):
    return run_json(owned_run(run_id, workspace_id))

@app.post('/api/runs/{run_id}/feedback')
def save_feedback(run_id: str, payload: Feedback, workspace_id: str = Depends(current_workspace)):
    row = owned_run(run_id, workspace_id)
    if payload.paper_id not in {p['id'] for p in row.result.get('papers', [])}: raise HTTPException(404, 'Paper not in this result.')
    with Session() as db:
        row = db.get(Run, run_id)
        row.feedback = {**row.feedback, payload.paper_id: payload.model_dump()}
        db.commit()
    return {'saved': True}

class ChatRequest(BaseModel):
    question: str = Field(min_length=5, max_length=1200)

@app.post('/api/runs/{run_id}/chat')
def chat_with_results(run_id: str, payload: ChatRequest, workspace_id: str = Depends(current_workspace)):
    row = owned_run(run_id, workspace_id)
    rate_limit('chat:' + workspace_id, count=30)
    if row.status != 'complete': raise HTTPException(409, 'Wait for the investigation to finish.')
    try:
        papers = row.result.get('papers', [])
        try:
            scores = agent.neural_scores(payload.question, papers) if papers else None
            if scores: papers = [p for _, p in sorted(zip(scores, papers), key=lambda pair: pair[0], reverse=True)]
        except Exception: pass
        return grounded_chat.answer(payload.question, papers)
    except llm.LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from None

@app.get('/api/runs/{run_id}/export/{format}')
def export_run(run_id: str, format: str, workspace_id: str = Depends(current_workspace)):
    row = owned_run(run_id, workspace_id); papers = row.result.get('papers', [])
    if format == 'json':
        text = json.dumps(run_json(row), ensure_ascii=False, indent=2); media = 'application/json'
    elif format == 'csv':
        out = io.StringIO(); writer = csv.writer(out)
        def cell(value):
            text = '' if value is None else str(value)
            return "'" + text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else text
        writer.writerow(['id', 'title', 'year', 'doi', 'criterion', 'status', 'quote', 'quote_verified'])
        for p in papers:
            for c in p.get('criteria') or [{}]: writer.writerow([cell(v) for v in [p['id'], p['title'], p.get('year'), p.get('doi'), c.get('criterion_id'), c.get('status'), c.get('quote'), c.get('quote_verified')]])
        text = out.getvalue(); media = 'text/csv'
    elif format == 'bib':
        def clean(x): return re.sub(r'[{}\\]', '', str(x or ''))
        text = '\n\n'.join('@article{'+p['id'].rsplit('/', 1)[-1]+',\n  title={'+clean(p['title'])+'},\n  year={'+clean(p.get('year'))+'},\n  doi={'+clean((p.get('doi') or '').replace('https://doi.org/', ''))+'}\n}' for p in papers)
        media = 'text/plain'
    else: raise HTTPException(404, 'Export format not supported.')
    return Response(text, media_type=media, headers={'Content-Disposition': f'attachment; filename="papertrail-{run_id[:8]}.{format}"'})

static = ROOT / 'static'
if not static.exists(): static = ROOT / 'web' / 'dist'
if static.exists():
    app.mount('/assets', StaticFiles(directory=static / 'assets'), name='assets')
    @app.get('/{path:path}')
    def frontend(path: str):
        return FileResponse(static / 'index.html')
