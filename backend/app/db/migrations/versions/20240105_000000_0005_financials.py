"""Company Intelligence Phase 2 — financials, ratios, earnings tables

Adds financial_statements, ratios, and earnings. Additive only — no changes
to companies/tickers or the Phase 1 market_data tables.

Revision ID: 0005
Revises: 0004
Create Date: 2024-01-05 00:00:00.000000

"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE financial_statements (
            id              BIGSERIAL PRIMARY KEY,
            company_id      BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            statement_type  TEXT NOT NULL,
            period_type     TEXT NOT NULL,
            period_end      DATE NOT NULL,
            line_items      JSONB NOT NULL,
            source          TEXT NOT NULL,
            fetched_at      TIMESTAMP NOT NULL,
            CONSTRAINT uq_financial_statements_period
                UNIQUE (company_id, statement_type, period_type, period_end)
        )
    """)
    op.execute(
        "CREATE INDEX idx_financial_statements_company ON financial_statements "
        "(company_id, statement_type, period_type)"
    )

    op.execute("""
        CREATE TABLE ratios (
            ticker_id           BIGINT PRIMARY KEY REFERENCES tickers(id) ON DELETE CASCADE,
            pe_trailing         NUMERIC(12, 4),
            pe_forward          NUMERIC(12, 4),
            peg_ratio           NUMERIC(12, 4),
            price_to_book       NUMERIC(12, 4),
            ev_to_ebitda        NUMERIC(12, 4),
            roe                 NUMERIC(12, 6),
            roa                 NUMERIC(12, 6),
            roic                NUMERIC(12, 6),
            debt_to_equity      NUMERIC(12, 4),
            dividend_yield      NUMERIC(9, 6),
            current_ratio       NUMERIC(9, 4),
            quick_ratio         NUMERIC(9, 4),
            eps_trailing        NUMERIC(12, 4),
            eps_forward         NUMERIC(12, 4),
            beta                NUMERIC(9, 4),
            source              TEXT NOT NULL,
            fetched_at          TIMESTAMP NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE earnings (
            company_id              BIGINT PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
            next_earnings_date      DATE,
            eps_estimate_low        NUMERIC(12, 4),
            eps_estimate_avg        NUMERIC(12, 4),
            eps_estimate_high       NUMERIC(12, 4),
            revenue_estimate_low    NUMERIC(20, 2),
            revenue_estimate_avg    NUMERIC(20, 2),
            revenue_estimate_high   NUMERIC(20, 2),
            history                 JSONB NOT NULL DEFAULT '[]',
            ai_summary              TEXT,
            source                  TEXT NOT NULL,
            fetched_at              TIMESTAMP NOT NULL
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS earnings")
    op.execute("DROP TABLE IF EXISTS ratios")
    op.execute("DROP TABLE IF EXISTS financial_statements")
