# PaperTrail

An evidence-led paper-finding agent built from scratch for complex research questions. OpenAlex provides the scholarly records; a hosted LLM plans searches and assesses criteria; a CPU cross-encoder reranks real candidates. The interface keeps uncertainty, counter-evidence, search provenance, and citations visible.

**Live app:** https://papertrail-production-da48fd85.up.railway.app

[Read the pilot report](docs/PaperTrail-Research-Report.pdf) · [Watch the 4:53 narrated walkthrough](docs/PaperTrail-Narrated-Walkthrough.mp4)

## What works

- Review/edit LLM-generated queries, inclusion criteria, publication years, and access filters before searching.
- OpenAlex keyword + native semantic search; DOI/title deduplication; reciprocal-rank fusion; real local neural reranking.
- A bounded LangGraph workflow with citation exploration and one criterion-driven repair round when evidence coverage is incomplete.
- Per-paper criterion ledger: supported, contradicted, or uncertain. Non-uncertain judgments require an exact source quote found independently in the supplied metadata.
- Criteria-first results, evidence matrix, actual reference links, discovery trace, relevance feedback, and JSON/CSV/BibTeX exports.
- Ask questions about the returned reading list; each returned claim requires a valid paper ID and matching source quote.
- Separate workspaces, durable PostgreSQL in production, SQLite for local development, and a browser-held recovery key.

This is a research prototype. It reads **titles and abstracts**, not full PDFs. Quote matching checks attribution, not logical entailment. No overall superiority over Google Scholar or Asta is claimed. The pilot findings and comparison limitations are documented under `docs/` and `evaluation/`.

## Models

| Component | Model | Where it runs |
|---|---|---|
| Planning, criteria assessment, grounded Q&A | `gemini-3.6-flash`, fallback `gemini-2.5-flash` | User's Gemini API account, via OpenAI-compatible endpoint |
| Neural reranking | `Alibaba-NLP/gte-reranker-modernbert-base` (ONNX int8) | Locally on CPU / application container; no inference API |
| Native semantic retrieval | OpenAlex's semantic-search service | OpenAlex; their documented Qwen3-Embedding-0.6B index |

The deployed reranker is a pretrained GTE ModernBERT model, quantized for CPU inference. It is not newly trained on this task. No fabricated training or tuning claims are made. Feedback is stored for evaluation and does not automatically retrain a model. This new build uses hosted inference with the user's authorization.

## Run locally

Requires Python 3.12 and Node.js 22. Windows PowerShell:

```powershell
Set-Location D:\PaperTrail
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env privately: set OPENALEX_API_KEY and LLM_API_KEY.
Set-Location web
npm ci
npm run build
Set-Location ..
uvicorn server.main:app --host 127.0.0.1 --port 8010
```

Open http://127.0.0.1:8010. For frontend development run `npm run dev` in `web`; Vite proxies `/api` to port 8010. The neural model downloads on first startup; `/api/status` reports readiness. Retrieval falls back explicitly to RRF if weights are still loading.

On this machine the existing working Python environment is `D:\LiteratureReviewAI\.venv\Scripts\python.exe`. Primary sources and artifacts are in `D:\PaperTrail`. Keep `.env` private. Do not put keys into frontend code, repository files, public URLs, or screenshots.

## Database and access

Local default: `sqlite:///./work/papertrail.sqlite3`. Production accepts `postgres://`, `postgresql://`, or `postgresql+psycopg://` URLs and uses psycopg 3. Tables are created on startup. Set `DATABASE_URL` to a database you control.

The browser stores a random workspace capability. Only its SHA-256 hash is stored server-side. Use **Workspace & data -> Copy recovery key** and keep that key privately. A lost key cannot be recovered from the database. Workspace authorization applies to reads, feedback, chat, and exports. Optional `ACCESS_CODE` limits workspace creation.

Current Railway project `6817ba60-5ba4-49d2-a073-6719f0787de1` is in **Hai Nguyen's Projects**, with separate `papertrail` and `Postgres` services. Manage it at https://railway.com/project/6817ba60-5ba4-49d2-a073-6719f0787de1 . Database access, backups, variables, billing, and service lifecycle remain under that account. The original literature-review deployment is separate.

## Deploy on Railway

The multistage Dockerfile builds React and installs ONNX Runtime for CPU inference. Model weights and tokenizer are pinned to revision `f7481e6055501a30fb19d090657df9ec1f79ab2c`. For a different ONNX model, set its compatible `RERANKER_MODEL` and `RERANKER_REVISION` explicitly. Set service variables privately:

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
OPENALEX_API_KEY=<your key>
LLM_API_KEY=<your inference key>
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemini-3.6-flash
LLM_FALLBACK_MODEL=gemini-2.5-flash
```

Then `railway up --service papertrail --detach` and generate a domain targeting port 8080. Health check: `/api/status`. Run **one application replica/worker**: the bounded job queue and rate limits are process-local. PostgreSQL persists finished runs; interrupted jobs are marked failed after restart with their plan preserved. Production scale requires a durable worker queue and shared rate limiter. No database credentials or model keys are embedded in the image.

## Verification and evaluation

```powershell
pip install pytest
python -m pytest -q
python -m evaluation.run_pilot --base http://127.0.0.1:8010
python -m evaluation.metrics
```

The pilot makes real API/inference calls. The initial eight-run pilot used MiniLM before the model upgrade; its saved results are retained unchanged. `python -m evaluation.model_replay` compares the current int8 ModernBERT model with cached candidate records without new hosted calls. This replay is a development comparison, not a held-out evaluation. Its fixed sample is defined before execution in `evaluation/litsearch-pilot-tasks.json`. The source is the official LitSearch dataset. It is a small transfer test to OpenAlex, not the official fixed-corpus benchmark. Metrics measure known-target title matches; unjudged papers are not automatically irrelevant. Stage snapshots expose single semantic retrieval, hybrid RRF, neural reranking, and final criterion ordering. Live Asta/Scholar observations were collected manually through their interfaces; no bulk Scholar scraping is included.

## Architecture

```mermaid
flowchart LR
 Q[Research question] --> P[LLM plan + user review]
 P --> R[OpenAlex keyword + semantic search]
 R --> D[Deduplicate + RRF]
 D --> N[CPU cross-encoder]
 N --> C[Citation expansion]
 C --> E[LLM criterion assessment]
 E --> V[Independent quote check]
 V --> G{Coverage gap?}
 G -->|One bounded round| R2[Targeted semantic repair]
 R2 --> N2[Rerank + reassess]
 G -->|Complete or budget reached| O[Evidence ledger + exports + grounded Q&A]
 N2 --> O
```

External documents and model output are untrusted. Metadata filters are rechecked after citation expansion. Keys never reach the browser. Workspace IDs are checked server-side, errors omit provider payloads, and CSV exports neutralize spreadsheet formula prefixes.

## Attribution

Inspired by the user's original Automated-Literature-Review-with-Multi-Agent-AI project; this is a fresh implementation. Dependencies keep their own licenses. OpenAlex data/API, Google Gemini, the MS MARCO cross-encoder, LangGraph, React, FastAPI, and LitSearch are credited in `docs/references.md`. Provider terms, data coverage, and third-party service availability still apply.
