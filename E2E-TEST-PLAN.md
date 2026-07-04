# End-to-End Testing Plan
## Mw-StockMarket-Analytics Backend

This document provides step-by-step instructions to test the entire system with real data.

---

## Prerequisites

### 1. API Keys Required
```bash
# In backend/.env file:
YOUTUBE_API_KEY=AIza...          # Get from Google Cloud Console
OPENAI_API_KEY=sk-...            # Get from OpenAI Platform
```

### 2. Configure Test Channel
Add a financial YouTube channel to analyze. Examples:
- CNBC Television: `UCrp_UI8XtuYfpiqluWLD7Lw`
- Bloomberg Television: `UCIALMKvObZNtJ6AmdCLP7Lg`
- Yahoo Finance: `UCEAZeUIeJs3KZJF33n8gHZw`

```bash
# In backend/.env:
YOUTUBE_CHANNEL_IDS=UCrp_UI8XtuYfpiqluWLD7Lw
VIDEO_LOOKBACK_DAYS=7  # Start with just 1 week
```

### 3. Start the System
```bash
cd infra
docker-compose up -d

# Wait 30 seconds for startup
timeout 30

# Verify health
curl http://localhost:8000/health
```

---

## Test Sequence

### Phase 1: Channel Discovery (30 seconds)

**Objective:** Verify the system can discover channels from YouTube

```bash
# Trigger channel discovery
curl -X POST http://localhost:8000/api/v1/scheduler/jobs/discover_channels/run \
  -H "X-Admin-Key: changeme-admin-key"

# Expected response:
# {"message":"Job discover_channels triggered successfully"}

# Wait 10 seconds for task to complete
timeout 10

# Verify channels were created
curl http://localhost:8000/api/v1/channels

# Expected: JSON array with 1 channel object containing:
# - channel_id (YouTube ID)
# - title
# - description
# - subscriber_count
# - video_count
```

**Success Criteria:**
- ✅ 1 channel returned
- ✅ `subscriber_count > 0`
- ✅ `video_count > 0`

---

### Phase 2: Video Discovery (1-2 minutes)

**Objective:** Discover recent videos from the channel

```bash
# Trigger video discovery
curl -X POST http://localhost:8000/api/v1/scheduler/jobs/discover_videos/run \
  -H "X-Admin-Key: changeme-admin-key"

# Wait 60 seconds (depends on channel size)
timeout 60

# Check discovered videos
curl "http://localhost:8000/api/v1/videos?limit=10&sort_by=published_at&sort_order=desc"

# Expected: Array of 5-20 videos with:
# - title
# - published_at
# - duration_seconds
# - view_count
# - pipeline_status = "INDEXED"
```

**Success Criteria:**
- ✅ At least 5 videos discovered
- ✅ All have `pipeline_status = "INDEXED"`
- ✅ All have `view_count > 0`

**Monitor logs:**
```bash
docker logs mw_worker --tail=50
# Look for: "Discovered X videos for channel..."
```

---

### Phase 3: Transcription (2-5 minutes per video)

**Objective:** Transcribe one video using OpenAI Whisper

```bash
# Get the first video ID
$videoId = (Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/videos?limit=1" | ConvertFrom-Json).items[0].id

# Trigger transcription pipeline for this video
Invoke-WebRequest -UseBasicParsing -Method POST `
  "http://localhost:8000/api/v1/admin/pipeline/retry/$videoId" `
  -Headers @{"X-Admin-Key"="changeme-admin-key"}

# Monitor progress (check every 30 seconds)
while ($true) {
  $status = (Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/videos/$videoId" | ConvertFrom-Json).pipeline_status
  Write-Host "Status: $status"
  if ($status -eq "TRANSCRIBED" -or $status -eq "ANALYZED" -or $status -eq "EMBEDDED") { break }
  Start-Sleep -Seconds 30
}

# Retrieve transcript
curl "http://localhost:8000/api/v1/videos/$videoId/transcript"

# Expected: JSON object with:
# - text (full transcript)
# - language
# - segments (array with timestamps)
# - word_count
```

**Success Criteria:**
- ✅ `pipeline_status` changes to `"TRANSCRIBED"` or beyond
- ✅ Transcript has `word_count > 100`
- ✅ Segments have timestamps and text

**Monitor logs:**
```bash
docker logs mw_worker -f
# Look for:
# - "Downloading audio for video..."
# - "Transcribing audio..."
# - "Transcript generated: X words"
```

**Estimated time:** 2-5 minutes depending on video length

---

### Phase 4: AI Analysis (1-2 minutes)

**Objective:** Extract investment insights using GPT-4

