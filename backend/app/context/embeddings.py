from collections.abc import Sequence
from enum import StrEnum
from typing import Protocol

# Bound to every `vector(768)` column in the migrations and the ORM models. Changing it is a
# schema migration plus a re-embed, so it is a code constant on purpose, not a setting.
EMBEDDING_DIMENSIONS = 768


class EmbedTask(StrEnum):
    """Gemini embeds documents and queries with different task types; mixing them hurts
    retrieval quality, so every call declares which side of the search it is on."""

    DOCUMENT = "RETRIEVAL_DOCUMENT"  # activity summaries, KB chunks
    QUERY = "RETRIEVAL_QUERY"  # retrieve() queries


class EmbeddingError(Exception):
    """Provider call failed or returned a malformed vector. Callers decide whether to retry."""


class Embedder(Protocol):
    model: str

    async def embed(self, texts: Sequence[str], task: EmbedTask) -> list[list[float]]:
        """Returns one EMBEDDING_DIMENSIONS-long vector per input text, in input order."""
        ...
