# Mw-StockMarket-Analytics — System Context

> **Purpose:** Give any AI assistant full understanding of this project so it can continue work exactly as established. Read this file before making any changes.

---

## Project Summary

AI-powered platform that ingests YouTube financial videos, transcribes them, runs 8 parallel LLM analysis extractors, stores vector embeddings in pgvector, and exposes a REST API for search, RAG chat, and analytics. **No OpenAI API key required** — uses Groq (free Whisper) + Ollama (free local LLM).

**Stack:** FastAPI · PostgreSQL 16 + pgvector · Redis 7 · Celery 5 · SQLAlchemy 2 async · Python 3.11 · Docker Compose

---

## Repository Layout

```
Mw-StockMarket-Analytics/
├── backend/
│   ├── app/
│   │   ├── api/v1/routers/      # 12 FastAPI routers
│   │   ├── core/                # config, security, logging, exceptions, celery_app
│   │   ├── db/                  # session.py, base.py, migrations/
│   │   ├── models/              # 17 SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic request/response models
│   │   ├── repositories/        # Data access layer (one per model group)
│   │   ├── services/            # Business logic
│   │   ├── providers/
│   │   │   ├── llm/             # ollama_provider.py, openai_provider.py
│   │   │   ├── transcription/   # groq_provider.py, whisper_api_provider.py, youtube_captions_provider.py
│   │   │   └── video_platforms/ # ytdlp_provider.py, youtube_provider.py
│   │   ├── workers/
│   │   │   ├── pipeline.py      # Celery canvas wiring
│   │   │   └── tasks/           # discovery, transcript, analysis, embedding, report, maintenance
│   │   ├── prompts/             # LLM prompt templates (executive_summary, investment_thesis, etc.)
│   │   └── utils/chunking.py    # Transcript → overlapping chunks for embeddings
│   ├── Dockerfile               # API image
│   ├── Dockerfile.worker        # Workers image (includes ffmpeg, Groq, yt-dlp)
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── .env                     # See environment variables section
├── infra/
│   └── docker-compose.yml       # 9 services
└── SYSTEM-CONTEXT.md            # This file
```

---

## Docker Services

| Container | Image | Purpose | Port |
|-----------|-------|---------|------|
| `mw_postgres` | pgvector/pgvector:pg16 | Database + pgvector | 5432 |
| `mw_redis` | redis:7-alpine | Celery broker + RAG session store | 6379 |
| `mw_ollama` | ollama/ollama:latest | Local LLM fallback | 11434 |
| `mw_api` | backend/Dockerfile | FastAPI (uvicorn --reload) | 8000 |
| `mw_worker_discovery` | backend/Dockerfile.worker | Celery: discovery, maintenance queues | — |
| `mw_worker_transcription` | backend/Dockerfile.worker | Celery: transcription queue (pool=solo) | — |
| `mw_worker_analysis` | backend/Dockerfile.worker | Celery: analysis + embedding queues | — |
| `mw_worker_reports` | backend/Dockerfile.worker | Celery: reports queue | — |
| `mw_beat` | backend/Dockerfile.worker | Celery Beat scheduler | — |

**Start everything:**
```powershell
cd infra
docker-compose up -d
```

**After code changes to workers (not hot-reloaded):**
```powershell
docker restart mw_worker_analysis mw_worker_transcription mw_worker_discovery
```

**After code changes to API (hot-reloaded via --reload):**
No restart needed, uvicorn watches the mounted volume.

---

## Environment Variables (backend/.env)

