"""Company Intelligence Phase 3 — news, analyst insights, executive summary

Adds news_articles, analyst_snapshots, executive_summaries. Additive only.

Revision ID: 0006
Revises: 0005
Create Date: 2024-01-06 00:00:00.000000

"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE news_articles (
            id              BIGSERIAL PRIMARY KEY,
            company_id      BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            title           TEXT NOT NULL,
            summary         TEXT NOT NULL,
            source          TEXT NOT NULL,
            url             TEXT NOT NULL,
            published_at    TIMESTAMP NOT NULL,
            thumbnail_url   TEXT,
            sentiment       TEXT,
            impact_score    NUMERIC(5, 2),
            related_tickers JSONB,
            fetched_at      TIMESTAMP NOT NULL,
            CONSTRAINT uq_news_articles_company_url UNIQUE (company_id, url)
        )
    """)
    op.execute(
        "CREATE INDEX idx_news_articles_company_published ON news_articles (company_id, published_at)"
    )

    op.execute("""
        CREATE TABLE analyst_snapshots (
            ticker_id               BIGINT PRIMARY KEY REFERENCES tickers(id) ON DELETE CASCADE,
            recommendation_mean     NUMERIC(5, 3),
            recommendation_key      TEXT,
            target_mean             NUMERIC(14, 4),
            target_high             NUMERIC(14, 4),
            target_low              NUMERIC(14, 4),
            target_median           NUMERIC(14, 4),
            num_analyst_opinions    INTEGER,
            held_pct_institutions   NUMERIC(9, 6),
            held_pct_insiders       NUMERIC(9, 6),
            recommendation_trend    JSONB NOT NULL DEFAULT '[]',
            actions                 JSONB NOT NULL DEFAULT '[]',
            institutional_holders   JSONB NOT NULL DEFAULT '[]',
            insider_transactions    JSONB NOT NULL DEFAULT '[]',
            source                  TEXT NOT NULL,
            fetched_at              TIMESTAMP NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE executive_summaries (
            ticker_id           BIGINT PRIMARY KEY REFERENCES tickers(id) ON DELETE CASCADE,
            business_overview   TEXT NOT NULL,
            market_outlook      TEXT NOT NULL,
            why_moving_today    TEXT NOT NULL,
            positive_factors    JSONB NOT NULL DEFAULT '[]',
            risks               JSONB NOT NULL DEFAULT '[]',
            opportunities       JSONB NOT NULL DEFAULT '[]',
            financial_health    TEXT NOT NULL,
            technical_outlook   TEXT NOT NULL,
            news_summary        TEXT NOT NULL,
            overall_sentiment   TEXT NOT NULL,
            investment_thesis   TEXT NOT NULL,
            short_term_outlook  TEXT NOT NULL,
            long_term_outlook   TEXT NOT NULL,
            confidence_score    NUMERIC(5, 2) NOT NULL,
            source              TEXT NOT NULL,
            fetched_at          TIMESTAMP NOT NULL
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS executive_summaries")
    op.execute("DROP TABLE IF EXISTS analyst_snapshots")
    op.execute("DROP TABLE IF EXISTS news_articles")
