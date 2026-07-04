"""Fix embeddings.segment_id column drift introduced by 0002

Migration 0002 recreated the embeddings table for the 768-dim change and
accidentally renamed transcript_segment_id -> segment_id, dropping its
NOT NULL and UNIQUE constraints in the process. The ORM model, the
embedding repository, and its raw pgvector similarity SQL all still
reference transcript_segment_id. This restores the original 0001 column
name and constraints so the schema matches the application code.

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-03 00:00:00.000000

"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE embeddings RENAME COLUMN segment_id TO transcript_segment_id"
    )
    op.execute(
        "ALTER TABLE embeddings ALTER COLUMN transcript_segment_id SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE embeddings ADD CONSTRAINT embeddings_transcript_segment_id_key "
        "UNIQUE (transcript_segment_id)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE embeddings DROP CONSTRAINT IF EXISTS embeddings_transcript_segment_id_key"
    )
    op.execute(
        "ALTER TABLE embeddings ALTER COLUMN transcript_segment_id DROP NOT NULL"
    )
    op.execute(
        "ALTER TABLE embeddings RENAME COLUMN transcript_segment_id TO segment_id"
    )
