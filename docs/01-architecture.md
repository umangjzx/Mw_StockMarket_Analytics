# Architecture — AI Stock Market Video Intelligence Platform

Phase 1 scope: backend only, YouTube as the sole video source. Everything is designed so
podcasts, earnings-call recordings, and X/Twitter video can be added later as new
**source adapters**, not rewrites.

## 1. System Context

```
                    ┌──────────────────────────────────────────────────┐
                    │                   Data Sources                    │
                    │  YouTube Data API  |  YouTube captions/yt-dlp     │
                    │  (podcasts, Twitter/X — Phase 2+ adapters)        │
                    └───────────────────────┬────────────────────────--┘
                                             │
                    ┌────────────────────────▼────────────────────────┐
                    │                Ingestion Layer                   │
                    │  Channel Poller · Video Discovery · Metadata     │
                    │  Sync · Transcript Fetcher · Whisper Fallback    │
                    └───────────────────────┬────────────────────────-┘
                                             │ Celery tasks (Redis broker)
                    ┌────────────────────────▼────────────────────────┐
                    │               AI Processing Layer                │
                    │  Summarization · Investment Thesis Extraction    │
                    │  Entity/Ticker Extraction · Topic Tagging        │
                    │  Sentiment Scoring · Quote/Number Extraction     │
                    │  Embedding Generation (OpenAI)                   │
                    └───────────────────────┬────────────────────────-┘
                                             │
                    ┌────────────────────────▼────────────────────────┐
                    │              Persistence Layer                   │
                    │  PostgreSQL (relational) + pgvector (embeddings) │
                    │  Object storage (audio/video cache, transcripts) │
                    └───────────────────────┬────────────────────────-┘
                                             │
                    ┌────────────────────────▼────────────────────────┐
                    │                 Serving Layer                    │
                    │  FastAPI REST API · Semantic Search · RAG Chat   │
                    │  Daily Report Generator · Analytics Aggregation  │
                    └───────────────────────┬────────────────────────-┘
                                             │
                    ┌────────────────────────▼────────────────────────┐
                    │        Next.js Frontend (Phase 2 deliverable)    │
                    └───────────────────────────────────────────────-─┘
```

## 2. Component Breakdown

**API Gateway (FastAPI)** — the only component clients talk to. Stateless, horizontally
scalable, async I/O throughout (httpx for outbound calls, asyncpg/SQLAlchemy async
engine for DB). Owns auth, validation, and orchestration of read paths (search, chat,
reports). It never does heavy work inline — anything slow (transcription, LLM analysis)
is delegated to Celery and the API returns a job/status handle.

**Scheduler (Celery Beat)** — fires the channel-poll task every 15 minutes and the
daily-report task once a day. Beat schedule is data-driven from the `channels` table
(`polling_interval_seconds` per channel) so cadence is configurable per channel, not
hardcoded.

**Ingestion workers** — pull the channel's upload feed (YouTube Data API
`search.list`/`playlistItems.list` against the uploads playlist, cheaper on quota than
`search.list`), diff against known `external_video_id`s, and enqueue one pipeline per
new video. Also polls for live/scheduled broadcast status transitions.

