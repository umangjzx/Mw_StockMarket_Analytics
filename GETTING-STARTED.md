# Getting Started — MW StockMarket Analytics

## Current Status ✅

- ✅ `.env` file created from `.env.example`
- ✅ `docker-compose.yml` fixed (removed obsolete version attribute)
- 🔄 Docker images building (first build takes 5-10 minutes)

## Next Steps

### 1. Wait for Docker Build to Complete

The Docker build is currently running in the background. This first build downloads:
- Postgres 16 + pgvector image (~155MB)
- Python 3.11 slim base image (~30MB)
- All Python dependencies (FastAPI, Celery, SQLAlchemy, OpenAI, etc.)
- System packages (libpq-dev, ffmpeg for workers, curl)

**Check build progress:**
```powershell
cd c:\Users\UMANG JAISWAL N\Claude\Projects\Mw-StockMarket-Analytics\infra
docker compose ps
```

**If build stopped, restart it:**
```powershell
docker compose up -d --build
```

### 2. Verify Services Are Running

Once build completes:
```powershell
docker compose ps
```

You should see:
- ✅ `mw_postgres` — running, healthy
- ✅ `mw_redis` — running, healthy
- ✅ `mw_api` — running, healthy
- ✅ `mw_worker_discovery` — running
- ✅ `mw_worker_transcription` — running
- ✅ `mw_worker_analysis` — running
- ✅ `mw_worker_reports` — running
- ✅ `mw_beat` — running

### 3. Run Database Migrations

```powershell
docker compose exec api alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, Initial schema -- all tables + pgvector/pg_trgm extensions
```

### 4. Test the Health Endpoint

```powershell
curl http://localhost:8000/health
```

Expected response:
```json
{"status":"healthy","environment":"development"}
```

Or in browser: http://localhost:8000/health

### 5. Access API Documentation

Once the API is running:
- **Swagger UI:** http://localhost:8000/api/docs
- **ReDoc:** http://localhost:8000/api/redoc
- **OpenAPI JSON:** http://localhost:8000/api/openapi.json

### 6. Check Logs

**All services:**
```powershell
docker compose logs -f
```

**Specific service:**
```powershell
docker compose logs -f api
docker compose logs -f worker-discovery
docker compose logs -f postgres
```

**Last 50 lines:**
```powershell
docker compose logs --tail=50 api
```

### 7. Verify Database Tables

```powershell
docker compose exec postgres psql -U mw_user -d mw_stockmarket -c "\dt"
```

Should list 20+ tables including:
- `channels`, `videos`, `video_stat_snapshots`
- `transcripts`, `transcript_segments`
- `companies`, `tickers`, `topics`
- `summaries`, `investment_theses`, `sentiments`
- `quotes`, `key_numbers`, `actionable_insights`
- `embeddings` (with pgvector)
- `daily_reports`, `report_video_links`
- `users`, `bookmarks`, `watchlists`, `watchlist_items`
- `task_logs`

**Check pgvector extension:**
```powershell
docker compose exec postgres psql -U mw_user -d mw_stockmarket -c "\dx"
```

Should show:
- `vector` (pgvector for embeddings)
- `pg_trgm` (for full-text search)

## Troubleshooting

### Build is stuck or failing

**Stop and rebuild:**
```powershell
docker compose down
docker compose build --no-cache
docker compose up -d
```

### "Port already in use" error

Check what's using the ports:
```powershell
# Check port 5432 (Postgres)
netstat -ano | findstr :5432

# Check port 6379 (Redis)
netstat -ano | findstr :6379

# Check port 8000 (API)
netstat -ano | findstr :8000
```

Stop the conflicting process or change ports in `docker-compose.yml`.

### Migrations fail

**Check Postgres is ready:**
```powershell
docker compose exec postgres pg_isready -U mw_user -d mw_stockmarket
```

**Check Alembic config:**
```powershell
docker compose exec api alembic current
```

**View migration history:**
```powershell
docker compose exec api alembic history --verbose
```

### API returns 500 error

**Check API logs:**
```powershell
docker compose logs api --tail=100
```

**Check environment variables:**
```powershell
docker compose exec api env | grep -E '(DATABASE_URL|REDIS_URL|SECRET_KEY)'
```

### Worker not processing tasks

**Check worker logs:**
```powershell
docker compose logs worker-discovery --tail=50
```

**Check Redis connection:**
```powershell
docker compose exec redis redis-cli ping
```

**Expected:** `PONG`

## Stopping the Stack

**Stop all services:**
```powershell
docker compose stop
```

**Stop and remove containers (keeps volumes):**
```powershell
docker compose down
```

**Stop, remove containers AND volumes (fresh start):**
```powershell
docker compose down -v
```

## Configuration

Before running in production, update `.env`:

```env
# Required: Set these before first run
SECRET_KEY=<generate-with-openssl-rand-hex-32>
YOUTUBE_API_KEY=<your-youtube-api-key>
OPENAI_API_KEY=<your-openai-api-key>

# Optional: Adjust limits
YOUTUBE_DAILY_QUOTA_LIMIT=10000
OPENAI_DAILY_SPEND_LIMIT=10.00
MAX_PIPELINE_RETRIES=5

# Optional: Observability
SENTRY_DSN=<your-sentry-dsn>
LOG_LEVEL=INFO
```

## What's Next

Phase 0 is complete. Ready to implement:

**Phase 1a — Channel & Video Discovery:**
- YouTube Data API integration
- Channel polling implementation
- Video metadata sync
- REST endpoints: `/api/v1/channels`, `/api/v1/videos`

See `docs/06-roadmap.md` for the full development plan.

## Need Help?

1. Check `README.md` for project overview
2. Review `docs/01-architecture.md` for system design
3. Check GitHub Issues
4. Review logs: `docker compose logs -f`
