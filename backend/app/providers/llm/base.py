"""
LLM and Embedding provider interfaces.

All LLM adapters (OpenAI today, self-hosted later) implement LLMProvider.
Embedding adapters implement EmbeddingProvider.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Parsed response from a single LLM call."""
    content: str                   # raw text / JSON string from the model
    model_used: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @property
    def estimated_cost_usd(self) -> float:
        """Rough cost estimate — actual rates live in the OpenAI provider."""
        return 0.0


class LLMProvider(ABC):
    """Port for language model completions."""

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_format: str = "text",   # "text" | "json_object"
    ) -> LLMResponse:
        """
        Send a chat completion request.
        Raises ExternalServiceError on API failures, QuotaExceededError on 429.
        """


class EmbeddingProvider(ABC):
    """Port for text embeddings."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts.
        Returns list of float vectors, one per input text.
        """
