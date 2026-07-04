"""Company Intelligence Phase 1 — market data tables

Adds company_profiles, market_quotes, and price_bars. Additive only — no
changes to companies/tickers/video_companies, so the video-analysis pipeline
is unaffected.

Revision ID: 0004
Revises: 0003
Create Date: 2024-01-04 00:00:00.000000

"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE company_profiles (
            company_id          BIGINT PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
            description         TEXT,
            ceo                 TEXT,
            headquarters        TEXT,
            employees           INTEGER,
            website             TEXT,
            primary_exchange    TEXT,
            ipo_date            DATE,
            business_segments   JSONB,
            source              TEXT NOT NULL,
            source_url          TEXT,
            fetched_at          TIMESTAMP NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE market_quotes (
            ticker_id           BIGINT PRIMARY KEY REFERENCES tickers(id) ON DELETE CASCADE,
            price               NUMERIC(18, 4),
            change_abs          NUMERIC(18, 4),
            change_pct          NUMERIC(9, 4),
            open                NUMERIC(18, 4),
            high                NUMERIC(18, 4),
            low                 NUMERIC(18, 4),
            prev_close          NUMERIC(18, 4),
            volume              BIGINT,
            market_cap          NUMERIC(24, 2),
            week52_high         NUMERIC(18, 4),
            week52_low          NUMERIC(18, 4),
            bid                 NUMERIC(18, 4),
            ask                 NUMERIC(18, 4),
            vwap                NUMERIC(18, 4),
            pre_market_price    NUMERIC(18, 4),
            after_hours_price   NUMERIC(18, 4),
            currency            TEXT,
            source              TEXT NOT NULL,
            fetched_at          TIMESTAMP NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE price_bars (
            id          BIGSERIAL PRIMARY KEY,
            ticker_id   BIGINT NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
            interval    TEXT NOT NULL,
            ts          TIMESTAMP NOT NULL,
            open        NUMERIC(18, 4) NOT NULL,
            high        NUMERIC(18, 4) NOT NULL,
            low         NUMERIC(18, 4) NOT NULL,
            close       NUMERIC(18, 4) NOT NULL,
            volume      BIGINT,
            CONSTRAINT uq_price_bars_ticker_interval_ts UNIQUE (ticker_id, interval, ts)
        )
    """)
    op.execute("CREATE INDEX idx_price_bars_ticker_interval ON price_bars (ticker_id, interval)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS price_bars")
    op.execute("DROP TABLE IF EXISTS market_quotes")
    op.execute("DROP TABLE IF EXISTS company_profiles")
