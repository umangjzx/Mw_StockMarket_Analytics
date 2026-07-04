"""Change embeddings to 768 dimensions for nomic-embed-text (Ollama)

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 00:00:00.000000

"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the existing HNSW index first (can't modify vector dims in place)
    op.execute("DROP INDEX IF EXISTS idx_embeddings_hnsw")

    # Recreate embeddings table with 768 dims (nomic-embed-text / Ollama)
    op.execute("DROP TABLE IF EXISTS embeddings CASCADE")
    op.execute("""
        CREATE TABLE embeddings (
            id          BIGSERIAL PRIMARY KEY,
            video_id    BIGINT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
            segment_id  BIGINT REFERENCES transcript_segments(id) ON DELETE SET NULL,
            embedding   VECTOR(768) NOT NULL,
            model_used  TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX idx_embeddings_hnsw ON embeddings "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )
    op.execute("CREATE INDEX idx_embeddings_video ON embeddings (video_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_embeddings_hnsw")
    op.execute("DROP TABLE IF EXISTS embeddings CASCADE")
    op.execute("""
        CREATE TABLE embeddings (
            id          BIGSERIAL PRIMARY KEY,
            video_id    BIGINT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
            segment_id  BIGINT REFERENCES transcript_segments(id) ON DELETE SET NULL,
            embedding   VECTOR(1536) NOT NULL,
            model_used  TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX idx_embeddings_hnsw ON embeddings "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )
    op.execute("CREATE INDEX idx_embeddings_video ON embeddings (video_id)")
