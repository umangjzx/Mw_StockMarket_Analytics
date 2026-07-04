# API Design

Base path: `/api/v1`. JSON request/response bodies. Auth via `Authorization: Bearer
<JWT>` for user-scoped endpoints and a separate `X-Admin-Key` (or admin-role JWT) for
`/admin` and `/scheduler`. List endpoints share one pagination convention:
`?page=1&page_size=20` → `{ "items": [...], "page": 1, "page_size": 20, "total": N }`.
Filterable list endpoints share `?sort=-published_at` style ordering (`-` prefix =
descending).

## 1. Videos — `/api/v1/videos`

| Method | Path | Purpose |
|---|---|---|
| GET | `/videos` | List videos. Filters: `channel_id`, `ticker`, `company`, `topic`, `sentiment`, `content_type`, `date_from`, `date_to`, `pipeline_status`. |
| GET | `/videos/{id}` | Full video detail: metadata + latest stats. |
| GET | `/videos/{id}/transcript` | Full transcript text + segments (paginated by segment). |
| GET | `/videos/{id}/summary` | Executive bullets + detailed summary. |
| GET | `/videos/{id}/thesis` | Investment thesis (bull/bear/risks/catalysts/valuation/outlook). |
| GET | `/videos/{id}/sentiment` | Overall sentiment + per-ticker sentiment breakdown. |
| GET | `/videos/{id}/quotes` | Top 10 important quotes with timestamps. |
| GET | `/videos/{id}/key-numbers` | Extracted financial figures. |
| GET | `/videos/{id}/insights` | Actionable insights (buy/sell/watchlist/risks/catalysts). |
| GET | `/videos/{id}/companies` | Companies/tickers mentioned, with mention counts. |
| POST | `/videos/{id}/reprocess` | Admin: re-enqueue the pipeline from a given stage (`?from_stage=ANALYSIS_PENDING`). |

## 2. Channels — `/api/v1/channels`

| Method | Path | Purpose |
|---|---|---|
| GET | `/channels` | List configured channels + polling status. |
| POST | `/channels` | Add a channel (admin). Body: `{platform, external_channel_id or handle, polling_interval_seconds?, include_shorts?}`. |
| GET | `/channels/{id}` | Channel detail + recent poll history. |
| PATCH | `/channels/{id}` | Update config (active flag, polling interval, include_shorts). |
| DELETE | `/channels/{id}` | Deactivate (soft, via `is_active=false`) — videos are retained. |
| POST | `/channels/{id}/poll-now` | Admin: trigger an immediate out-of-band poll. |
| GET | `/channels/{id}/videos` | Videos from this channel (paginated). |

## 3. Summaries — `/api/v1/summaries`

Cross-video summary queries that don't belong under a single `/videos/{id}`:

| Method | Path | Purpose |
|---|---|---|
| GET | `/summaries` | List/filter summaries across videos (`ticker`, `channel_id`, `date_from/to`). |
| GET | `/summaries/{video_id}` | Same payload as `/videos/{id}/summary` — kept for a flat resource-oriented client. |

## 4. Search — `/api/v1/search`

| Method | Path | Purpose |
|---|---|---|
| GET | `/search` | Structured filter search. Params: `q` (keyword, full-text), `ticker`, `company`, `creator` (channel), `topic`, `date_from`, `date_to`, `sector`, `industry`. Returns matching videos ranked by relevance. |
| POST | `/search/semantic` | Natural-language query. Body: `{"query": "What did analysts say about Nvidia?", "top_k": 10, "filters": {...}}`. Embeds the query, runs pgvector similarity over `embeddings`, returns transcript segments with `{video, timestamp, similarity_score}`. |

## 5. Chat (RAG) — `/api/v1/chat`

| Method | Path | Purpose |
|---|---|---|
| POST | `/chat/sessions` | Create a chat session (optionally scoped to `ticker`/`watchlist` context). |
| POST | `/chat/sessions/{id}/messages` | Send a question. Server retrieves top-k relevant transcript chunks, builds a grounded prompt, streams back an answer. Response includes `citations: [{video_id, video_title, creator, published_date, start_seconds}]` for every claim. |
| GET | `/chat/sessions/{id}` | Fetch conversation history. |
| GET | `/chat/sessions/{id}/messages` | Paginated message history. |

Streaming is via Server-Sent Events on the messages endpoint (`Accept:
text/event-stream`) so the frontend can render tokens incrementally; a non-streaming
JSON response is returned otherwise.

