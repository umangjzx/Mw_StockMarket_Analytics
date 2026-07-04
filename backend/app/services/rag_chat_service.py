"""
RAG chat service — retrieval-augmented generation for the chat assistant.

Flow:
1. Embed the question
2. Retrieve top-k transcript chunks via pgvector
3. Enrich chunks with channel name from joined video data
4. Build a grounded prompt with citations
5. Call LLM, parse citations back to structured objects
6. Validate citations against the retrieval set (no hallucinated sources)
"""

import re
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.providers.llm.base import EmbeddingProvider, LLMProvider
from app.prompts import rag_answer as prompt_mod
from app.repositories.embedding_repository import EmbeddingRepository

logger = get_logger(__name__)


@dataclass
class Citation:
    """A grounded citation back to a specific video."""
    video_id: int
    video_title: str
    channel_name: str
    published_at: datetime | None
    start_seconds: float | None


@dataclass
class ChatAnswer:
    """Structured answer returned by the RAG service."""
    answer: str
    citations: list[Citation] = field(default_factory=list)
    retrieved_chunks: int = 0
    model_used: str = ""


class RagChatService:

    def __init__(
        self,
        session: AsyncSession,
        llm: LLMProvider,
        embedder: EmbeddingProvider,
    ) -> None:
        self._session = session
        self._llm = llm
        self._embedder = embedder
        self._embed_repo = EmbeddingRepository(session)

    async def answer(
        self,
        question: str,
        top_k: int = 10,
        channel_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        video_id: int | None = None,
        video_ids: list[int] | None = None,
    ) -> ChatAnswer:
        """
        Answer a question using RAG over the transcript corpus.
        `video_ids` scopes retrieval to a set of videos (e.g. all videos
        mentioning a given ticker in the Company Intelligence module) and
        takes precedence over the single `video_id` filter if both are given.
        Returns structured answer with validated citations.
        """
        # 1. Embed question
        vectors = await self._embedder.embed([question])
        query_vector = vectors[0]

        # 2. Retrieve chunks
        chunks = await self._embed_repo.similarity_search(
            query_vector=query_vector,
            top_k=top_k,
            video_id=video_id,
            video_ids=video_ids,
            channel_id=channel_id,
            date_from=date_from.replace(tzinfo=None).isoformat() if date_from else None,
            date_to=date_to.replace(tzinfo=None).isoformat() if date_to else None,
        )

        if not chunks:
            return ChatAnswer(
                answer="No relevant content found in the database for your question.",
                retrieved_chunks=0,
            )

        # 3. Enrich with channel name (fetch once, keyed by video_id)
        channel_map = await self._get_channel_names({c["video_id"] for c in chunks})
        for chunk in chunks:
            chunk["channel_name"] = channel_map.get(chunk["video_id"], "Unknown")

        # 4. Build prompt and call LLM
        response = await self._llm.complete(
            system_prompt=prompt_mod.SYSTEM,
            user_prompt=prompt_mod.build_user_prompt(question, chunks),
            temperature=0.1,  # low temperature for factual grounding
        )

        # 5. Extract and validate citations
        valid_video_ids = {c["video_id"] for c in chunks}
        video_meta = {c["video_id"]: c for c in chunks}

        cited_ids = set(map(int, re.findall(r"\[SOURCE:\s*video_id=(\d+)\]", response.content)))
        valid_cited = cited_ids & valid_video_ids  # drop any hallucinated IDs

        if cited_ids - valid_video_ids:
            logger.warning(
                "LLM cited non-retrieved video IDs — dropped",
                extra={"hallucinated": list(cited_ids - valid_video_ids)},
            )

        citations: list[Citation] = []
        for vid_id in sorted(valid_cited):
            meta = video_meta[vid_id]
            citations.append(Citation(
                video_id=vid_id,
                video_title=meta.get("video_title", ""),
                channel_name=meta.get("channel_name", ""),
                published_at=meta.get("published_at"),
                start_seconds=float(meta["start_seconds"]) if meta.get("start_seconds") else None,
            ))

        # Clean citation markers from answer text for display
        clean_answer = re.sub(r"\s*\[SOURCE:[^\]]+\]", "", response.content).strip()

        logger.info(
            "RAG answer generated",
            extra={
                "question": question[:80],
                "chunks_retrieved": len(chunks),
                "citations": len(citations),
            },
        )

        return ChatAnswer(
            answer=clean_answer,
            citations=citations,
            retrieved_chunks=len(chunks),
            model_used=response.model_used,
        )

    async def _get_channel_names(self, video_ids: set[int]) -> dict[int, str]:
        """Batch-fetch channel display names for a set of video IDs."""
        from sqlalchemy import select
        from app.models.video import Video
        from app.models.channel import Channel
        from sqlalchemy.orm import selectinload

        result = await self._session.execute(
            select(Video)
            .options(selectinload(Video.channel))
            .where(Video.id.in_(video_ids))
        )
        videos = result.scalars().all()
        return {v.id: (v.channel.display_name if v.channel else "Unknown") for v in videos}