After transcription completes, analysis runs automatically. Wait for it:

```bash
# Check if analysis completed
$videoId = 1  # Use your video ID
curl "http://localhost:8000/api/v1/videos/$videoId"
# Look for: "pipeline_status": "ANALYZED"

# Retrieve analysis results
curl "http://localhost:8000/api/v1/videos/$videoId/summary"
curl "http://localhost:8000/api/v1/videos/$videoId/sentiment"
curl "http://localhost:8000/api/v1/videos/$videoId/companies"
curl "http://localhost:8000/api/v1/videos/$videoId/key-numbers"
curl "http://localhost:8000/api/v1/videos/$videoId/insights"
curl "http://localhost:8000/api/v1/videos/$videoId/quotes"
```

**Expected Results:**

**Summary:**
```json
{
  "video_id": 1,
  "executive_summary": "Discussion about...",
  "investment_thesis": "The key investment opportunity...",
  "key_takeaways": ["Point 1", "Point 2", ...]
}
```

**Sentiment:**
```json
{
  "video_id": 1,
  "overall_sentiment": "BULLISH",
  "confidence_score": 0.85,
  "reasoning": "Strong positive indicators..."
}
```

**Companies:**
```json
[
  {
    "ticker": "NVDA",
    "company_name": "NVIDIA Corporation",
    "sector": "Technology",
    "industry": "Semiconductors"
  }
]
```

**Key Numbers:**
```json
[
  {
    "metric_type": "PRICE_TARGET",
    "value": 450.0,
    "context": "Analyst sets price target of $450"
  }
]
```

**Success Criteria:**
- ✅ `pipeline_status = "ANALYZED"`
- ✅ Summary has meaningful text (>50 words)
- ✅ At least 1 company extracted
- ✅ Sentiment is BULLISH, BEARISH, or NEUTRAL
- ✅ At least 1 key number extracted

---

### Phase 5: Embedding Generation (30 seconds)

**Objective:** Generate vector embeddings for semantic search

```bash
# Check if embeddings generated
$videoId = 1
$video = Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/videos/$videoId" | ConvertFrom-Json

# Look for: "pipeline_status": "EMBEDDED"
Write-Host "Status: $($video.pipeline_status)"

# Check embedding count (should be transcript_length/500 tokens)
curl "http://localhost:8000/api/v1/admin/pipeline/status"
# Look for embedding_count in response
```

**Success Criteria:**
- ✅ `pipeline_status = "EMBEDDED"`
- ✅ Embedding count > 0 in pipeline status

---

### Phase 6: Semantic Search (instant)

**Objective:** Test RAG-based search over video content

```bash
# Search for investment-related content
curl "http://localhost:8000/api/v1/search?q=nvidia+earnings+forecast&limit=5"

# Expected: Array of results with:
# - video metadata (title, published_at)
# - matched_text (relevant chunk)
# - relevance_score (0.0-1.0)
# - timestamp (when in video)
```

**Success Criteria:**
- ✅ Returns relevant results
- ✅ `relevance_score > 0.5` for top result
- ✅ `matched_text` contains query keywords

---

### Phase 7: RAG Chat (2-5 seconds per query)

**Objective:** Ask natural language questions about the content

```bash
# Ask a question
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the key investment opportunities mentioned?",
    "conversation_id": null
  }'

# Expected response:
{
  "conversation_id": "uuid-here",
  "message_id": "uuid-here",
  "response": "Based on the analyzed videos, key opportunities include...",
  "sources": [
    {
      "video_id": 1,
      "video_title": "...",
      "timestamp": 120,
      "relevance_score": 0.87
    }
  ]
}
```

**Success Criteria:**
- ✅ Response is coherent and relevant
- ✅ Sources are provided with video context
- ✅ Conversation ID is returned for follow-ups

**Follow-up question:**
```bash
# Use the conversation_id from previous response
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the risks?",
    "conversation_id": "uuid-from-previous-response"
  }'
```

---

### Phase 8: Analytics (instant)

**Objective:** Verify aggregated analytics work

```bash
# Trending stocks (7-day window)
curl "http://localhost:8000/api/v1/analytics/trending-stocks?window=7d&limit=10"

# Expected:
[
  {
    "ticker": "NVDA",
    "company_name": "NVIDIA Corporation",
    "mention_count": 5,
    "avg_sentiment": 0.75,
    "sector": "Technology"
  }
]

# Trending sectors
curl "http://localhost:8000/api/v1/analytics/trending-sectors"

# Expected:
[
  {
    "sector": "Technology",
    "mention_count": 15,
    "avg_sentiment": 0.68,
    "video_count": 8
  }
]

# Sector heatmap
curl "http://localhost:8000/api/v1/analytics/sector-heatmap"

# Expected: 2D array of sentiment by sector and time
```