**Transcript workers** — try, in order: (1) YouTube's own timed-text captions via
`youtube-transcript-api`/`yt-dlp` subtitle extraction (free, fast, usually
auto-generated captions are good enough), (2) if unavailable, download audio only
(`yt-dlp -x`) and run Whisper (local `faster-whisper` on a GPU-enabled worker pool, or
OpenAI's hosted Whisper API for burst capacity) to generate the transcript. Transcript
is stored both as one full-text blob and as time-coded segments (needed later for RAG
citation timestamps).

**AI analysis workers** — a fan-out/fan-in (Celery `chord`) of independent LLM calls
against the same transcript: executive summary, detailed summary, investment thesis,
company/ticker extraction, topic tagging, sentiment, quotes, key numbers, actionable
insights. Fanning these out in parallel (rather than one mega-prompt) keeps each prompt
focused, keeps outputs independently retryable, and lets us swap/upgrade one extractor
without re-running the rest.

**Embedding workers** — chunk each transcript into ~500-token overlapping windows aligned
to sentence/caption boundaries, call OpenAI embeddings, and upsert into the `embeddings`
table (pgvector). Chunk-level embeddings (not one embedding per video) are what make
timestamp-cited RAG possible.

**Search & RAG service** — hybrid search: pgvector cosine similarity over chunk
embeddings, combined with Postgres full-text search (`tsvector`) and structured filters
(ticker, channel, date range). The chat assistant is retrieval-augmented: embed the
question, retrieve top-k chunks (with metadata), build a grounded prompt, and require the
LLM to cite `(video_title, creator, published_date, timestamp)` per claim — the citation
fields are passed into the prompt as structured context, not left to the model to invent.

**Reporting service** — a scheduled aggregation job (not an LLM call over everything)
that queries structured tables (mentions, sentiment, tickers) for the trailing 24h, plus
one LLM synthesis pass over the day's top summaries/quotes to write the narrative
sections (conflicting opinions, interesting insights).

**Object storage** — raw audio/video is cached only long enough to transcribe (ephemeral,
deleted after success) unless the user opts to retain it; transcripts and thumbnails are
retained permanently. Local disk volume in Docker Compose for dev; S3-compatible bucket
in production.

## 3. Video Processing State Machine

Every video moves through an explicit, persisted state (`videos.pipeline_status`) so any
step can fail and retry independently without reprocessing earlier steps or double-billing
LLM calls:

```
DISCOVERED → METADATA_SYNCED → TRANSCRIPT_PENDING → TRANSCRIPT_READY
           → ANALYSIS_PENDING → ANALYZED → EMBEDDING_PENDING → EMBEDDED
           → INDEXED (terminal success)
Any state → FAILED (with failure_reason, retry_count, next_retry_at)
```

`FAILED` is not a dead end — a `retry_failed_pipelines` beat task periodically requeues
failures below a max-retry threshold with exponential backoff, and anything past the
threshold is surfaced via the admin API for manual inspection rather than retried forever.

## 4. Key Architectural Decisions

**Celery + Redis over Kafka/stream processing.** This workload is task-shaped (discrete
units of work per video with clear success/failure and per-task retry), not a continuous
high-volume event stream. Celery gives per-task retry/backoff, priority queues, and a
simple ops story (one broker) for the expected volume (dozens of channels, tens of new
videos/day). If ingestion volume grows by orders of magnitude later, the ingestion layer
can be swapped for a Kafka-based pipeline behind the same repository/service interfaces
without touching the AI or serving layers.

**pgvector over a dedicated vector database (Pinecone/Weaviate/Qdrant).** Keeping
embeddings in the same PostgreSQL instance as the relational data means a single
transactional source of truth (a video's embeddings can never exist without its
transcript row), one database to operate/back up, and SQL joins between vector search
and structured filters (ticker, date, channel) in one query instead of a
merge-in-application-code step. pgvector's HNSW index is sufficient for a personal/small-
team corpus (low hundreds of thousands of chunks). Access goes through an
`EmbeddingRepository` interface, so migrating to a dedicated vector store later — if
corpus size or query latency demands it — is a swap behind that interface, not a rewrite.

**Provider abstraction (ports & adapters) for every external dependency.** Video source
(YouTube today, podcast RSS/Twitter later), transcription (captions vs. local Whisper vs.
OpenAI Whisper API), and LLM (OpenAI today) are each defined as an abstract interface in
`app/providers/*/base.py` with concrete adapters implementing it. Business logic in
`services/` depends only on the interface. This is the mechanism that makes "Phase 1
focuses on YouTube" actually mean something — adding a source later is additive.

**Explicit pipeline state machine over "fire and hope."** Video processing spans
external network calls (YouTube, Whisper, OpenAI) that will fail transiently. Persisting
state after every step means a crashed worker or a rate-limited API call loses at most one
step of progress, retries are idempotent (re-running `METADATA_SYNCED → TRANSCRIPT_READY`
doesn't re-fetch metadata), and the system is debuggable by reading one column.

**Multi-user-ready schema from day one, even for a single-user deployment.** `users`,
`bookmarks`, and `watchlists` are first-class tables with foreign keys from day one. It
costs nothing to add now and avoids a painful migration if this becomes a shared/team tool
later — every "personal Bloomberg terminal" eventually gets a second user.

**FastAPI + async SQLAlchemy.** The workload is I/O-bound (waiting on YouTube, OpenAI,
Postgres) far more than CPU-bound, so async request handling matters. FastAPI's native
Pydantic integration also gives us request/response schema validation and OpenAPI docs
for free, which matters for a REST surface this wide (9 resource groups).

## 5. Cross-Cutting Concerns

- **Idempotency & locking.** A Redis lock keyed by `video_id` wraps each pipeline stage
  so a duplicate Celery task (e.g., from a retry race) can't process the same video twice.
- **Quota management.** YouTube Data API has a fixed daily unit quota. A `QuotaTracker`
  service records unit spend per call type and the channel poller throttles/backs off
  before hitting the ceiling rather than failing loudly.
- **Cost tracking.** Every OpenAI call (LLM + embeddings) is logged with token counts and
  estimated cost against the `video_id`, rolled up into a daily spend metric — important
  once dozens of channels are polled continuously.
- **Observability.** Structured JSON logging, correlation ID per pipeline run, Celery task
  events exported to Prometheus, error tracking via Sentry. Every failure is queryable by
  video/channel/task type, not just visible in logs.
- **Security.** Admin endpoints (channel config, retry triggers) require an authenticated
  admin role; read endpoints (search, videos, reports) can be opened more permissively
  depending on deployment (single-user vs. shared).
