# Quick Start Guide
## Get Your System Running in 15 Minutes

---

## Step 1: Get API Keys (5 minutes)

### YouTube Data API v3
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable "YouTube Data API v3"
4. Create credentials → API Key
5. Copy the key (looks like: `AIzaSyA...`)

**Cost:** FREE (10,000 quota units/day)

### OpenAI API Key
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create new API key
3. Copy the key (looks like: `sk-proj-...`)

**Cost:** Pay-as-you-go (~$0.90 per 10-minute video)

---

## Step 2: Configure Environment (2 minutes)

Edit `backend/.env`:

```bash
# Replace these two lines:
YOUTUBE_API_KEY=AIzaSyA...your-actual-key...
OPENAI_API_KEY=sk-proj-...your-actual-key...
```

**Optional:** Add financial YouTube channels to analyze:

```bash
# Add after YOUTUBE_API_KEY:
YOUTUBE_CHANNEL_IDS=UCrp_UI8XtuYfpiqluWLD7Lw,UCIALMKvObZNtJ6AmdCLP7Lg
VIDEO_LOOKBACK_DAYS=7
```

Suggested channels:
- `UCrp_UI8XtuYfpiqluWLD7Lw` - CNBC Television
- `UCIALMKvObZNtJ6AmdCLP7Lg` - Bloomberg Television  
- `UCEAZeUIeJs3KZJF33n8gHZw` - Yahoo Finance

---

## Step 3: Start the System (3 minutes)

```powershell
# Navigate to project
cd "c:\Users\UMANG JAISWAL N\Claude\Projects\Mw-StockMarket-Analytics\infra"

# Start all containers
docker-compose up -d

# Wait for startup (30 seconds)
Start-Sleep -Seconds 30

# Verify health
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health

# View API documentation
Start-Process http://localhost:8000/docs
```

Expected output:
```json
{"status":"healthy","version":"1.0.0"}
```

---

## Step 4: Run Your First Analysis (5-10 minutes)

### Discover Channels
```powershell
Invoke-WebRequest -UseBasicParsing -Method POST `
  "http://localhost:8000/api/v1/scheduler/jobs/discover_channels/run" `
  -Headers @{"X-Admin-Key"="changeme-admin-key"}

# Wait 10 seconds
Start-Sleep -Seconds 10

# Verify channels created
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/channels" | ConvertFrom-Json
```

### Discover Videos
```powershell
Invoke-WebRequest -UseBasicParsing -Method POST `
  "http://localhost:8000/api/v1/scheduler/jobs/discover_videos/run" `
  -Headers @{"X-Admin-Key"="changeme-admin-key"}

# Wait 60 seconds
Start-Sleep -Seconds 60

# Check videos
$videos = (Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/videos?limit=10" | ConvertFrom-Json).items
Write-Host "Found $($videos.Length) videos"
$videos | Format-Table id, title, duration_seconds, pipeline_status
```

### Process First Video
```powershell
# Get first video ID
$videoId = $videos[0].id
Write-Host "Processing video: $($videos[0].title)"

# Trigger full pipeline
Invoke-WebRequest -UseBasicParsing -Method POST `
  "http://localhost:8000/api/v1/admin/pipeline/retry/$videoId" `
  -Headers @{"X-Admin-Key"="changeme-admin-key"}

# Monitor progress (updates every 30 seconds)
while ($true) {
  $video = Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/videos/$videoId" | ConvertFrom-Json
  $status = $video.pipeline_status
  Write-Host "$(Get-Date -Format 'HH:mm:ss') - Status: $status"
  
  if ($status -eq "EMBEDDED") {
    Write-Host "✓ COMPLETE!" -ForegroundColor Green
    break
  } elseif ($status -eq "FAILED") {
    Write-Host "✗ FAILED - Check logs" -ForegroundColor Red
    break
  }
  
  Start-Sleep -Seconds 30
}
```

**Expected timeline:**
- 0-2 min: Transcribing (INDEXED → TRANSCRIBED)
- 2-4 min: Analyzing (TRANSCRIBED → ANALYZED)  
- 4-5 min: Embedding (ANALYZED → EMBEDDED)

### View Results
```powershell
# Summary
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/videos/$videoId/summary" | ConvertFrom-Json | Format-List

# Companies mentioned
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/videos/$videoId/companies" | ConvertFrom-Json | Format-Table

# Sentiment
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/videos/$videoId/sentiment" | ConvertFrom-Json | Format-List

# Key numbers (prices, targets, metrics)
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/videos/$videoId/key-numbers" | ConvertFrom-Json | Format-Table

# Actionable insights
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/videos/$videoId/insights" | ConvertFrom-Json | Format-Table
```

---

## Step 5: Try Search & Chat

### Semantic Search
```powershell
# Search for investment topics
$results = Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/v1/search?q=nvidia+stock+forecast" | ConvertFrom-Json
$results | Select-Object -First 3 | Format-List video_title, matched_text, relevance_score
```

