"""Gemini text embeddings for semantic similarity linking."""

from __future__ import annotations

import hashlib
import logging
import math
import re

from google import genai
from google.genai import types

from app.core.config import settings
from app.core.http_client import create_sync_client

logger = logging.getLogger(__name__)

_MAX_CHARS = 1800


def _get_client() -> genai.Client:
    return genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(httpx_client=create_sync_client()),
    )


def content_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def l2_normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def truncate_text(text: str, max_chars: int = _MAX_CHARS) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def build_grammar_source_text(
    grammar_point: str,
    usages: list[dict] | None = None,
) -> str:
    """Compose embedding text focused on Chinese meaning (no JLPT, no 接續規則).

    Connection rules look alike across many grammar points (Vた＋…), which
    pollutes cosine similarity. Prefer semantic_concept / meaning_zh / blocks.
    """
    meaning_parts: list[str] = []
    for usage in usages or []:
        for key in ("semantic_concept", "meaning_zh"):
            val = (usage.get(key) or "").strip()
            if val:
                meaning_parts.append(val)
        for block in usage.get("meaning_blocks") or []:
            if isinstance(block, dict):
                text = (block.get("text") or "").strip()
                if text:
                    meaning_parts.append(text)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for part in meaning_parts:
        if part not in seen:
            seen.add(part)
            unique.append(part)

    if unique:
        # Repeat core meaning to weight semantics over the pattern title
        core = "；".join(unique[:4])
        parts = [
            f"日文文法語意：{core}",
            f"句型：{grammar_point}",
            core,
        ]
    else:
        # Fallback when usages lack Chinese — weaker signal
        parts = [f"日文文法句型：{grammar_point}"]
    return truncate_text("\n".join(parts))


def build_vocab_source_text(
    word: str,
    reading: str | None = None,
    definitions: list[dict] | None = None,
) -> str:
    """Compose embedding text focused on Chinese glosses (no JLPT)."""
    meanings: list[str] = []
    for definition in definitions or []:
        meaning = (definition.get("meaning_zh") or "").strip()
        if meaning:
            meanings.append(meaning)

    head = word
    if reading:
        head = f"{word}（{reading}）"

    if meanings:
        gloss = "；".join(meanings[:4])
        parts = [f"日文單字語意：{gloss}", f"詞：{head}", gloss]
    else:
        parts = [f"日文單字：{head}"]
    return truncate_text("\n".join(parts))


class EmbeddingService:
    def embed_text(self, text: str) -> list[float]:
        text = truncate_text(text)
        if not text:
            raise ValueError("Cannot embed empty text")

        client = _get_client()
        dim = settings.EMBEDDING_DIM
        try:
            response = client.models.embed_content(
                model=settings.GEMINI_EMBEDDING_MODEL,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="SEMANTIC_SIMILARITY",
                    output_dimensionality=dim,
                ),
            )
        except Exception:
            # Fallback for older SDK / model param shapes
            response = client.models.embed_content(
                model=settings.GEMINI_EMBEDDING_MODEL,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="SEMANTIC_SIMILARITY",
                ),
            )

        values: list[float] | None = None
        embeddings = getattr(response, "embeddings", None)
        if embeddings:
            first = embeddings[0]
            values = list(getattr(first, "values", None) or [])
        if not values and hasattr(response, "embedding"):
            values = list(getattr(response.embedding, "values", None) or [])

        if not values:
            raise RuntimeError("Embedding API returned empty vector")

        if len(values) > dim:
            values = values[:dim]
        elif len(values) < dim:
            values = values + [0.0] * (dim - len(values))

        return l2_normalize(values)


embedding_service = EmbeddingService()
