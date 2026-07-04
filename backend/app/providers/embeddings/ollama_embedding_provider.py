"""
Ollama Embeddings Provider - FREE local embeddings

Uses nomic-embed-text via Ollama (768 dimensions).
No API costs, runs on your hardware.
"""

import httpx

from app.core.config import settings
from app.core.exceptions import EmbeddingError
from app.core.logging import get_logger
from app.providers.embeddings.base import EmbeddingProvider

logger = get_logger(__name__)


class OllamaEmbeddingProvider(EmbeddingProvider):
    """
    Embeddings via Ollama's local models.
    Uses nomic-embed-text which produces 768-dimensional vectors.
    FREE - runs on your own hardware.
    """

    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_EMBEDDING_MODEL  # nomic-embed-text
        self.dimensions = 768  # nomic-embed-text dimension

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        if not texts:
            return []

        results = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for text in texts:
                try:
                    response = await client.post(
                        f"{self.base_url}/api/embeddings",
                        json={
                            "model": self.model,
                            "prompt": text
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    embedding = data.get("embedding")
                    if not embedding:
                        raise EmbeddingError(f"No embedding in Ollama response")
                    
                    results.append(embedding)
                    
                except httpx.HTTPError as exc:
                    raise EmbeddingError(f"Ollama embedding error: {exc}") from exc
                except Exception as exc:
                    raise EmbeddingError(f"Embedding generation failed: {exc}") from exc

        logger.info(f"Generated {len(results)} embeddings via Ollama ({self.model})")
        return results

    @property
    def embedding_dimensions(self) -> int:
        return self.dimensions
