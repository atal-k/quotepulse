"""Provider-specific LLM and embedding client. Gemini calls live only here (CLAUDE §3, §13);
everything else talks to the `Embedder` protocol from context/embeddings.py."""

import asyncio
from collections.abc import Sequence

import httpx
from pydantic import BaseModel

from app.context.embeddings import EMBEDDING_DIMENSIONS, Embedder, EmbeddingError, EmbedTask
from app.core.config import settings

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_TIMEOUT_SECONDS = 30.0
# Single-text calls only: the model's supported generation methods have no synchronous batch.
GEMINI_MAX_CONCURRENCY = 5


class _EmbeddingValues(BaseModel):
    values: list[float]


class _EmbedContentResponse(BaseModel):
    embedding: _EmbeddingValues


class GeminiEmbedder:
    """Implements the `Embedder` protocol over the Gemini REST API. Retries are the caller's
    decision: a failed call raises EmbeddingError and nothing here retries."""

    def __init__(self, *, api_key: str, model: str, client: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self.model = model
        self._client = client

    async def embed(self, texts: Sequence[str], task: EmbedTask) -> list[list[float]]:
        if not texts:
            return []
        semaphore = asyncio.Semaphore(GEMINI_MAX_CONCURRENCY)

        async def embed_one(text: str) -> list[float]:
            async with semaphore:
                return await self._embed_one(text, task)

        return list(await asyncio.gather(*(embed_one(text) for text in texts)))

    async def _embed_one(self, text: str, task: EmbedTask) -> list[float]:
        # The key travels in a header, never the URL, so it cannot end up in access logs.
        try:
            response = await self._client.post(
                f"{GEMINI_BASE_URL}/models/{self.model}:embedContent",
                headers={"x-goog-api-key": self._api_key},
                json={
                    "content": {"parts": [{"text": text}]},
                    "taskType": task.value,
                    "outputDimensionality": EMBEDDING_DIMENSIONS,
                },
                timeout=GEMINI_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"Gemini embedding request failed: {type(exc).__name__}") from exc
        if response.status_code != 200:
            raise EmbeddingError(f"Gemini embedding returned HTTP {response.status_code}")
        try:
            parsed = _EmbedContentResponse.model_validate(response.json())
        except ValueError as exc:
            raise EmbeddingError("Gemini embedding response was malformed") from exc
        values = parsed.embedding.values
        if len(values) != EMBEDDING_DIMENSIONS:
            raise EmbeddingError(
                f"Gemini returned {len(values)} dimensions, expected {EMBEDDING_DIMENSIONS}"
            )
        return values


def build_embedder(client: httpx.AsyncClient) -> Embedder:
    """Builds the configured embedder. Fails fast when the key is missing, so a job never
    starts and then fails on its first embedding call."""
    if settings.gemini_api_key is None:
        raise EmbeddingError("GEMINI_API_KEY is not configured")
    return GeminiEmbedder(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.embedding_model,
        client=client,
    )