## 6. Reports — `/api/v1/reports`

| Method | Path | Purpose |
|---|---|---|
| GET | `/reports/daily` | Latest daily report. |
| GET | `/reports/daily/{date}` | Report for a specific date (`YYYY-MM-DD`). |
| GET | `/reports/daily?date_from&date_to` | Range of reports (for trend views). |
| POST | `/reports/daily/generate` | Admin: force-regenerate today's report on demand. |

## 7. Analytics — `/api/v1/analytics`

| Method | Path | Purpose |
|---|---|---|
| GET | `/analytics/trending-stocks` | Most-mentioned tickers over a rolling window (`?window=24h\|7d\|30d`). |
| GET | `/analytics/trending-sectors` | Sector-level mention/sentiment aggregation. |
| GET | `/analytics/sentiment/{ticker}` | Sentiment time series for one ticker (for charting). |
| GET | `/analytics/sector-heatmap` | Sector x sentiment matrix for the heatmap widget. |
| GET | `/analytics/creator/{channel_id}` | Per-creator stats: video volume, avg sentiment, top tickers covered. |

## 8. Watchlist — `/api/v1/watchlist`

| Method | Path | Purpose |
|---|---|---|
| GET | `/watchlists` | Current user's watchlists. |
| POST | `/watchlists` | Create a watchlist. |
| GET | `/watchlists/{id}` | Watchlist detail with tickers + latest mentions/sentiment per ticker. |
| POST | `/watchlists/{id}/items` | Add a ticker. |
| DELETE | `/watchlists/{id}/items/{ticker_id}` | Remove a ticker. |
| GET | `/watchlists/{id}/feed` | Videos/insights relevant to any ticker on this watchlist, most recent first. |

Bookmarks live alongside watchlist since both are user-curated collections:

| Method | Path | Purpose |
|---|---|---|
| GET | `/bookmarks` | Current user's bookmarked videos. |
| POST | `/bookmarks` | Bookmark a video (`{video_id, note?}`). |
| DELETE | `/bookmarks/{video_id}` | Remove bookmark. |

## 9. Admin — `/api/v1/admin`

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/pipeline/status` | Counts of videos by `pipeline_status`, failure breakdown. |
| GET | `/admin/pipeline/failures` | List failed videos with `failure_reason`, `retry_count`. |
| POST | `/admin/pipeline/retry/{video_id}` | Manually re-enqueue a failed video. |
| GET | `/admin/quota` | Current YouTube API + OpenAI usage/cost against budget. |
| GET | `/admin/task-logs` | Query `task_logs` (filters: `task_name`, `status`, `date_from/to`). |
| GET | `/admin/users` | User management (list/roles). |

## 10. Scheduler — `/api/v1/scheduler`

| Method | Path | Purpose |
|---|---|---|
| GET | `/scheduler/jobs` | List Celery Beat periodic jobs + next run time. |
| POST | `/scheduler/jobs/{name}/trigger` | Fire a scheduled job immediately (e.g., force a channel-poll cycle or daily report). |
| PATCH | `/scheduler/jobs/{name}` | Update a job's cadence (writes through to the DB-backed beat schedule). |

## Design Notes

**Why `/search` and `/search/semantic` are separate endpoints instead of one endpoint
that "figures it out."** Structured filter search (ticker/date/creator) is a fast,
predictable SQL query; semantic search is an embedding call plus a vector query with
materially different latency and cost. Keeping them separate lets the frontend choose
the right one (e.g., dropdown filters hit `/search`, the natural-language search bar hits
`/search/semantic`) and lets each be cached/rate-limited differently. Both endpoints
return the same result shape.

**Why chat citations are structured fields, not inline markdown links.** Requiring
`citations` as a typed array (not just text asking the model to "cite your sources") lets
the frontend render clickable, timestamp-seeking video links deterministically and lets
the backend validate that every citation actually maps to a retrieved chunk — an LLM
that invents a citation should be programmatically catchable in review, since the
citation IDs are cross-checked against the retrieval set before the response is
returned.

**Why `/admin` and `/scheduler` are separate from the rest of the surface.** They expose
operational internals (retry controls, quota, task logs) that a normal API consumer
(frontend dashboard, or a future third-party integration) has no business calling, so
they get a stricter auth requirement and are easy to disable entirely in a
public-facing deployment.

**Versioning.** Everything sits under `/api/v1` from day one so a `v2` can be introduced
later (e.g., if the RAG chat response shape needs a breaking change) without disrupting
existing clients.
