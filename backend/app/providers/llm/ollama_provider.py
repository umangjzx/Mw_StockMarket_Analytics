"""
Ollama LLM + Embedding Provider — FREE local models.

Implements both LLMProvider and EmbeddingProvider from base.py.
Uses Ollama's OpenAI-compatible API.

Models in use:
  LLM:        mistral:latest  (or llama3.1:latest)
  Embeddings: nomic-embed-text:latest  (768 dimensions)
"""

import httpx
from openai import AsyncOpenAI
from openai import APIError

from app.core.config import settings
from app.core.exceptions import ExternalServiceError, QuotaExceededError
from app.core.logging import get_logger
from app.providers.llm.base import EmbeddingProvider, LLMProvider, LLMResponse

logger = get_logger(__name__)


class OllamaProvider(LLMProvider, EmbeddingProvider):
    """
    Local LLM + Embeddings via Ollama.
    Uses Ollama's OpenAI-compatible endpoint for LLM (chat completions).
    Uses Ollama's native /api/embeddings endpoint for vectors.
    """

    def __init__(self) -> None:
        self._base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self._llm_model = settings.OLLAMA_LLM_MODEL
        self._embed_model = settings.OLLAMA_EMBEDDING_MODEL

        # ngrok tunnels require this header to skip the browser warning page
        extra_headers = {}
        if "ngrok" in self._base_url:
            extra_headers["ngrok-skip-browser-warning"] = "true"

        # Use Ollama's OpenAI-compatible endpoint for chat
        self._client = AsyncOpenAI(
            api_key="ollama",  # any non-empty string
            base_url=f"{self._base_url}/v1",
            default_headers=extra_headers,
        )
        self._extra_headers = extra_headers

    # ── LLMProvider ────────────────────────────────────────────────────────

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_format: str = "text",  # "text" | "json_object"
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self._llm_model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        # Ollama supports JSON mode via response_format
        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except APIError as exc:
            raise ExternalServiceError(f"Ollama API error: {exc}") from exc
        except Exception as exc:
            raise ExternalServiceError(f"Ollama LLM failed: {exc}") from exc

        usage = resp.usage
        prompt_tokens     = usage.prompt_tokens     if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens      = usage.total_tokens      if usage else 0
        content = resp.choices[0].message.content or ""

        logger.info(
            "Ollama completion",
            extra={
                "model": self._llm_model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        )

        try:
            from app.services.quota_tracker import QuotaTracker
            QuotaTracker().record_usage(1, service="ollama")
        except Exception as exc:
            logger.warning("Ollama quota tracking failed (non-fatal)", extra={"error": str(exc)})

        return LLMResponse(
            content=content,
            model_used=self._llm_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    # ── EmbeddingProvider ───────────────────────────────────────────────────

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via Ollama's native /api/embeddings endpoint."""
        if not texts:
            return []

        results: list[list[float]] = []

        async with httpx.AsyncClient(timeout=120.0) as client:
            for text in texts:
                try:
                    response = await client.post(
                        f"{self._base_url}/api/embeddings",
                        json={"model": self._embed_model, "prompt": text},
                        headers=self._extra_headers,
                    )
                    response.raise_for_status()
                    embedding = response.json().get("embedding")
                    if not embedding:
                        raise ExternalServiceError("Empty embedding from Ollama")
                    results.append(embedding)

                except httpx.HTTPError as exc:
                    raise ExternalServiceError(f"Ollama embedding HTTP error: {exc}") from exc
                except Exception as exc:
                    raise ExternalServiceError(f"Ollama embedding failed: {exc}") from exc

        logger.info(
            "Ollama embeddings generated",
            extra={"model": self._embed_model, "count": len(results)},
        )

        try:
            from app.services.quota_tracker import QuotaTracker
            QuotaTracker().record_usage(len(results), service="ollama")
        except Exception as exc:
            logger.warning("Ollama quota tracking failed (non-fatal)", extra={"error": str(exc)})

        return results