```ini
# App
APP_ENV=development
SECRET_KEY=changeme-use-openssl-rand-hex-32
ADMIN_API_KEY=changeme-admin-key

# Database — Docker overrides these to use container hostnames
DATABASE_URL=postgresql+asyncpg://mw_user:mw_pass@localhost:5432/mw_stockmarket
DATABASE_URL_SYNC=postgresql://mw_user:mw_pass@localhost:5432/mw_stockmarket

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# YouTube (optional — only needed for channel-based discovery, NOT for process-url endpoint)
YOUTUBE_API_KEY=your-youtube-api-key-here

# OpenAI (optional — only used when LLM_PROVIDER=openai)
OPENAI_API_KEY=your-openai-api-key-here

# Ollama — LLM + Embeddings (FREE)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=https://single-darkness-estrogen.ngrok-free.dev  # ngrok tunnel to Colab GPU
OLLAMA_LLM_MODEL=mistral:latest
OLLAMA_EMBEDDING_MODEL=nomic-embed-text:latest

# Groq — Transcription (FREE)
WHISPER_MODE=groq
GROQ_API_KEY=<your-groq-api-key>

# Misc
MEDIA_CACHE_DIR=/tmp/mw_media_cache
MAX_PIPELINE_RETRIES=5
```

> **IMPORTANT:** The `OLLAMA_BASE_URL` points to a Google Colab ngrok tunnel for GPU acceleration. When the Colab session expires, update this URL to either the new ngrok URL or `http://ollama:11434` (local Docker Ollama). See the **Ollama / Colab GPU** section below.

---

## Key Design Decisions

### 1. No YouTube API Key Required for Single-Video Processing
`POST /api/v1/videos/process-url?url=<youtube_url>` uses `yt-dlp` to scrape metadata. No API key needed.

### 2. `create_worker_session()` — NOT `get_async_session()`
**Always use `create_worker_session()` in Celery worker tasks.** Each `asyncio.run()` call creates a new event loop. Using the module-level engine in `get_async_session()` causes `asyncpg.InterfaceError: another operation is in progress`. The worker session uses `NullPool` to create a fresh connection per task.

```python
# ✅ CORRECT in worker tasks
async with create_worker_session() as session:
    ...

# ❌ WRONG in worker tasks (will cause asyncpg cross-loop errors)
async with get_async_session() as session:
    ...
```

### 3. Celery Task Registration
All task modules must be explicitly imported in `celery_app.py` via `_import_all_tasks()`. Autodiscovery alone doesn't reliably register tasks before the worker starts accepting jobs.

### 4. Embedding Dimensions = 768
The `embeddings` table uses `VECTOR(768)` for `nomic-embed-text`. If switching to OpenAI (`text-embedding-3-small` = 1536 dims), a new migration is required to alter the column. Migration `0002` handles the 1536→768 change.

### 5. Lazy Relationship Loading Forbidden in Workers
`video.channel.display_name` triggers a lazy load. With `NullPool`, the connection is gone after the initial query. Always use `selectinload` when you need relationships, or fetch the channel name in a separate query.

```python
# ✅ CORRECT
from sqlalchemy.orm import selectinload
result = await session.execute(
    select(Video).options(selectinload(Video.channel)).where(Video.id == video_id)
)
video = result.scalar_one()
channel_name = video.channel.display_name  # now safe

# ❌ WRONG — lazy load on closed connection
video = await repo.get_by_id(video_id)
channel_name = video.channel.display_name  # MissingGreenlet error
```

### 6. Datetime Timezone — Always Naive UTC in DB
PostgreSQL columns are `TIMESTAMP WITHOUT TIME ZONE` storing naive UTC. Never pass timezone-aware datetimes to DB queries.

```python
# ✅ CORRECT
from datetime import datetime
published_at = datetime.utcnow()
since = datetime.utcnow() - timedelta(days=7)

# ❌ WRONG — causes DataError
from datetime import datetime, timezone
published_at = datetime.now(timezone.utc)  # timezone-aware
```

### 7. ngrok Header for Ollama via Colab
When `OLLAMA_BASE_URL` contains "ngrok", the `OllamaProvider` automatically adds `ngrok-skip-browser-warning: true` to all requests. This bypasses ngrok's interstitial browser warning page.

---

## Pipeline State Machine

Videos progress through these states:

