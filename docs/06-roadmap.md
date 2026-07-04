# Development Roadmap

Module-by-module, each phase produces something runnable and testable before the next
starts. Phase 1 (backend, YouTube-only) is the scope of the current build; Phase 2+ are
sequenced but not started until Phase 1 is solid.

## Phase 0 — Foundations
- Repo scaffold matching `02-folder-structure.md`.
- `docker-compose.yml`: Postgres+pgvector, Redis, backend API, placeholder worker/beat.
- `core/config.py` (Pydantic Settings), `.env.example`, structured logging, Alembic wired
  to the models in `03-database-schema.md`.
- CI skeleton: lint (ruff), type-check (mypy), test (pytest) on every push.
- **Exit criteria:** `docker compose up` boots Postgres + Redis + a FastAPI app that
  responds on `/health`; `alembic upgrade head` creates every table.

## Phase 1a — Channel & Video Discovery
- `providers/video_platforms/youtube_provider.py` (YouTube Data API v3 client: channel
  lookup, uploads-playlist paging, live/scheduled status).
- `channel_discovery_service.py`, `discovery_tasks.py::poll_channel`.
- Seed the 17 channels from the project brief via a migration/seed script (configurable,
  not hardcoded — matches the "channel list must be configurable" requirement).
- `channels` and `videos` REST endpoints (read + admin CRUD).
- Quota tracker (Redis-backed) wired into every YouTube call.
- **Exit criteria:** running `poll_channel` against a real channel inserts new `videos`
  rows with full metadata and moves them to `METADATA_SYNCED`; re-running is a no-op for
  already-seen videos.

## Phase 1b — Transcript Pipeline
- `providers/transcription/youtube_captions_provider.py` (captions-first path).
- `providers/transcription/whisper_local_provider.py` + `whisper_api_provider.py`
  (fallback path), `transcript_tasks.py`.
- Transcript + `transcript_segments` persistence, `/videos/{id}/transcript` endpoint.
- **Exit criteria:** a video with captions gets a transcript via the fast path; a video
  without captions falls back to Whisper and produces an equivalent transcript with
  timestamped segments.

## Phase 1c — AI Analysis Pipeline
- `providers/llm/openai_provider.py`, prompt templates in `prompts/` for each of the
  9 extractors (summary, detailed summary, thesis, companies/tickers, topics, sentiment,
  quotes, key numbers, actionable insights).
- `analysis_service.py`, `analysis_tasks.py`, the chord wiring from
  `05-worker-architecture.md`.
- Corresponding `/videos/{id}/summary|thesis|sentiment|quotes|key-numbers|insights`
  endpoints.
- **Exit criteria:** a transcript produces all nine analysis artifacts, each stored in
  its own table, independently retryable, video reaches `ANALYZED`.

## Phase 1d — Embeddings & Semantic Search / RAG
- `utils/chunking.py`, `embedding_service.py`, `embedding_tasks.py`.
- `embeddings` table populated via pgvector, HNSW index tuned.
- `/search/semantic` endpoint (structured `/search` can ship in parallel since it's pure
  SQL over already-existing tables).
- `rag_chat_service.py` + `/chat` endpoints with citation validation against the
  retrieval set.
- **Exit criteria:** `"What did analysts say about Nvidia?"` returns a grounded, cited
  answer pulling from at least two different videos/creators.

## Phase 1e — Daily Report
- `report_service.py`: structured aggregation queries (mentions, sentiment, top
  videos/quotes) + one LLM synthesis pass for narrative sections.
- `report_tasks.py::generate_daily_report`, `/reports` endpoints.
- **Exit criteria:** a report is generated automatically at the scheduled time and is
  fetchable via the API for any past date once generated.

## Phase 1f — API Completion, Watchlist, Admin, Scheduler
- `watchlist_service.py`, bookmarks, `/watchlist` and `/bookmarks` endpoints.
- `/admin` (pipeline status/failures/retry, quota, task logs) and `/scheduler`
  (list/trigger/update jobs) endpoints.
- Auth: JWT issuance/verification, admin role gate.
- **Exit criteria:** every endpoint in `04-api-design.md` is implemented, documented via
  FastAPI's generated OpenAPI schema, and covered by at least one integration test.

## Phase 1g — Hardening
- Unit tests for every service/provider (mocked externals); integration tests for
  repositories against a real Postgres+pgvector (testcontainers).
- Load-test the discovery + analysis queues at expected channel-count volume.
- Sentry error tracking, Prometheus metrics export, structured request logging.
- Production `docker-compose.prod.yml`, resource limits per worker pool.
- **Exit criteria:** CI green (lint, types, unit, integration), documented runbook for
  common failure modes (quota exhaustion, stuck pipeline, worker crash recovery).

## Phase 2 — Frontend (Next.js)
- App shell, dark mode, auth, TanStack Query wired to the v1 API.
- Dashboard: latest videos, trending stocks/companies, sentiment graphs, sector heatmap.
- Search UI (structured filters + semantic search bar), video detail page (summary,
  thesis, quotes, key numbers, insights, embedded citations).
- Chat assistant UI with streaming + clickable timestamped citations.
- Watchlist, daily digest view, admin panel.

## Phase 3 — Additional Sources
- Podcast RSS adapter (where transcripts exist) behind the existing
  `VideoPlatformProvider`/`TranscriptionProvider` interfaces — additive, no core rewrite.
- Earnings call recording ingestion (often longer-form audio, may need chunked
  transcription).
- Twitter/X video adapter (deferred until X API access/cost is evaluated).

## Sequencing Rationale

Discovery → transcript → analysis → embeddings → reports is a strict dependency chain
(you cannot summarize a transcript that doesn't exist), so phases 1a-1e are ordered, not
parallelizable, for a single engineer/session. API completion (1f) and hardening (1g)
are pulled to the end deliberately: building admin/scheduler endpoints against a pipeline
that doesn't exist yet would mean mocking the very thing they're meant to operate.
Frontend is entirely gated on the API being stable, per the original brief's "Phase 1 is
backend only."
