# MW StockMarket Analytics

**AI Stock Market Video Intelligence Platform**

Automatically discovers, transcribes, and analyzes financial commentary from YouTube
channels, extracting investment theses, sentiment, company/ticker mentions, key numbers,
and actionable insights — searchable via structured filters, pgvector semantic search,
and a RAG-powered chat assistant. On top of that, a **Company Intelligence module** turns
any ticker, company name, or keyword into a full research page: live market data,
fundamentals, technicals, news, analyst opinion, and an AI executive summary, all fully
integrated with the video pipeline above rather than duplicating it.

Runs entirely on free-tier infrastructure — **no OpenAI key required**: Groq (free
Whisper transcription) + Ollama (free local/Colab-GPU LLM + embeddings) + yfinance (free
market data).

## Current status

**Backend is functional end-to-end.** The full video pipeline (discovery → transcription
→ 8 parallel LLM extractors → embedding → indexing) runs, is searchable, and is chat-able.
The Company Intelligence module's first three phases are built and verified live against
real tickers on both US (NASDAQ) and Indian (NSE/BSE) exchanges. No frontend yet —
everything below is backend/API only.

| Area | Status |
|---|---|
| Video discovery, transcription, 8-extractor AI analysis, embeddings, semantic search, RAG chat | ✅ Working |
| Company Intelligence — Phase 1 (resolution, live quote, charts, profile, AI video intelligence) | ✅ Working |
| Company Intelligence — Phase 2 (ratios, financial statements, earnings, technical analysis) | ✅ Working |
| Company Intelligence — Phase 3 (news + AI sentiment scoring, analyst insights, AI executive summary) | ✅ Working |
| Company Intelligence — Phase 4 (SEC filings, social sentiment, competitor comparison) | ⏳ Scoped, not built |
| Frontend | ⏳ Not started |
| Multi-user auth enforcement, watchlist endpoints beyond stub | ⏳ Partial |

## Architecture

Full design documentation lives in `docs/`:
- [01-architecture.md](docs/01-architecture.md) — system overview, components, data flow
- [02-folder-structure.md](docs/02-folder-structure.md) — monorepo layout
- [03-database-schema.md](docs/03-database-schema.md) — PostgreSQL + pgvector schema (video pipeline)
- [04-api-design.md](docs/04-api-design.md) — FastAPI REST API specification
- [05-worker-architecture.md](docs/05-worker-architecture.md) — Celery queues and pipeline
- [06-roadmap.md](docs/06-roadmap.md) — phased development plan
- [07-company-intelligence.md](docs/07-company-intelligence.md) — Company Intelligence module: architecture diagrams, DB schema, provider waterfall, API reference, caching strategy

For deep operational detail (known bugs and fixes, exact env vars, pipeline state machine,
Ollama/Colab setup), see [`SYSTEM-CONTEXT.md`](SYSTEM-CONTEXT.md) at the repo root — that
file is the authoritative day-to-day reference and is kept current across sessions.

### System overview

```
YouTube channels ──▶ Discovery/Polling ──▶ Transcription (captions → Groq Whisper)
                                                    │
                                                    ▼
                          8 parallel LLM extractors (Ollama mistral)
                     summary · thesis · entities · topics · sentiment
                          quotes · key numbers · actionable insights
                                                    │
                                                    ▼
                    Chunk + embed (Ollama nomic-embed-text) ──▶ pgvector
                                                    │
                                                    ▼
                 FastAPI: structured search · semantic search · RAG chat
                          · analytics · daily reports · Company Intelligence
```

### Company Intelligence module

```mermaid
graph LR
    Client --> Router["/api/v1/companies/*"]
    Router --> CIS[CompanyIntelligenceService]
    CIS --> Sections["MarketDataService · FinancialsService<br/>TechnicalAnalysisService · NewsService<br/>AnalystService · ExecutiveSummaryService"]
    CIS --> Existing["AnalysisRepository · EmbeddingRepository<br/>RagChatService (reused, not duplicated)"]
    Sections --> Waterfall["CompositeMarketDataProvider<br/>yfinance → Twelve Data fallback"]
    Sections --> PG[(PostgreSQL<br/>additive tables only)]
    Sections --> LLM[Ollama LLM]
    Existing --> LLM
```

See [docs/07-company-intelligence.md](docs/07-company-intelligence.md) for the full
component diagram, request-lifecycle sequence diagram, and entity-relationship diagram.

## Quick Start (Development)

