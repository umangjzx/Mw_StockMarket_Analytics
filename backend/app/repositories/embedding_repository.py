"""
Embedding repository — pgvector similarity queries and embedding upserts.

This is the only place that writes raw pgvector SQL.
All vector similarity searches are expressed here so they can be swapped to
a dedicated vector store later without touching service code.
"""

from decimal import Decimal

from sqlalchemy import bindparam, delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embedding import Embedding
from app.models.transcript import TranscriptSegment
from app.models.video import Video


class EmbeddingRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_for_video(
        self,
        video_id: int,
        embeddings: list[dict],  # [{segment_id, embedding, model_used}]
    ) -> int:
        """
        Atomically delete existing embeddings for a video, then insert fresh ones.
        Returns the number of embeddings inserted.
        """
        await self._session.execute(
            delete(Embedding).where(Embedding.video_id == video_id)
        )

        for item in embeddings:
            emb = Embedding(
                transcript_segment_id=item["segment_id"],
                video_id=video_id,
                embedding=item["embedding"],
                model_used=item["model_used"],
            )
            self._session.add(emb)

        await self._session.flush()
        return len(embeddings)

    async def similarity_search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        video_id: int | None = None,
        video_ids: list[int] | None = None,
        channel_id: int | None = None,
        date_from: str | None = None,    # ISO date string
        date_to: str | None = None,
    ) -> list[dict]:
        """
        Return the top-k most similar transcript segments using cosine similarity.

        `video_ids` scopes the search to a set of videos (e.g. all videos
        mentioning a given ticker) and takes precedence over the single
        `video_id` filter if both are given.

        Returns list of dicts:
        {
            segment_id, video_id, transcript_id,
            text, start_seconds, end_seconds,
            similarity,
            video_title, external_video_id, published_at, channel_id
        }
        """
        # Build WHERE clauses dynamically
        where_clauses = []
        params: dict = {
            "query_vec": str(query_vector),
            "top_k": top_k,
        }
        extra_bindparams = []

        if video_ids:
            where_clauses.append("e.video_id IN :video_ids")
            params["video_ids"] = tuple(video_ids)
            extra_bindparams.append(bindparam("video_ids", expanding=True))
        elif video_id is not None:
            where_clauses.append("e.video_id = :video_id")
            params["video_id"] = video_id
        if channel_id is not None:
            where_clauses.append("v.channel_id = :channel_id")
            params["channel_id"] = channel_id
        if date_from is not None:
            where_clauses.append("v.published_at >= :date_from")
            params["date_from"] = date_from
        if date_to is not None:
            where_clauses.append("v.published_at <= :date_to")
            params["date_to"] = date_to

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        sql = text(f"""
            SELECT
                e.id            AS embedding_id,
                e.transcript_segment_id AS segment_id,
                e.video_id,
                ts.transcript_id,
                ts.text,
                ts.start_seconds,
                ts.end_seconds,
                ts.sequence_no,
                1 - (e.embedding <=> CAST(:query_vec AS vector)) AS similarity,
                v.title         AS video_title,
                v.external_video_id,
                v.published_at,
                v.channel_id
            FROM embeddings e
            JOIN transcript_segments ts ON ts.id = e.transcript_segment_id
            JOIN videos v               ON v.id  = e.video_id
            {where_sql}
            ORDER BY e.embedding <=> CAST(:query_vec AS vector)
            LIMIT :top_k
        """)
        if extra_bindparams:
            sql = sql.bindparams(*extra_bindparams)

        result = await self._session.execute(sql, params)
        rows = result.mappings().all()
        return [dict(r) for r in rows]

    async def count_for_video(self, video_id: int) -> int:
        result = await self._session.execute(
            select(Embedding).where(Embedding.video_id == video_id)
        )
        return len(result.scalars().all())
