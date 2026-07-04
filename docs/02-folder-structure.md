# Folder Structure

Monorepo. Backend and frontend are separate deployables sharing one repo and one
`docs/` and `infra/` root, so architecture decisions and API contracts stay in one place.

```
Mw-StockMarket-Analytics/
├── docs/                              # This deliverable set (architecture, schema, API, roadmap)
│   ├── 01-architecture.md
│   ├── 02-folder-structure.md
│   ├── 03-database-schema.md
│   ├── 04-api-design.md
│   ├── 05-worker-architecture.md
│   └── 06-roadmap.md
│
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory, router mounting, middleware
│   │   │
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── router.py          # aggregates all resource routers under /api/v1
│   │   │       └── routers/
│   │   │           ├── videos.py
│   │   │           ├── channels.py
│   │   │           ├── summaries.py
│   │   │           ├── search.py
│   │   │           ├── reports.py
│   │   │           ├── chat.py
│   │   │           ├── analytics.py
│   │   │           ├── watchlist.py
│   │   │           ├── admin.py
│   │   │           └── scheduler.py
│   │   │
│   │   ├── core/
│   │   │   ├── config.py              # Pydantic Settings (env-driven), per-environment
│   │   │   ├── logging.py             # structured JSON logging setup
│   │   │   ├── security.py            # auth (JWT/API key), password hashing
│   │   │   ├── celery_app.py          # Celery app instance, queue routing config
│   │   │   └── exceptions.py          # domain exception -> HTTP error mapping
│   │   │
│   │   ├── db/
│   │   │   ├── base.py                # Declarative base, naming conventions
│   │   │   ├── session.py             # async session factory / dependency
│   │   │   └── migrations/            # Alembic env + versions/
│   │   │
│   │   ├── models/                    # SQLAlchemy ORM models (1 concept per file)
│   │   │   ├── channel.py
│   │   │   ├── video.py
│   │   │   ├── video_stat_snapshot.py
│   │   │   ├── transcript.py
│   │   │   ├── transcript_segment.py
│   │   │   ├── summary.py
│   │   │   ├── investment_thesis.py
│   │   │   ├── company.py
│   │   │   ├── ticker.py
│   │   │   ├── topic.py
│   │   │   ├── sentiment.py
│   │   │   ├── quote.py
│   │   │   ├── key_number.py
│   │   │   ├── actionable_insight.py
│   │   │   ├── daily_report.py
│   │   │   ├── embedding.py
│   │   │   ├── user.py
│   │   │   ├── bookmark.py
│   │   │   ├── watchlist.py
│   │   │   └── task_log.py
│   │   │
│   │   ├── schemas/                   # Pydantic request/response models, mirrors models/
│   │   │   └── ...                    # (one file per resource, e.g. video.py, channel.py)
│   │   │
│   │   ├── repositories/              # Data-access layer; only place raw queries live
│   │   │   ├── base.py
│   │   │   ├── video_repository.py
│   │   │   ├── channel_repository.py
│   │   │   ├── transcript_repository.py
│   │   │   ├── embedding_repository.py   # pgvector similarity queries live here
│   │   │   └── ...
│   │   │
│   │   ├── services/                  # Business logic, orchestrates repos + providers
│   │   │   ├── channel_discovery_service.py
│   │   │   ├── transcript_service.py
│   │   │   ├── analysis_service.py
│   │   │   ├── embedding_service.py
│   │   │   ├── search_service.py
│   │   │   ├── rag_chat_service.py
│   │   │   ├── report_service.py
│   │   │   ├── watchlist_service.py
│   │   │   └── quota_tracker.py
│   │   │
│   │   ├── providers/                 # Ports & adapters for every external dependency
│   │   │   ├── video_platforms/
│   │   │   │   ├── base.py            # VideoPlatformProvider interface
│   │   │   │   └── youtube_provider.py
│   │   │   ├── transcription/
│   │   │   │   ├── base.py            # TranscriptionProvider interface
│   │   │   │   ├── youtube_captions_provider.py
│   │   │   │   ├── whisper_local_provider.py
│   │   │   │   └── whisper_api_provider.py
│   │   │   └── llm/
│   │   │       ├── base.py            # LLMProvider / EmbeddingProvider interfaces
│   │   │       └── openai_provider.py
│   │   │
│   │   ├── workers/
│   │   │   ├── tasks/
│   │   │   │   ├── discovery_tasks.py     # poll_channel, sync_video_metadata
│   │   │   │   ├── transcript_tasks.py    # fetch_captions, run_whisper
│   │   │   │   ├── analysis_tasks.py      # summarize, extract_entities, sentiment, ...
│   │   │   │   ├── embedding_tasks.py     # chunk_and_embed
│   │   │   │   ├── report_tasks.py        # generate_daily_report
│   │   │   │   └── maintenance_tasks.py   # retry_failed_pipelines, cleanup_media_cache
│   │   │   ├── pipeline.py            # Celery canvas wiring (chain/chord) per video
│   │   │   └── beat_schedule.py       # Celery beat periodic task definitions
│   │   │
│   │   ├── prompts/                   # Versioned LLM prompt templates (one per extractor)
│   │   │   ├── executive_summary.py
│   │   │   ├── investment_thesis.py
│   │   │   ├── entity_extraction.py
│   │   │   ├── sentiment.py
│   │   │   ├── quotes.py
│   │   │   ├── key_numbers.py
│   │   │   ├── actionable_insights.py
│   │   │   └── rag_answer.py
│   │   │
│   │   └── utils/
│   │       ├── chunking.py            # transcript -> overlapping token windows
│   │       ├── ticker_normalizer.py
│   │       └── datetime_utils.py
│   │
│   ├── tests/
│   │   ├── unit/                      # mirrors app/ structure
│   │   ├── integration/               # DB + repository tests (testcontainers)
│   │   └── conftest.py
│   │
│   ├── alembic.ini
│   ├── pyproject.toml                 # deps, ruff/mypy/pytest config
│   ├── Dockerfile
│   ├── Dockerfile.worker               # separate image/entrypoint for Celery workers
│   └── .env.example
│
├── frontend/                           # Phase 2 deliverable
│   ├── app/                            # Next.js App Router
│   │   ├── (dashboard)/
│   │   │   ├── page.tsx                # dashboard home
│   │   │   ├── videos/
│   │   │   ├── search/
│   │   │   ├── chat/
│   │   │   ├── reports/
│   │   │   ├── watchlist/
│   │   │   └── admin/
│   │   └── layout.tsx
│   ├── components/
│   │   ├── ui/                         # shadcn/ui primitives
│   │   └── domain/                     # VideoCard, SentimentGauge, SectorHeatmap, ...
│   ├── lib/
│   │   ├── api-client.ts               # typed fetch wrapper for backend REST API
│   │   └── query-client.ts             # TanStack Query setup
│   ├── hooks/
│   ├── styles/
│   ├── package.json
│   ├── tailwind.config.ts
│   └── Dockerfile
│
├── infra/
│   ├── docker-compose.yml              # postgres+pgvector, redis, backend api, celery worker(s), celery beat, frontend
│   ├── docker-compose.prod.yml
│   └── nginx/
│       └── default.conf
│
├── .github/
│   └── workflows/
│       ├── backend-ci.yml              # lint, mypy, pytest
│       └── frontend-ci.yml             # lint, typecheck, build
│
└── README.md
```

## Rationale

**`providers/` is the only place that knows about YouTube, Whisper, or OpenAI
specifically.** `services/` and `workers/tasks/` call interfaces, never SDKs directly.
This is what lets "YouTube-only Phase 1" and "podcasts/Twitter later" be true without a
rewrite, and lets provider swaps (e.g., self-hosted LLM instead of OpenAI) stay
contained.

**`repositories/` is the only place that writes raw SQL/ORM queries**, including the
pgvector similarity search. Services never touch the DB session directly. This keeps
business logic testable with mocked repositories and keeps query optimization
centralized.

**`prompts/` is separated from `services/`** so prompt engineering iteration doesn't
require touching orchestration code, and so prompts can be versioned/tested
independently (important since prompt changes silently change output quality/cost).

**Two Dockerfiles for the backend** (`Dockerfile` for the API, `Dockerfile.worker` for
Celery) because the worker image needs heavier dependencies (`ffmpeg`, Whisper model
weights, optionally CUDA) that the API process doesn't, keeping the API image small and
fast to deploy.
