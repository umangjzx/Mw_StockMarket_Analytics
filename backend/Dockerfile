# ── Base stage ────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

WORKDIR /app

# System deps needed by psycopg2 and httpx
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Deps stage ────────────────────────────────────────────────────────────────
FROM base AS deps

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        fastapi \
        uvicorn[standard] \
        pydantic \
        pydantic-settings \
        "sqlalchemy[asyncio]" \
        alembic \
        asyncpg \
        psycopg2-binary \
        "celery[redis]" \
        redis \
        pgvector \
        httpx \
        "python-jose[cryptography]" \
        "passlib[bcrypt]" \
        python-multipart \
        email-validator \
        google-api-python-client \
        google-auth \
        openai \
        isodate \
        "sentry-sdk[fastapi]" \
        prometheus-client \
        python-json-logger \
        tenacity \
        yt-dlp \
        youtube-transcript-api \
        yfinance \
        lxml

# ── Final stage ────────────────────────────────────────────────────────────────
FROM base AS final

COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