**Success Criteria:**
- ✅ Trending stocks show companies from analyzed videos
- ✅ Sentiment scores are between -1.0 and 1.0
- ✅ Mention counts are accurate

---

### Phase 9: Admin Monitoring

**Objective:** Verify operational dashboards work

```bash
# Pipeline status overview
curl -H "X-Admin-Key: changeme-admin-key" \
  "http://localhost:8000/api/v1/admin/pipeline/status"

# Expected:
{
  "total_videos": 10,
  "indexed": 10,
  "transcribed": 1,
  "analyzed": 1,
  "embedded": 1,
  "failed": 0,
  "pending": 9
}

# Check for failures
curl -H "X-Admin-Key: changeme-admin-key" \
  "http://localhost:8000/api/v1/admin/pipeline/failures"

# Expected: Empty array [] if all succeeded

# Quota tracking
curl -H "X-Admin-Key: changeme-admin-key" \
  "http://localhost:8000/api/v1/admin/quota"

# Expected:
{
  "youtube": {
    "daily_limit": 10000,
    "used_today": 150,
    "remaining": 9850,
    "reset_time": "2026-07-04T00:00:00Z"
  }
}

# Task logs
curl -H "X-Admin-Key: changeme-admin-key" \
  "http://localhost:8000/api/v1/admin/task-logs?limit=20"

# Expected: Array of task execution logs
```

---

## Full Pipeline Test Script

Run everything in sequence:

```powershell
# PowerShell script for complete E2E test
$base = "http://localhost:8000"
$adminKey = "changeme-admin-key"

Write-Host "=== Phase 1: Channel Discovery ===" -ForegroundColor Cyan
Invoke-WebRequest -UseBasicParsing -Method POST "$base/api/v1/scheduler/jobs/discover_channels/run" `
  -Headers @{"X-Admin-Key"=$adminKey}
Start-Sleep -Seconds 15

$channels = (Invoke-WebRequest -UseBasicParsing "$base/api/v1/channels" | ConvertFrom-Json)
Write-Host "Channels discovered: $($channels.Length)" -ForegroundColor Green

Write-Host "`n=== Phase 2: Video Discovery ===" -ForegroundColor Cyan
Invoke-WebRequest -UseBasicParsing -Method POST "$base/api/v1/scheduler/jobs/discover_videos/run" `
  -Headers @{"X-Admin-Key"=$adminKey}
Start-Sleep -Seconds 60

$videos = (Invoke-WebRequest -UseBasicParsing "$base/api/v1/videos?limit=100" | ConvertFrom-Json).items
Write-Host "Videos discovered: $($videos.Length)" -ForegroundColor Green

Write-Host "`n=== Phase 3: Process First Video ===" -ForegroundColor Cyan
$videoId = $videos[0].id
Write-Host "Processing video ID: $videoId - $($videos[0].title)"

Invoke-WebRequest -UseBasicParsing -Method POST "$base/api/v1/admin/pipeline/retry/$videoId" `
  -Headers @{"X-Admin-Key"=$adminKey}

Write-Host "Waiting for pipeline to complete (this may take 5-10 minutes)..." -ForegroundColor Yellow

while ($true) {
  $video = Invoke-WebRequest -UseBasicParsing "$base/api/v1/videos/$videoId" | ConvertFrom-Json
  $status = $video.pipeline_status
  Write-Host "  Status: $status" -NoNewline
  
  if ($status -eq "EMBEDDED") {
    Write-Host " ✓ COMPLETE" -ForegroundColor Green
    break
  } elseif ($status -eq "FAILED") {
    Write-Host " ✗ FAILED" -ForegroundColor Red
    break
  }
  
  Write-Host ""
  Start-Sleep -Seconds 30
}

Write-Host "`n=== Phase 4: Verify Analysis Results ===" -ForegroundColor Cyan
try {
  $summary = Invoke-WebRequest -UseBasicParsing "$base/api/v1/videos/$videoId/summary" | ConvertFrom-Json
  Write-Host "✓ Summary generated: $($summary.executive_summary.Substring(0, 100))..." -ForegroundColor Green
} catch {
  Write-Host "✗ Summary failed" -ForegroundColor Red
}

try {
  $companies = Invoke-WebRequest -UseBasicParsing "$base/api/v1/videos/$videoId/companies" | ConvertFrom-Json
  Write-Host "✓ Companies extracted: $($companies.Length)" -ForegroundColor Green
} catch {
  Write-Host "✗ Companies failed" -ForegroundColor Red
}