```
DISCOVERED → TRANSCRIPT_PENDING → TRANSCRIPT_READY → ANALYSIS_PENDING
          → ANALYZED → EMBEDDING_PENDING → EMBEDDED → INDEXED
          → FAILED (at any stage)
```

**Trigger pipeline from a URL (no API key needed):**
```powershell
Invoke-WebRequest -UseBasicParsing -Method POST `
  "http://localhost:8000/api/v1/videos/process-url?url=https://youtu.be/VIDEO_ID"
```

**Retry a failed video from a specific stage:**
```powershell
Invoke-WebRequest -UseBasicParsing -Method POST `
  "http://localhost:8000/api/v1/videos/1/reprocess?from_stage=ANALYSIS_PENDING" `
  -Headers @{"X-Admin-Key"="changeme-admin-key"}
```

Valid `from_stage` values: `DISCOVERED`, `TRANSCRIPT_PENDING`, `ANALYSIS_PENDING`, `EMBEDDING_PENDING`

---

## Celery Task Architecture

### Queues and Workers

| Queue | Worker | Tasks |
|-------|--------|-------|
| `discovery` | mw_worker_discovery | poll_channel, process_single_video_url, refresh_video_stats |
| `maintenance` | mw_worker_discovery | retry_failed_pipelines, cleanup_media_cache, reset_quota_counters |
| `transcription` | mw_worker_transcription | fetch_captions, run_whisper |
| `analysis` | mw_worker_analysis | 8 extractors + mark_analysis_complete |
| `embedding` | mw_worker_analysis | chunk_and_embed, mark_indexed |
| `reports` | mw_worker_reports | generate_daily_report |

### Analysis Chord
8 tasks run in **parallel** via a Celery chord, then `mark_analysis_complete` fires:
- `generate_executive_summary` → run_summary
- `extract_investment_thesis` → run_thesis
- `extract_companies_and_tickers` → run_entities
- `classify_topics` → run_topics
- `score_sentiment` → run_sentiment
- `extract_quotes` → run_quotes
- `extract_key_numbers` → run_key_numbers
- `generate_actionable_insights` → run_insights

`mark_analysis_complete` advances to `ANALYZED` and enqueues `chunk_and_embed`.

### Beat Schedule

| Job | Schedule |
|-----|----------|
| `retry-failed-pipelines` | Every 10 min |
| `refresh-video-stats` | Every 6 hours |
| `generate-daily-report` | Daily at 06:00 UTC |
| `cleanup-media-cache` | Daily at 03:00 UTC |
| `reset-quota-counters` | Daily at 00:00 UTC |

> `poll-all-channels` is **disabled** — requires YouTube API key. Enable it in `celery_app.py` if you have one.

---

## AI Provider Configuration

### Transcription: Groq Whisper (FREE)
- Model: `whisper-large-v3`
- Limit: 25MB file size, 7000 requests/day
- Key: configured in `.env` as `GROQ_API_KEY`
- Downloads audio via `yt-dlp`, sends to Groq, deletes audio after
- Fallback waterfall: YouTube captions → Groq Whisper

### LLM + Embeddings: Ollama (FREE)
- LLM: `mistral:latest` (or `llama3.1:latest`)
- Embeddings: `nomic-embed-text:latest` (768 dimensions)
- Normally runs locally or in Docker (`http://ollama:11434`)
- **Currently configured to use Google Colab T4 GPU via ngrok** for ~10x speed

### Ollama on Google Colab Setup

When Colab session expires, run this notebook again and update `.env`:

