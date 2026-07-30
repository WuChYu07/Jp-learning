"""Gemini text embeddings for semantic similarity linking."""

from __future__ import annotations

import hashlib
import logging
import math
import re

from google.genai import types

from app.core.config import settings
from app.services.gemini_client import run_with_key_failover

logger = logging.getLogger(__name__)

_MAX_CHARS = 1800


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


def _dedupe_preserve_order(parts: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        if part not in seen:
            seen.add(part)
            unique.append(part)
    return unique


def build_grammar_sense_texts(
    grammar_point: str,
    usages: list[dict] | None = None,
    *,
    max_senses: int = 4,
) -> list[str]:
    """One embeddable text per usage ("sense"), so a grammar point with
    several distinct usages isn't reduced to a single averaged/diluted
    vector — a real match on one usage could otherwise be hidden by
    unrelated other usages pulling a combined vector away.

    Connection rules look alike across many grammar points (Vた＋…), which
    pollutes cosine similarity. Prefer semantic_concept / meaning_zh / blocks.
    Falls back to a single grammar-point-only text when no usage has any
    Chinese meaning content yet (e.g. image-only, not yet AI-enriched).
    """
    texts: list[str] = []
    for usage in usages or []:
        meaning_parts: list[str] = []
        for key in ("semantic_concept", "meaning_zh"):
            val = (usage.get(key) or "").strip()
            if val:
                meaning_parts.append(val)
        for block in usage.get("meaning_blocks") or []:
            if isinstance(block, dict):
                text = (block.get("text") or "").strip()
                if text:
                    meaning_parts.append(text)

        unique = _dedupe_preserve_order(meaning_parts)
        if not unique:
            continue
        core = "；".join(unique)
        parts = [f"日文文法語意：{core}", f"句型：{grammar_point}", core]
        texts.append(truncate_text("\n".join(parts)))
        if len(texts) >= max_senses:
            break

    if not texts:
        # Fallback when no usage has Chinese content — weaker signal
        texts = [truncate_text(f"日文文法句型：{grammar_point}")]
    return texts


def build_vocab_sense_texts(
    word: str,
    reading: str | None = None,
    definitions: list[dict] | None = None,
    *,
    max_senses: int = 4,
) -> list[str]:
    """One embeddable text per definition ("sense") — see build_grammar_sense_texts."""
    head = f"{word}（{reading}）" if reading else word

    texts: list[str] = []
    for definition in definitions or []:
        meaning = (definition.get("meaning_zh") or "").strip()
        if not meaning:
            continue
        parts = [f"日文單字語意：{meaning}", f"詞：{head}", meaning]
        texts.append(truncate_text("\n".join(parts)))
        if len(texts) >= max_senses:
            break

    if not texts:
        texts = [truncate_text(f"日文單字：{head}")]
    return texts


class EmbeddingService:
    def embed_text(self, text: str) -> list[float]:
        text = truncate_text(text)
        if not text:
            raise ValueError("Cannot embed empty text")

        dim = settings.EMBEDDING_DIM

        def _embed(client):
            try:
                return client.models.embed_content(
                    model=settings.GEMINI_EMBEDDING_MODEL,
                    contents=text,
                    config=types.EmbedContentConfig(
                        task_type="SEMANTIC_SIMILARITY",
                        output_dimensionality=dim,
                    ),
                )
            except Exception:
                # Fallback for older SDK / model param shapes
                return client.models.embed_content(
                    model=settings.GEMINI_EMBEDDING_MODEL,
                    contents=text,
                    config=types.EmbedContentConfig(
                        task_type="SEMANTIC_SIMILARITY",
                    ),
                )

        response = run_with_key_failover(_embed)

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