Write-Host "`n=== Phase 5: Test Search ===" -ForegroundColor Cyan
$searchResults = Invoke-WebRequest -UseBasicParsing "$base/api/v1/search?q=stock+market" | ConvertFrom-Json
Write-Host "✓ Search returned: $($searchResults.Length) results" -ForegroundColor Green

Write-Host "`n=== Phase 6: Test Analytics ===" -ForegroundColor Cyan
$trending = Invoke-WebRequest -UseBasicParsing "$base/api/v1/analytics/trending-stocks?window=7d" | ConvertFrom-Json
Write-Host "✓ Trending stocks: $($trending.Length)" -ForegroundColor Green
$trending | Select-Object -First 3 | Format-Table ticker, mention_count, avg_sentiment

Write-Host "`n=== Pipeline Status ===" -ForegroundColor Cyan
$pipelineStatus = Invoke-WebRequest -UseBasicParsing "$base/api/v1/admin/pipeline/status" `
  -Headers @{"X-Admin-Key"=$adminKey} | ConvertFrom-Json
$pipelineStatus | Format-List

Write-Host "`n✅ E2E TEST COMPLETE" -ForegroundColor Green
```

---

## Cost Estimation

For processing **1 video (10 minutes long)**:

| Service | Operation | Cost |
|---------|-----------|------|
| YouTube API | Video discovery | $0.00 (free quota) |
| OpenAI Whisper | Transcription (10min) | ~$0.60 |
| OpenAI GPT-4 | Analysis (7 extractions) | ~$0.30 |
| OpenAI Embeddings | Vectors (2000 tokens) | ~$0.00 |
| **Total per video** | | **~$0.90** |

For **100 videos/month**: ~$90/month

---

## Troubleshooting

### Videos stuck in INDEXED status
```bash
# Check worker logs for errors
docker logs mw_worker -f

# Common issues:
# - Invalid YouTube API key
# - Video has no audio track
# - Video is age-restricted or private
```

### Transcription fails
```bash
# Check OpenAI API key is valid
docker exec mw_api python -c "import os; print(os.getenv('OPENAI_API_KEY'))"

# Check audio download works
docker logs mw_worker | grep "Downloading audio"

# Manual test:
docker exec mw_worker celery -A app.core.celery_app call app.workers.tasks.transcript_tasks.transcribe_video --args='[1]'
```

### Analysis produces empty results
```bash
# Check GPT-4 responses
docker logs mw_worker | grep "GPT"

# Verify transcript exists
curl http://localhost:8000/api/v1/videos/1/transcript

# Check prompt templates are loaded
docker exec mw_api ls -la /app/app/prompts/
```

### Search returns no results
```bash
# Verify embeddings were generated
docker logs mw_worker | grep "embedding"

# Check pgvector extension loaded
docker exec mw_postgres psql -U stock_user -d stock_db -c "SELECT * FROM pg_extension WHERE extname='vector';"

# Count embeddings
docker exec mw_postgres psql -U stock_user -d stock_db -c "SELECT COUNT(*) FROM embeddings;"
```

---

## Success Checklist

After running all tests, verify:

- [ ] Channels discovered from YouTube
- [ ] Videos discovered and indexed
- [ ] At least 1 video fully transcribed
- [ ] Analysis extracted companies, sentiment, insights
- [ ] Embeddings generated
- [ ] Semantic search returns relevant results
- [ ] RAG chat provides coherent answers
- [ ] Analytics show trending stocks/sectors
- [ ] Admin dashboard shows pipeline status
- [ ] No critical errors in logs

**System is ready for production use when all boxes are checked!**

---

## Next: Add More Channels

Once 1 video works, scale up:

```bash
# Add more financial channels in .env:
YOUTUBE_CHANNEL_IDS=UCrp_UI8XtuYfpiqluWLD7Lw,UCIALMKvObZNtJ6AmdCLP7Lg,UCEAZeUIeJs3KZJF33n8gHZw

# Increase lookback window:
VIDEO_LOOKBACK_DAYS=30  # Process last month

# Restart to apply changes:
docker-compose restart mw_api mw_worker

# Trigger full discovery:
curl -X POST http://localhost:8000/api/v1/scheduler/jobs/discover_channels/run \
  -H "X-Admin-Key: changeme-admin-key"

curl -X POST http://localhost:8000/api/v1/scheduler/jobs/discover_videos/run \
  -H "X-Admin-Key: changeme-admin-key"
```

The system will process all videos in the background. Monitor progress via `/api/v1/admin/pipeline/status`.