```python
# Cell 1 — Install
!sudo apt-get install -y zstd curl
!curl -fsSL https://ollama.com/install.sh | sh

# Cell 2 — Start server
import subprocess, threading, time, os
env = os.environ.copy()
env["OLLAMA_HOST"] = "0.0.0.0"
def run_ollama():
    subprocess.run(["ollama", "serve"], env=env)
threading.Thread(target=run_ollama, daemon=True).start()
time.sleep(8)

# Cell 3 — Pull models
!ollama pull mistral:latest
!ollama pull nomic-embed-text:latest

# Cell 4 — Expose via ngrok
!pip install -q pyngrok
from pyngrok import ngrok, conf
conf.get_default().auth_token = "3FzVODbYpxql243oIWnb5CfURVt_72socAveAn2119XUQBLGD"
tunnel = ngrok.connect(11434, "http")
print(f"OLLAMA_BASE_URL = {tunnel.public_url}")
# Paste this URL into backend/.env OLLAMA_BASE_URL
# Then restart: docker restart mw_api mw_worker_analysis mw_worker_reports

# Cell 5 — Keep alive
import time, urllib.request
while True:
    time.sleep(30)
    urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
    print(".", end="", flush=True)
```

**After getting new URL, update two places:**
1. `backend/.env` → `OLLAMA_BASE_URL=https://new-url.ngrok-free.dev`
2. `infra/docker-compose.yml` → Update all `OLLAMA_BASE_URL` entries
3. Restart: `docker restart mw_api mw_worker_analysis mw_worker_transcription mw_worker_discovery mw_worker_reports`

**Switch back to local Ollama (no Colab):**
```ini
OLLAMA_BASE_URL=http://ollama:11434
```

---

## API Endpoints

**Base URL:** `http://localhost:8000`
**API Docs:** `http://localhost:8000/api/docs`
**Admin Key Header:** `X-Admin-Key: changeme-admin-key`

### Videos
| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/api/v1/videos/process-url?url=<yt_url>` | **Main entry point** — no API key needed, uses yt-dlp |
| `GET` | `/api/v1/videos` | List with filters: channel_id, pipeline_status, date range |
| `GET` | `/api/v1/videos/{id}` | Get video with pipeline status |
| `POST` | `/api/v1/videos/{id}/reprocess?from_stage=X` | Admin: retry from stage (requires X-Admin-Key) |

### Analysis Results (all return 404 if video not yet at that stage)
| Method | Path |
|--------|------|
| `GET` | `/api/v1/videos/{id}/transcript` |
| `GET` | `/api/v1/videos/{id}/summary` |
| `GET` | `/api/v1/videos/{id}/sentiment` |
| `GET` | `/api/v1/videos/{id}/companies` |
| `GET` | `/api/v1/videos/{id}/key-numbers` |
| `GET` | `/api/v1/videos/{id}/insights` |
| `GET` | `/api/v1/videos/{id}/quotes` |

### Analytics
| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/v1/analytics/trending-stocks?window=7d` | window: 24h, 7d, 30d |
| `GET` | `/api/v1/analytics/trending-sectors?window=7d` | |
| `GET` | `/api/v1/analytics/sector-heatmap?window=7d` | |
| `GET` | `/api/v1/analytics/sentiment/{ticker}?window=7d` | Time series |
| `GET` | `/api/v1/analytics/creator/{channel_id}?window=30d` | |