### Ask Questions (RAG Chat)
```powershell
$body = @{
  message = "What are the key investment opportunities mentioned in recent videos?"
  conversation_id = $null
} | ConvertTo-Json

$response = Invoke-WebRequest -UseBasicParsing -Method POST `
  "http://localhost:8000/api/v1/chat" `
  -ContentType "application/json" `
  -Body $body | ConvertFrom-Json

Write-Host $response.response
Write-Host "`nSources:"
$response.sources | Format-Table video_title, timestamp, relevance_score
```

---

## Step 6: View Analytics

```powershell
# Trending stocks (7-day window)
$trending = Invoke-WebRequest -UseBasicParsing `
  "http://localhost:8000/api/v1/analytics/trending-stocks?window=7d&limit=10" | ConvertFrom-Json
$trending | Format-Table ticker, company_name, mention_count, avg_sentiment

# Trending sectors
$sectors = Invoke-WebRequest -UseBasicParsing `
  "http://localhost:8000/api/v1/analytics/trending-sectors" | ConvertFrom-Json
$sectors | Format-Table sector, mention_count, avg_sentiment, video_count

# Pipeline health
$status = Invoke-WebRequest -UseBasicParsing `
  "http://localhost:8000/api/v1/admin/pipeline/status" `
  -Headers @{"X-Admin-Key"="changeme-admin-key"} | ConvertFrom-Json
$status | Format-List
```

---

## What the System Does

### ✅ Currently Supported
- **YouTube videos only** - analyzes financial commentary from YouTube channels
- **Automatic transcription** - converts video audio to text
- **AI extraction** - finds companies, sentiment, price targets, insights
- **Semantic search** - search by meaning, not just keywords
- **RAG chat** - ask questions, get answers with sources
- **Analytics** - trending stocks, sectors, sentiment over time

### ❌ NOT Currently Supported
- **Web articles** - blog posts, news sites (would need new provider)
- **PDFs** - research reports, earnings docs (would need PDF parser)
- **Twitter/X** - social media posts (would need Twitter API)
- **Earnings calls** - audio from company websites (different source)
- **SEC filings** - 10-K, 10-Q documents (would need EDGAR parser)

**To add these:** You'd need to build additional providers in Phase 2

---

## Monitoring

### View Logs
```powershell
# API logs
docker logs mw_api -f

# Worker logs (shows processing progress)
docker logs mw_worker -f

# Database logs
docker logs mw_postgres --tail=50

# Redis logs
docker logs mw_redis --tail=50
```

### Common Log Messages

**Success indicators:**
```
✓ "Discovered X videos for channel..."
✓ "Transcript generated: X words"
✓ "Analysis complete for video..."
✓ "Generated X embeddings for video..."
```

**Error indicators:**
```
✗ "YouTube API quota exceeded"
✗ "OpenAI API error: insufficient_quota"
✗ "Failed to download audio"
✗ "Transcription failed"
```

---

## Troubleshooting

### "YouTube API quota exceeded"
**Solution:** Wait until next day (resets midnight PT) or upgrade quota

### "OpenAI API error: insufficient_quota"  
**Solution:** Add credits at [OpenAI Billing](https://platform.openai.com/account/billing)

### Videos stuck in INDEXED status
**Solution:** Check worker logs for errors:
```powershell
docker logs mw_worker | Select-String "ERROR"
```

### Containers not starting
**Solution:** Check if ports are available:
```powershell
netstat -ano | findstr "8000 5432 6379"
```

### Out of memory
**Solution:** Increase Docker Desktop memory limit:
- Docker Desktop → Settings → Resources → Memory → 8GB

---

## Stop the System

```powershell
cd infra
docker-compose down

# Remove all data (fresh start)
docker-compose down -v
```

---

## Next Steps

1. **Process more videos:** Change `VIDEO_LOOKBACK_DAYS=30` in `.env`
2. **Add more channels:** Add IDs to `YOUTUBE_CHANNEL_IDS`
3. **Schedule automatic updates:** Jobs run daily by default
4. **Build a frontend:** Use the API endpoints
5. **Read the full E2E test plan:** See `E2E-TEST-PLAN.md`

---

## Cost Tracking

Monitor spending:
```powershell
# OpenAI usage
Write-Host "Check: https://platform.openai.com/usage"

# YouTube quota
$quota = Invoke-WebRequest -UseBasicParsing `
  "http://localhost:8000/api/v1/admin/quota" `
  -Headers @{"X-Admin-Key"="changeme-admin-key"} | ConvertFrom-Json
Write-Host "YouTube quota used: $($quota.youtube.used_today) / $($quota.youtube.daily_limit)"
```

**Typical costs:**
- YouTube: FREE (within quota)
- Per video (10 min): ~$0.90
- 100 videos/month: ~$90/month
- 1000 videos/month: ~$900/month

---

## Need Help?

1. Check logs: `docker logs mw_worker -f`
2. Verify health: `curl http://localhost:8000/health`
3. View API docs: http://localhost:8000/docs
4. Read full test plan: `E2E-TEST-PLAN.md`
5. Check completion report: `PHASE1A-COMPLETION.md`

**System is ready to use! 🚀**
