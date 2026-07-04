"""
OpenAI provider — implements both LLMProvider and EmbeddingProvider.

All OpenAI calls are logged with token counts and estimated cost
(tracked against the video_id for per-video spend reporting).
"""

from openai import AsyncOpenAI
from openai import RateLimitError, APIError

from app.core.config import settings
from app.core.exceptions import ExternalServiceError, QuotaExceededError
from app.core.logging import get_logger
from app.providers.llm.base import EmbeddingProvider, LLMProvider, LLMResponse

logger = get_logger(__name__)

# Approximate cost per 1K tokens (USD) — update as OpenAI pricing changes
_COST_PER_1K: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.000150, "output": 0.000600},
    "gpt-4o":      {"input": 0.005000, "output": 0.015000},
    "gpt-4-turbo": {"input": 0.010000, "output": 0.030000},
}
_EMBEDDING_COST_PER_1K = {
    "text-embedding-3-small": 0.000020,
    "text-embedding-3-large": 0.000130,
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = _COST_PER_1K.get(model, {"input": 0.0, "output": 0.0})
    return (prompt_tokens / 1000) * rates["input"] + (completion_tokens / 1000) * rates["output"]


class OpenAIProvider(LLMProvider, EmbeddingProvider):
    """Async OpenAI client implementing both LLM and Embedding ports."""

    def __init__(self, api_key: str | None = None) -> None:
        self._client = AsyncOpenAI(api_key=api_key or settings.OPENAI_API_KEY)
        self._model = settings.OPENAI_LLM_MODEL
        self._embed_model = settings.OPENAI_EMBEDDING_MODEL

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_format: str = "text",
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self._model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens or settings.OPENAI_MAX_TOKENS
        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except RateLimitError as exc:
            raise QuotaExceededError(f"OpenAI rate limit exceeded: {exc}") from exc
        except APIError as exc:
            raise ExternalServiceError(f"OpenAI API error: {exc}") from exc

        usage = resp.usage
        prompt_tokens    = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens     = usage.total_tokens if usage else 0
        content = resp.choices[0].message.content or ""

        cost = _estimate_cost(self._model, prompt_tokens, completion_tokens)
        logger.info(
            "OpenAI completion",
            extra={
                "model": self._model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "estimated_cost_usd": round(cost, 6),
            },
        )

        return LLMResponse(
            content=content,
            model_used=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            resp = await self._client.embeddings.create(
                model=self._embed_model,
                input=texts,
            )
        except RateLimitError as exc:
            raise QuotaExceededError(f"OpenAI embeddings rate limit: {exc}") from exc
        except APIError as exc:
            raise ExternalServiceError(f"OpenAI embeddings API error: {exc}") from exc

        # Sort by index to preserve order
        items = sorted(resp.data, key=lambda x: x.index)
        tokens = resp.usage.total_tokens if resp.usage else 0
        cost = (tokens / 1000) * _EMBEDDING_COST_PER_1K.get(self._embed_model, 0.0)
        logger.info(
            "OpenAI embeddings",
            extra={"texts": len(texts), "tokens": tokens, "estimated_cost_usd": round(cost, 6)},
        )
        return [item.embedding for item in items]