### Prerequisites
- Docker + Docker Compose
- Python 3.11+ (for local dev without Docker)
- A [Groq API key](https://console.groq.com) (free) for transcription
- Ollama running somewhere reachable — locally, in Docker, or via an ngrok tunnel to a
  Colab GPU notebook (see `SYSTEM-CONTEXT.md` → "Ollama / Colab GPU" for the exact setup)

### 1. Clone and configure

```bash
git clone <repo-url> mw-stockmarket-analytics
cd mw-stockmarket-analytics/backend
cp .env.example .env
```

Edit `.env` — the values that actually matter for a working local setup:

```ini
SECRET_KEY=<openssl rand -hex 32>
ADMIN_API_KEY=changeme-admin-key

GROQ_API_KEY=<your free Groq key>          # transcription
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434        # or your ngrok/Colab tunnel URL
OLLAMA_LLM_MODEL=mistral:latest
OLLAMA_EMBEDDING_MODEL=nomic-embed-text:latest

YOUTUBE_API_KEY=                            # optional — only needed for channel polling,
                                             # NOT for the single-video process-url endpoint
TWELVE_DATA_API_KEY=                        # optional — Company Intelligence market-data
                                             # fallback; empty means yfinance-only, which
                                             # is sufficient on its own
```

### 2. Boot via Docker Compose

```bash
cd ../infra
docker compose up -d
```

This starts:
- **postgres** (`localhost:5432`) — Postgres 16 + pgvector
- **redis** (`localhost:6379`) — Redis 7
- **ollama** (`localhost:11434`) — local Ollama fallback (skip if using a Colab tunnel)
- **api** (`localhost:8000`) — FastAPI backend
- **worker-discovery** — Celery worker (discovery, maintenance, **market_data** queues)
- **worker-transcription** — Celery worker (transcription queue, `--pool=solo`)
- **worker-analysis** — Celery worker (analysis, embedding queues, `--pool=solo`)
- **worker-reports** — Celery worker (reports queue)
- **beat** — Celery Beat scheduler

### 3. Run migrations

```bash
docker compose exec api alembic upgrade head
```

Current head: `0006` (video pipeline schema `0001`-`0003`, Company Intelligence Phases
1-3 add `0004`-`0006`).

### 4. Verify

```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","environment":"development"}
```

Access interactive API docs at: http://localhost:8000/api/docs

### 5. Try it

```bash
# Process a single YouTube video (no YouTube API key needed)
curl -X POST "http://localhost:8000/api/v1/videos/process-url?url=https://youtu.be/<video_id>"

# Once indexed, ask about a company mentioned in it — or any ticker at all
curl "http://localhost:8000/api/v1/companies/AAPL"
curl "http://localhost:8000/api/v1/companies/AAPL/executive-summary"
```

## Development Workflow

### Running locally (without Docker)

1. Install dependencies:
   ```bash
   cd backend
   pip install -e .
   ```

2. Start Postgres+Redis via Docker Compose (just the infra):
   ```bash
   cd ../infra
   docker compose up postgres redis -d
   ```

3. Run migrations:
   ```bash
   cd ../backend
   alembic upgrade head
   ```

4. Start the API:
   ```bash
   uvicorn app.main:app --reload
   ```

5. Start Celery workers + beat (separate terminals — note `--pool=solo` for
   transcription/analysis, required for the libraries those queues use):
   ```bash
   celery -A app.core.celery_app worker -Q discovery,maintenance,market_data --concurrency=8 --loglevel=info
   celery -A app.core.celery_app worker -Q transcription --pool=solo --loglevel=info
   celery -A app.core.celery_app worker -Q analysis,embedding --pool=solo --loglevel=info
   celery -A app.core.celery_app worker -Q reports --loglevel=info
   celery -A app.core.celery_app beat --loglevel=info
   ```

**After code changes to workers** (not hot-reloaded — restart to pick up changes):
```bash
docker restart mw_worker_analysis mw_worker_transcription mw_worker_discovery
```

**After code changes to the API** — uvicorn's `--reload` usually picks it up, but on
Windows-mounted Docker volumes it can miss changes; if in doubt, `docker restart mw_api`.

### Linting / Type-checking / Tests

```bash
cd backend
ruff check .
mypy app
pytest
```

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app factory
│   ├── core/                # Config, logging, security, Celery app
│   ├── db/                  # SQLAlchemy base, session, migrations/ (0001-0006)
│   ├── models/               # ORM models — video pipeline + market_data.py,
│   │                         # financials.py, news_analyst.py (Company Intelligence)
│   ├── schemas/              # Pydantic request/response schemas
│   ├── repositories/         # Data access layer
│   ├── services/             # Business logic — analysis/embedding/search/rag_chat
│   │                         # + market_data/financials/technical_analysis/news/
│   │                         #   analyst/executive_summary/company_intelligence services
│   ├── providers/
│   │   ├── llm/               # Ollama, OpenAI adapters
│   │   ├── transcription/     # Groq, Whisper local/API, YouTube captions
│   │   ├── video_platforms/   # yt-dlp, YouTube Data API
│   │   └── market_data/       # yfinance (primary), Twelve Data (fallback), composite waterfall
│   ├── workers/tasks/        # Celery tasks, incl. market_data_tasks.py
│   ├── prompts/              # LLM prompt templates, incl. news_classification.py,
│   │                         #   company_executive_summary.py
│   ├── api/v1/routers/       # FastAPI route handlers, incl. company_intelligence.py
│   └── utils/                # Helpers (chunking, etc.)
├── tests/
├── alembic.ini
├── pyproject.toml
├── Dockerfile              # API image
└── Dockerfile.worker       # Worker image (heavier deps: ffmpeg, Whisper, yfinance)

infra/
└── docker-compose.yml      # Full stack orchestration

docs/
├── 01-architecture.md
├── 02-folder-structure.md
├── 03-database-schema.md
├── 04-api-design.md
├── 05-worker-architecture.md
├── 06-roadmap.md
└── 07-company-intelligence.md
```

## API Endpoints

Base URL: `http://localhost:8000` · Interactive docs: `/api/docs` · Admin routes require
header `X-Admin-Key`.

### Video pipeline
| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/videos/process-url?url=` | Main entry point — no API key needed, uses yt-dlp |
| GET | `/api/v1/videos` | List with filters |
| GET | `/api/v1/videos/{id}` | Pipeline status |
| POST | `/api/v1/videos/{id}/reprocess?from_stage=` | Admin retry |
| GET | `/api/v1/videos/{id}/{summary\|sentiment\|companies\|key-numbers\|insights\|quotes\|transcript}` | Per-video AI results |
| GET | `/api/v1/search` · POST `/api/v1/search/semantic` | Structured / pgvector search |
| POST | `/api/v1/chat/sessions` · `/messages` | RAG chat |
| GET | `/api/v1/analytics/{trending-stocks\|trending-sectors\|sector-heatmap\|sentiment\|creator}` | Aggregations |

### Company Intelligence
| Method | Path | Phase |
|---|---|---|
| GET | `/api/v1/companies/resolve?q=` | 1 |
| GET | `/api/v1/companies/{ticker}` | 1 |
| GET | `/api/v1/companies/{ticker}/{quote\|chart\|profile}` | 1 |
| GET | `/api/v1/companies/{ticker}/{ratios\|financials\|earnings\|technicals}` | 2 |
| GET | `/api/v1/companies/{ticker}/{news\|analyst\|executive-summary}` | 3 |
| GET | `/api/v1/companies/{ticker}/{videos\|intelligence}` | 1 (reused pipeline) |
| POST | `/api/v1/companies/{ticker}/chat` | 1 (reused pipeline) |

Full endpoint-by-endpoint reference with parameters: [docs/07-company-intelligence.md §7](docs/07-company-intelligence.md#7-api-reference).

### Admin
`/api/v1/admin/{pipeline/status\|pipeline/failures\|pipeline/retry\|quota\|task-logs\|users}`,
`/api/v1/scheduler/jobs` — all require `X-Admin-Key`.

## Pipeline state machine

```
DISCOVERED → TRANSCRIPT_PENDING → TRANSCRIPT_READY → ANALYSIS_PENDING
          → ANALYZED → EMBEDDING_PENDING → EMBEDDED → INDEXED
          → FAILED (at any stage, auto-retried by Celery Beat every 10 min)
```

## Roadmap

- ✅ **Foundations** — repo scaffold, Docker Compose, DB schema, `/health` endpoint
- ✅ **Video pipeline** — discovery, transcription, 8-extractor AI analysis, embeddings, semantic search, RAG chat
- ✅ **Company Intelligence Phase 1** — ticker/company resolution, live market data, charts, profile, AI video intelligence integration
- ✅ **Company Intelligence Phase 2** — financial statements, ratios, earnings, in-house technical analysis
- ✅ **Company Intelligence Phase 3** — news aggregation with AI sentiment/impact scoring, analyst insights, AI executive summary
- ⏳ **Company Intelligence Phase 4** — SEC filings (US-only), social sentiment (Reddit + best-effort StockTwits), competitor comparison
- ⏳ **Frontend** — Next.js, not started
- ⏳ **Additional video sources** — podcasts, Twitter/X (source-adapter pattern already anticipated in the architecture)
- ⏳ **Hardening** — broader test coverage, observability dashboards, production-grade docker-compose

See [docs/06-roadmap.md](docs/06-roadmap.md) for the original phased plan and
[docs/07-company-intelligence.md §10](docs/07-company-intelligence.md#10-whats-not-built--phase-4)
for exactly what Phase 4 would involve and why it's deferred.

## License

Proprietary / Internal use only.

## Contact

For questions or contributions, reach out to the MW StockMarket Analytics team.
