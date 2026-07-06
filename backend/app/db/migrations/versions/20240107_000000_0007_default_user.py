"""Seed a single default user — personal-tool mode, no auth required

This is a single-user personal tool, not a multi-tenant product. Watchlists
and bookmarks still have a user_id FK (kept as-is rather than reworking the
schema), so this seeds exactly one row for the watchlist/bookmark endpoints
to attach to — see the removal of JWT auth on those routes in this same
change (backend/app/api/v1/routers/watchlist.py).

Revision ID: 0007
Revises: 0006
Create Date: 2024-01-07 00:00:00.000000

"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

DEFAULT_USER_ID = 1


def upgrade() -> None:
    op.execute(f"""
        INSERT INTO users (id, email, display_name, role)
        VALUES ({DEFAULT_USER_ID}, 'local@personal.tool', 'Personal', 'admin')
        ON CONFLICT (id) DO NOTHING
    """)
    # Keep the sequence ahead of the manually-inserted id so future inserts
    # (if a real auth system is ever added back) don't collide with it.
    op.execute(
        "SELECT setval('users_id_seq', (SELECT MAX(id) FROM users))"
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM users WHERE id = {DEFAULT_USER_ID}")
