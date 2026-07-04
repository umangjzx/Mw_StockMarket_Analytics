"""
Chat (RAG) endpoints.

POST /chat/sessions                  — create a session
POST /chat/sessions/{id}/messages    — ask a question, get a grounded answer
GET  /chat/sessions/{id}             — fetch session metadata
GET  /chat/sessions/{id}/messages    — paginated message history

Sessions are stored in Redis (TTL 7 days) so there's no DB table to migrate.
Message history is stored per-session in Redis as a JSON list.
"""

import json
import uuid
from datetime import UTC, datetime

import redis as redis_sync

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.schemas.search import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    CitationResponse,
)
from app.services.rag_chat_service import RagChatService

router = APIRouter(prefix="/chat", tags=["chat"])

SESSION_TTL = 60 * 60 * 24 * 7  # 7 days


def _redis() -> redis_sync.Redis:
    return redis_sync.from_url(settings.REDIS_URL, decode_responses=True)


def _session_key(session_id: str) -> str:
    return f"chat:session:{session_id}"


def _messages_key(session_id: str) -> str:
    return f"chat:messages:{session_id}"


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
async def create_session(body: ChatSessionCreate) -> ChatSessionResponse:
    """Create a new chat session, optionally scoped to a ticker or channel."""
    session_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    session_data = {
        "id": session_id,
        "created_at": now.isoformat(),
        "ticker": body.ticker,
        "channel_id": body.channel_id,
    }

    r = _redis()
    r.setex(_session_key(session_id), SESSION_TTL, json.dumps(session_data))

    return ChatSessionResponse(
        id=session_id,
        created_at=now,
        ticker=body.ticker,
        channel_id=body.channel_id,
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(session_id: str) -> ChatSessionResponse:
    """Fetch session metadata."""
    r = _redis()
    raw = r.get(_session_key(session_id))
    if not raw:
        raise NotFoundError(f"Chat session {session_id} not found or expired")
    data = json.loads(raw)
    return ChatSessionResponse(
        id=data["id"],
        created_at=datetime.fromisoformat(data["created_at"]),
        ticker=data.get("ticker"),
        channel_id=data.get("channel_id"),
    )


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    session_id: str,
    body: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatMessageResponse:
    """
    Ask a question in a chat session.
    Retrieves relevant transcript chunks, builds a grounded answer with citations.
    """
    r = _redis()
    raw = r.get(_session_key(session_id))
    if not raw:
        raise NotFoundError(f"Chat session {session_id} not found or expired")

    session_data = json.loads(raw)

    provider = (
        __import__("app.providers.llm.ollama_provider", fromlist=["OllamaProvider"]).OllamaProvider()
        if settings.LLM_PROVIDER == "ollama"
        else __import__("app.providers.llm.openai_provider", fromlist=["OpenAIProvider"]).OpenAIProvider()
    )
    service = RagChatService(session=db, llm=provider, embedder=provider)

    result = await service.answer(
        question=body.question,
        top_k=body.top_k,
        channel_id=session_data.get("channel_id"),
    )

    # Persist message to session history
    message = {
        "role": "user",
        "content": body.question,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    assistant_message = {
        "role": "assistant",
        "content": result.answer,
        "citations": [
            {
                "video_id": c.video_id,
                "video_title": c.video_title,
                "channel_name": c.channel_name,
                "published_at": c.published_at.isoformat() if c.published_at else None,
                "start_seconds": c.start_seconds,
            }
            for c in result.citations
        ],
        "timestamp": datetime.now(UTC).isoformat(),
    }

    messages_key = _messages_key(session_id)
    history_raw = r.get(messages_key)
    history = json.loads(history_raw) if history_raw else []
    history.extend([message, assistant_message])
    r.setex(messages_key, SESSION_TTL, json.dumps(history))
    r.expire(_session_key(session_id), SESSION_TTL)  # reset TTL on activity

    return ChatMessageResponse(
        session_id=session_id,
        question=body.question,
        answer=result.answer,
        citations=[
            CitationResponse(
                video_id=c.video_id,
                video_title=c.video_title,
                channel_name=c.channel_name,
                published_at=c.published_at,
                start_seconds=c.start_seconds,
            )
            for c in result.citations
        ],
        retrieved_chunks=result.retrieved_chunks,
        model_used=result.model_used,
    )


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """Paginated message history for a session."""
    r = _redis()
    if not r.exists(_session_key(session_id)):
        raise NotFoundError(f"Chat session {session_id} not found or expired")

    history_raw = r.get(_messages_key(session_id))
    history = json.loads(history_raw) if history_raw else []

    start = (page - 1) * page_size
    end = start + page_size
    page_items = history[start:end]

    return {
        "session_id": session_id,
        "messages": page_items,
        "page": page,
        "page_size": page_size,
        "total": len(history),
    }