### Search
| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/v1/search?q=nvidia` | Structured SQL search |
| `POST` | `/api/v1/search/semantic` | pgvector cosine similarity |

### Chat (RAG)
| Method | Path |
|--------|------|
| `POST` | `/api/v1/chat/sessions` |
| `POST` | `/api/v1/chat/sessions/{id}/messages` |
| `GET` | `/api/v1/chat/sessions/{id}/messages` |

### Admin (all require X-Admin-Key)
| Method | Path |
|--------|------|
| `GET` | `/api/v1/admin/pipeline/status` |
| `GET` | `/api/v1/admin/pipeline/failures` |
| `POST` | `/api/v1/admin/pipeline/retry/{video_id}` |
| `GET` | `/api/v1/admin/quota` |
| `GET` | `/api/v1/admin/task-logs` |
| `GET` | `/api/v1/admin/users` |
| `GET` | `/api/v1/scheduler/jobs` |
| `POST` | `/api/v1/scheduler/jobs/{name}/trigger` |

---

## Database Schema

### Core Tables

| Table | Purpose |
|-------|---------|
| `channels` | YouTube channels (platform + external_channel_id unique) |
| `videos` | Video metadata + pipeline state machine |
| `transcripts` | Full text + source + language |
| `transcript_segments` | Timestamped segments (start/end seconds) |
| `embeddings` | `VECTOR(768)` with HNSW cosine index |
| `summaries` | JSONB executive bullets + detailed text |
| `investment_theses` | Bull/bear/risks/catalysts |
| `sentiments` | bullish/bearish/neutral percentages |
| `companies` | Name + sector + industry |
| `tickers` | symbol + exchange + FK to company |
| `video_companies` | Junction: video ↔ company + mention_count |
| `key_numbers` | Extracted financial figures |
| `actionable_insights` | Watchlist items / catalysts |
| `topics` + `video_topics` | Theme classification |
| `daily_reports` | Generated market summaries |
| `users` | Auth (email + hashed_password + role) |
| `bookmarks` | User ↔ video |
| `task_logs` | Celery task execution history |

### Migrations
```powershell
# Run all migrations
docker exec mw_api alembic upgrade head

# Create new migration
docker exec mw_api alembic revision --autogenerate -m "description"
```

Migration `0001` — initial schema
Migration `0002` — changed embeddings from `VECTOR(1536)` → `VECTOR(768)` for nomic-embed-text

---

## Known Bugs and Fixes Applied

### Bug 1: asyncpg Cross-Event-Loop Error
**Symptom:** `InterfaceError: cannot perform operation: another operation is in progress`
**Root Cause:** Module-level SQLAlchemy engine is shared across Celery worker processes. Each `asyncio.run()` creates a new event loop but the connection pool was created in a different loop.
**Fix:** `create_worker_session()` in `backend/app/db/session.py` creates a fresh engine with `NullPool` on every call. All worker tasks must use this, never `get_async_session()`.

### Bug 2: MissingGreenlet (Lazy Relationship Load)
**Symptom:** `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called`
**Root Cause:** `NullPool` closes the connection immediately after the initial query. Accessing `video.channel.display_name` tries to lazy-load but the connection is gone.
**Fix:** Use `selectinload(Video.channel)` when fetching videos that need `video.channel.display_name`.

### Bug 3: Groq Segment Parsing
**Symptom:** `'dict' object has no attribute 'text'`
**Root Cause:** Groq's `verbose_json` response returns segments as plain dicts, not objects with `.text/.start/.end` attributes.
**Fix:** In `groq_provider.py`, use `_get(seg, key)` helper that checks `isinstance(seg, dict)` and uses `seg[key]` vs `getattr(seg, key)`.

### Bug 4: yt-dlp Timezone in published_at
**Symptom:** `DataError: invalid input for query argument: can't subtract offset-naive and offset-aware datetimes`
**Root Cause:** `datetime.strptime(...).replace(tzinfo=timezone.utc)` creates timezone-aware datetime, but DB column is `TIMESTAMP WITHOUT TIME ZONE`.
**Fix:** In `ytdlp_provider.py`, use `datetime.strptime(upload_date_str, "%Y%m%d")` (no timezone).

### Bug 5: Celery Task Factory `__name__` AttributeError
**Symptom:** `AttributeError: property '__name__' of '_task' object has no setter`
**Root Cause:** `_task.__name__ = method` fails on Celery task proxy objects.
**Fix:** Removed the `__name__` assignment from `_make_task()` factory in `analysis_tasks.py`.

### Bug 6: Ollama `NullPool` + `pool_size` Conflict
**Symptom:** `TypeError: Invalid argument(s) 'pool_size','max_overflow' sent to create_engine()`
**Root Cause:** `NullPool` doesn't accept pool sizing arguments.
**Fix:** Removed `pool_size` and `max_overflow` from `create_worker_session()` engine kwargs.

