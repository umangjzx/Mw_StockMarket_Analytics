# Background Worker Architecture

Celery 5.x with Redis as both broker and result backend. Redis is also used for
distributed locks and the quota tracker's counters — one piece of infra doing three
jobs at this scale, rather than introducing RabbitMQ + a separate lock service.

## 1. Queues

Separate named queues, each with its own worker pool sized for its workload's
resource profile:

| Queue | Handles | Concurrency model |
|---|---|---|
| `discovery` | Channel polling, video metadata sync | High concurrency, I/O-bound (YouTube API calls) |
| `transcription` | Caption fetch, Whisper transcription | Low concurrency, CPU/GPU-bound. Whisper tasks routed to workers with model weights loaded |
| `analysis` | All LLM extraction tasks (summary, thesis, entities, sentiment, quotes, key numbers, insights) | High concurrency, I/O-bound (OpenAI calls), rate-limited to respect OpenAI RPM/TPM |
| `embedding` | Chunking + embedding generation + pgvector upsert | Medium concurrency, batched calls to the embeddings API |
| `reports` | Daily report generation | Low concurrency, one job/day, can run alongside `analysis` |
| `maintenance` | Retry sweeps, media cache cleanup, quota resets | Low concurrency, scheduled only |

Routing is explicit in `celery_app.py` (`task_routes`), not left to the default queue,
so a spike in transcription volume can't starve the API-adjacent `analysis` queue.

## 2. Celery Beat Schedule

Beat schedule entries are seeded from `core/config.py` defaults but the actual source
of truth is a `scheduled_jobs` table (name, cron/interval, enabled) read via
`django-celery-beat`-style database scheduler equivalent (`celery-sqlalchemy-scheduler`
or a small custom `Scheduler` subclass) — this is what makes `/scheduler` API endpoints
meaningful (PATCHing a job's cadence actually changes behavior without a redeploy).

Default jobs:

| Job | Cadence | Task |
|---|---|---|
| `poll_all_channels` | every 15 minutes | fans out one `poll_channel(channel_id)` task per active channel |
| `retry_failed_pipelines` | every 10 minutes | requeues `FAILED` videos where `pipeline_retry_count < max_retries` and `pipeline_next_retry_at <= now()` |
| `generate_daily_report` | daily at 06:00 local | aggregates prior 24h and writes `daily_reports` |
| `refresh_video_stats` | every 6 hours | re-fetches view/like/comment counts for videos published in the last 14 days, writes `video_stat_snapshots` |
| `cleanup_media_cache` | daily at 03:00 | deletes cached audio/video files older than retention window |
| `reset_quota_counters` | daily at 00:00 UTC | resets the YouTube API daily quota counter in Redis |

`poll_all_channels` fans out rather than looping serially inside one task so a slow or
failing channel doesn't delay polling the other 16+ configured channels, and so
per-channel failures are isolated and independently retryable.

## 3. Per-Video Pipeline (Celery Canvas)

Each newly discovered video runs through a chain, with a chord for the
independently-parallelizable analysis step:

```python
pipeline = chain(
    sync_video_metadata.s(video_id),
    fetch_or_generate_transcript.s(),
    chord(
        group(
            generate_executive_summary.s(),
            generate_detailed_summary.s(),
            extract_investment_thesis.s(),
            extract_companies_and_tickers.s(),
            classify_topics.s(),
            score_sentiment.s(),
            extract_quotes.s(),
            extract_key_numbers.s(),
            generate_actionable_insights.s(),
        ),
        mark_analysis_complete.s(),
    ),
    chunk_and_embed.s(),
    mark_indexed.s(),
)
```

Each task updates `videos.pipeline_status` on entry/exit so a crash mid-chain leaves an
accurate resume point, and `mark_analysis_complete` only transitions the video to
`ANALYZED` once every member of the chord has either succeeded or exhausted its own
retries — a failure in, say, `extract_key_numbers` doesn't block the executive summary
from being available, but it does keep the video out of `ANALYZED` until it's resolved
or explicitly skipped by an admin.

## 4. Retry Policy

- **Transient errors** (timeouts, 5xx, rate limits): Celery's `autoretry_for` with
  exponential backoff (`retry_backoff=True, retry_backoff_max=600, max_retries=5`) plus
  jitter, so a whole batch of tasks hitting a rate limit at once doesn't retry in lockstep.
- **Quota/rate-limit errors specifically** (YouTube 403 quota exceeded, OpenAI 429): caught
  separately and rescheduled via `pipeline_next_retry_at` rather than Celery's own retry,
  since the correct backoff here is "wait until the quota window resets," not a fixed
  exponential curve.
- **Permanent errors** (video deleted/private, unsupported language, malformed response
  from LLM after retries): task marks `pipeline_status = FAILED` with a specific
  `pipeline_failure_reason` and does not retry further; surfaced via
  `/admin/pipeline/failures` for manual triage.
- **Every attempt is logged** to `task_logs` (task name, video/channel id, status,
  error message, duration) regardless of outcome — this is the data source for both the
  admin dashboard and for noticing systemic issues (e.g., one provider's error rate
  spiking).

## 5. Idempotency & Locking

- A Redis lock (`SET NX PX`) keyed `pipeline-lock:{video_id}` wraps each pipeline stage
  transition. If a duplicate task fires (e.g., a Celery retry racing a manual
  `/admin/pipeline/retry`), the second acquire fails fast and no-ops instead of doing
  duplicate work or duplicate LLM spend.
- Every write step is an upsert keyed on the natural unique constraint (`channel_id +
  external_video_id` for videos, `video_id` for transcripts/summaries/thesis/sentiment),
  so re-running any stage is safe and doesn't create duplicate rows.
- `chunk_and_embed` deletes and regenerates a video's segments/embeddings atomically in
  one transaction rather than appending, so re-embedding after a transcript correction
  never leaves stale vectors searchable.

## 6. Worker Deployment

Separate Celery worker processes per queue group (not one worker consuming everything),
so resource-heavy transcription workers (GPU/CPU, `ffmpeg`, Whisper weights) can be
scaled and deployed independently from lightweight I/O-bound discovery/analysis
workers:

```
celery -A app.core.celery_app worker -Q discovery,maintenance --concurrency=8
celery -A app.core.celery_app worker -Q transcription --concurrency=2 --pool=solo   # GPU-bound
celery -A app.core.celery_app worker -Q analysis,embedding --concurrency=16
celery -A app.core.celery_app worker -Q reports --concurrency=2
celery -A app.core.celery_app beat -A app.core.celery_app
```

In `docker-compose.yml` each becomes its own service, and in production each maps to
its own deployment/replica count so transcription (the most expensive, slowest stage)
can be scaled to match video volume without over-provisioning the cheap analysis
workers, or vice versa.
