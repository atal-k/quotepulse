import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.agents import llm
from app.agents.llm import GeminiEmbedder, build_embedder
from app.context.embeddings import EMBEDDING_DIMENSIONS, EmbeddingError, EmbedTask

API_KEY = "test-key-do-not-leak"


def _vector(seed: float) -> list[float]:
    return [seed] + [0.0] * (EMBEDDING_DIMENSIONS - 1)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ok_handler(request: httpx.Request) -> httpx.Response:
    text = json.loads(request.content)["content"]["parts"][0]["text"]
    return httpx.Response(200, json={"embedding": {"values": _vector(float(len(text)))}})


def _embedder(client: httpx.AsyncClient) -> GeminiEmbedder:
    return GeminiEmbedder(api_key=API_KEY, model="gemini-embedding-2", client=client)


async def test_returns_one_vector_per_text_in_input_order() -> None:
    texts = ["a", "bbb", "cc"]
    async with _client(_ok_handler) as client:
        vectors = await _embedder(client).embed(texts, EmbedTask.DOCUMENT)
    assert vectors == [_vector(1.0), _vector(3.0), _vector(2.0)]


async def test_empty_input_makes_no_request() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    async with _client(fail) as client:
        assert await _embedder(client).embed([], EmbedTask.QUERY) == []


async def test_request_declares_task_dimension_and_key_in_header_not_url() -> None:
    seen: list[httpx.Request] = []

    def capture(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _ok_handler(request)

    async with _client(capture) as client:
        await _embedder(client).embed(["hello"], EmbedTask.QUERY)

    (request,) = seen
    body: dict[str, Any] = json.loads(request.content)
    assert body["taskType"] == "RETRIEVAL_QUERY"
    assert body["outputDimensionality"] == EMBEDDING_DIMENSIONS
    assert request.headers["x-goog-api-key"] == API_KEY
    assert API_KEY not in str(request.url)
    assert request.url.path == "/v1beta/models/gemini-embedding-2:embedContent"


async def test_wrong_dimension_raises() -> None:
    def short(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embedding": {"values": [0.1, 0.2]}})

    async with _client(short) as client:
        with pytest.raises(EmbeddingError, match="expected 768"):
            await _embedder(client).embed(["x"], EmbedTask.DOCUMENT)


async def test_http_error_raises_without_leaking_the_key() -> None:
    def unauthorized(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text=f"denied for {API_KEY}")

    async with _client(unauthorized) as client:
        with pytest.raises(EmbeddingError) as info:
            await _embedder(client).embed(["x"], EmbedTask.DOCUMENT)
    assert "403" in str(info.value)
    assert API_KEY not in str(info.value)


async def test_malformed_body_raises() -> None:
    def junk(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    async with _client(junk) as client:
        with pytest.raises(EmbeddingError, match="malformed"):
            await _embedder(client).embed(["x"], EmbedTask.DOCUMENT)


async def test_transport_failure_raises_embedding_error() -> None:
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    async with _client(unreachable) as client:
        with pytest.raises(EmbeddingError, match="ConnectError"):
            await _embedder(client).embed(["x"], EmbedTask.DOCUMENT)


async def test_build_embedder_fails_fast_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm.settings, "gemini_api_key", None)
    async with _client(_ok_handler) as client:
        with pytest.raises(EmbeddingError, match="not configured"):
            build_embedder(client)


@pytest.mark.llm
async def test_live_gemini_embedding_has_expected_shape() -> None:
    """Live smoke test: one real call. Excluded by default (pyproject `-m 'not llm'`)."""
    async with httpx.AsyncClient() as client:
        embedder = build_embedder(client)
        (vector,) = await embedder.embed(
            ["500 pcs 6mm SS bolts and 200 bearings 6204"], EmbedTask.DOCUMENT
        )
    assert len(vector) == EMBEDDING_DIMENSIONS