### Bug 7: Logger `name` Key Conflict
**Symptom:** `KeyError: "Attempt to overwrite 'name' in LogRecord"`
**Root Cause:** Passing `name=...` in `extra={}` to logger conflicts with Python's built-in `LogRecord.name` attribute.
**Fix:** Renamed `name` to `display_name` or `channel_name` in all logger `extra` dicts.

---

## Testing the Pipeline

### Quick Health Check
```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health
# Expected: {"status":"healthy","environment":"development"}
```

### Submit a YouTube Video
```powershell
$resp = Invoke-WebRequest -UseBasicParsing -Method POST `
  "http://localhost:8000/api/v1/videos/process-url?url=https://youtu.be/iV_BAY2Ptpo" |
  ConvertFrom-Json
Write-Host "Task: $($resp.task_id)"
```

### Monitor Pipeline Progress
```powershell
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 15
    $v = Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/videos/1" | ConvertFrom-Json
    Write-Host "$(Get-Date -Format 'HH:mm:ss') | $($v.pipeline_status)"
    if ($v.pipeline_status -in @("INDEXED","FAILED")) { break }
}
```

### Check Results
```powershell
# Summary
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/videos/1/summary" |
  ConvertFrom-Json | Format-List

# Sentiment
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/videos/1/sentiment" |
  ConvertFrom-Json | Format-List

# Companies/tickers extracted
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/videos/1/companies" |
  ConvertFrom-Json | Format-Table
```

### Monitor Worker Logs (side by side with status)
```powershell
# In one terminal — pipeline status polling
while ($true) {
    $v = (Invoke-WebRequest -UseBasicParsing http://localhost:8000/api/v1/videos/1 | ConvertFrom-Json)
    Write-Host "$(Get-Date -Format 'HH:mm:ss') STATUS: $($v.pipeline_status)"
    Start-Sleep 10
}

# In another terminal — worker logs
docker logs mw_worker_analysis -f 2>&1 |
  Where-Object { $_ -match "succeeded|ERROR|Ollama|HTTP|saved" }
```

---

## Adding More Videos / Channels

### Single Video (no API key needed)
```powershell
Invoke-WebRequest -UseBasicParsing -Method POST `
  "http://localhost:8000/api/v1/videos/process-url?url=https://youtu.be/VIDEO_ID"
```

### Add a YouTube Channel (requires YouTube API key)
```powershell
Invoke-WebRequest -UseBasicParsing -Method POST `
  "http://localhost:8000/api/v1/channels" `
  -Headers @{"X-Admin-Key"="changeme-admin-key"; "Content-Type"="application/json"} `
  -Body '{"platform":"youtube","handle":"@CNBC","include_shorts":false}'
```

### Retry All Failed Videos
```powershell
Invoke-WebRequest -UseBasicParsing -Method POST `
  "http://localhost:8000/api/v1/scheduler/jobs/retry-failed-pipelines/trigger" `
  -Headers @{"X-Admin-Key"="changeme-admin-key"}
```

---

## Performance Notes

| Operation | Without Colab GPU | With Colab T4 GPU |
|-----------|------------------|-------------------|
| First LLM response (model load) | 360s | ~100s |
| Subsequent LLM responses | ~30-60s/task | ~2-15s/task |
| Embedding generation (per batch) | ~60s | ~5s |
| Groq transcription (12min video) | ~30s (network) | ~30s (network) |

> Groq transcription speed is independent of GPU — it's a remote API call.

---

## What's NOT Implemented (Phase 1B+)

- No unit tests (only manual smoke tests)
- No frontend UI
- No article/PDF ingestion (YouTube only currently)
- No email notifications
- No Prometheus dashboards (metrics exported but not visualized)
- No CI/CD pipeline
- No multi-user auth enforcement (admin key auth only for writes)
- Watchlist/bookmark schema exists but endpoints are stubs

---

*Last updated: July 3, 2026 — Phase 1A complete, pipeline debugging in progress*
