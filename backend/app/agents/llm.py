"""Provider-specific LLM and embedding client. Gemini calls live only here (CLAUDE §3, §13);
everything else talks to the `Embedder` protocol from context/embeddings.py."""

import asyncio
import re
from collections.abc import Sequence
from typing import Literal

import httpx
from pydantic import BaseModel

from app.agents.prompts.activity_insight import build_prompt
from app.context.embeddings import EMBEDDING_DIMENSIONS, Embedder, EmbeddingError, EmbedTask
from app.core.config import settings

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_TIMEOUT_SECONDS = 30.0
# Single-text calls only: the model's supported generation methods have no synchronous batch.
GEMINI_MAX_CONCURRENCY = 5
# Gemini sometimes wraps JSON output in a markdown fence despite responseMimeType; defensive.
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


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


class ActivityEntities(BaseModel):
    products: list[str] = []
    quantities: list[str] = []
    dates: list[str] = []


class ActivityInsight(BaseModel):
    """Structured read of one activity (ARCHITECTURE §7). Parsed from the LLM's JSON output and
    stored in `activities.meta["insight"]` — never trusted directly, always Pydantic-validated
    first (CLAUDE §2.7)."""

    summary: str
    sentiment: Literal["positive", "neutral", "negative"]
    intents: list[str]
    next_steps: list[str]
    entities: ActivityEntities


class InsightExtractionError(Exception):
    """Insight generation failed, or its output didn't parse as ActivityInsight after one
    retry. Callers (the process_activity job) decide what "fail closed to a human" means."""


class _Part(BaseModel):
    text: str


class _Content(BaseModel):
    parts: list[_Part]


class _Candidate(BaseModel):
    content: _Content


class _GenerateContentResponse(BaseModel):
    candidates: list[_Candidate] = []


class GeminiInsightExtractor:
    """Gemini Flash-Lite ActivityInsight extraction. Retries once on invalid JSON/parse
    (CLAUDE §2.7); transport/HTTP/envelope failures are not retried here — they propagate so
    RQ's own retry handles them (process_activity is idempotent and safe to re-run)."""

    def __init__(self, *, api_key: str, model: str, client: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self.model = model
        self._client = client

    async def extract(self, subject: str, body: str) -> ActivityInsight:
        last_error: Exception | None = None
        for _ in range(2):
            text = await self._generate(build_prompt(subject, body))
            try:
                return ActivityInsight.model_validate_json(_strip_json_fence(text))
            except ValueError as exc:
                last_error = exc
        raise InsightExtractionError(
            "Gemini insight output did not parse as ActivityInsight after one retry"
        ) from last_error

    async def _generate(self, prompt: str) -> str:
        # The key travels in a header, never the URL, so it cannot end up in access logs.
        try:
            response = await self._client.post(
                f"{GEMINI_BASE_URL}/models/{self.model}:generateContent",
                headers={"x-goog-api-key": self._api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0,
                        "responseMimeType": "application/json",
                    },
                },
                timeout=GEMINI_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise InsightExtractionError(
                f"Gemini insight request failed: {type(exc).__name__}"
            ) from exc
        if response.status_code != 200:
            raise InsightExtractionError(f"Gemini insight returned HTTP {response.status_code}")
        try:
            parsed = _GenerateContentResponse.model_validate(response.json())
        except ValueError as exc:
            raise InsightExtractionError("Gemini insight response was malformed") from exc
        if not parsed.candidates or not parsed.candidates[0].content.parts:
            raise InsightExtractionError("Gemini insight response had no candidates")
        return parsed.candidates[0].content.parts[0].text


def _strip_json_fence(text: str) -> str:
    return _JSON_FENCE_RE.sub("", text).strip()


def build_insight_extractor(client: httpx.AsyncClient) -> GeminiInsightExtractor:
    """Builds the configured insight extractor. Fails fast when the key is missing, so a job
    never starts and then fails on its first generation call."""
    if settings.gemini_api_key is None:
        raise InsightExtractionError("GEMINI_API_KEY is not configured")
    return GeminiInsightExtractor(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.insight_model,
        client=client,
    )
