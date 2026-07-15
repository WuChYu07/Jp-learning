"""Batch JLPT level suggestions for vocab / grammar with unknown level."""

from __future__ import annotations

import json
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from supabase import Client

from app.core.config import settings
from app.core.http_client import create_sync_client
from app.db.supabase import get_supabase_client
from app.models.schemas.common import JlptLevel
from app.models.schemas.grammar import coerce_grammar_jlpt
from app.models.schemas.jlpt import (
    JlptApplyItem,
    JlptApplyResponse,
    JlptPreviewResponse,
    JlptSuggestionItem,
)

_VOCAB_LEVELS = {level.value for level in JlptLevel if level != JlptLevel.UNKNOWN}

_PROMPT = """你是一位 JLPT 分級顧問。請為下列「目前等級為 unknown」的項目建議合適的 JLPT 等級。

## 規則
- 單字（vocab）：只能填 N5、N4、N3、N2、N1 其一（不要填 unknown，不要組合等級）。
- 文法（grammar）：可填 N5–N1 單一等級；若確實橫跨兩級可填如 N3/N2（斜線、無空格）。
- 依常見教科書／JLPT 出題範圍保守判斷；不確定時偏向較容易的那一級。
- 必須回傳每個輸入的 id，不可杜撰新 id。

## 輸出
只回傳可解析的 JSON，格式：
{"items":[{"id":"<uuid>","suggested_jlpt":"N3","confidence":0.8}]}
不要 markdown。
"""


class _AiItem(BaseModel):
    id: str
    suggested_jlpt: str
    confidence: float | None = None


class _AiBatch(BaseModel):
    items: list[_AiItem] = Field(default_factory=list)


def _get_client() -> genai.Client:
    return genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(httpx_client=create_sync_client()),
    )


def _normalize_json_payload(raw: str | None) -> str:
    if not raw:
        raise ValueError("Gemini returned an empty response")
    text = raw.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return text


def _parse_batch(raw: str | None) -> _AiBatch:
    payload = _normalize_json_payload(raw)
    try:
        return _AiBatch.model_validate_json(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"AI JSON invalid: {exc}") from exc


def _raise_gemini_http_error(exc: Exception) -> None:
    message = str(exc)
    if "429" in message or "RESOURCE_EXHAUSTED" in message:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Gemini API 額度已用完，請稍後再試或更換 API key。",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"JLPT 建議失敗：{exc}",
    ) from exc


def _normalize_vocab_jlpt(raw: str) -> str | None:
    upper = raw.strip().upper().replace(" ", "")
    if upper in _VOCAB_LEVELS:
        return upper
    # Take first valid part if model returns N3/N2 for vocab
    for part in upper.replace("、", "/").split("/"):
        token = part.strip()
        if token in _VOCAB_LEVELS:
            return token
    return None


def _normalize_grammar_jlpt(raw: str) -> str | None:
    coerced = coerce_grammar_jlpt(raw)
    if coerced == "unknown":
        return None
    return coerced


class JlptEnrichmentService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def preview(
        self,
        entity: Literal["vocab", "grammar", "both"] = "both",
        limit: int = 20,
    ) -> JlptPreviewResponse:
        remaining = self._count_unknown(entity)
        candidates = self._fetch_unknown_candidates(entity, limit)
        if not candidates:
            return JlptPreviewResponse(items=[], remaining_unknown=remaining)

        suggestions_map = self._suggest_levels(candidates)
        items: list[JlptSuggestionItem] = []
        for cand in candidates:
            suggested = suggestions_map.get(cand["id"])
            if not suggested:
                continue
            if cand["entity"] == "vocab":
                level = _normalize_vocab_jlpt(suggested)
            else:
                level = _normalize_grammar_jlpt(suggested)
            if not level:
                continue
            items.append(
                JlptSuggestionItem(
                    entity=cand["entity"],
                    id=UUID(cand["id"]),
                    label=cand["label"],
                    detail=cand.get("detail"),
                    current="unknown",
                    suggested_jlpt=level,
                )
            )

        return JlptPreviewResponse(items=items, remaining_unknown=remaining)

    def apply(self, items: list[JlptApplyItem]) -> JlptApplyResponse:
        updated = 0
        for item in items:
            table = "vocabularies" if item.entity == "vocab" else "grammars"
            if item.entity == "vocab":
                level = _normalize_vocab_jlpt(item.jlpt_level)
            else:
                level = _normalize_grammar_jlpt(item.jlpt_level)
            if not level:
                continue

            existing = (
                self.db.table(table)
                .select("id")
                .eq("id", str(item.id))
                .eq("jlpt_level", "unknown")
                .limit(1)
                .execute()
            )
            if not existing.data:
                continue

            self.db.table(table).update({"jlpt_level": level}).eq(
                "id", str(item.id)
            ).eq("jlpt_level", "unknown").execute()
            updated += 1
        return JlptApplyResponse(updated=updated)

    def _count_unknown(self, entity: Literal["vocab", "grammar", "both"]) -> int:
        total = 0
        if entity in ("vocab", "both"):
            total += self._count_table("vocabularies")
        if entity in ("grammar", "both"):
            total += self._count_table("grammars")
        return total

    def _count_table(self, table: str) -> int:
        result = (
            self.db.table(table)
            .select("id", count="exact")
            .eq("jlpt_level", "unknown")
            .limit(1)
            .execute()
        )
        return int(result.count or 0)

    def _fetch_unknown_candidates(
        self,
        entity: Literal["vocab", "grammar", "both"],
        limit: int,
    ) -> list[dict]:
        if entity == "vocab":
            return self._fetch_unknown_vocab(limit)
        if entity == "grammar":
            return self._fetch_unknown_grammar(limit)

        vocab_limit = (limit + 1) // 2
        grammar_limit = limit - vocab_limit
        vocab = self._fetch_unknown_vocab(vocab_limit)
        grammar = self._fetch_unknown_grammar(grammar_limit)
        # If one side is short, fill with the other
        if len(vocab) < vocab_limit:
            grammar = self._fetch_unknown_grammar(limit - len(vocab))
        elif len(grammar) < grammar_limit:
            vocab = self._fetch_unknown_vocab(limit - len(grammar))
        return vocab + grammar

    def _fetch_unknown_vocab(self, limit: int) -> list[dict]:
        if limit <= 0:
            return []
        rows = (
            self.db.table("vocabularies")
            .select("id, word, reading")
            .eq("jlpt_level", "unknown")
            .order("word")
            .limit(limit * 3)
            .execute()
        ).data or []
        if not rows:
            return []

        # Skip junk Notion rows so Gemini quota goes to real words
        rows = [
            row
            for row in rows
            if (row.get("word") or "").strip() not in {"", "-", "ー", "－"}
        ][:limit]
        if not rows:
            return []

        ids = [row["id"] for row in rows]
        defs = (
            self.db.table("vocabulary_definitions")
            .select("vocabulary_id, sort_order, meaning_zh")
            .in_("vocabulary_id", ids)
            .order("sort_order")
            .execute()
        ).data or []
        first_meaning: dict[str, str] = {}
        for d in defs:
            vid = d["vocabulary_id"]
            if vid not in first_meaning and d.get("meaning_zh"):
                first_meaning[vid] = d["meaning_zh"]

        out: list[dict] = []
        for row in rows:
            meaning = first_meaning.get(row["id"])
            detail_parts = [p for p in [row.get("reading"), meaning] if p]
            out.append(
                {
                    "entity": "vocab",
                    "id": row["id"],
                    "label": row["word"],
                    "detail": "／".join(detail_parts) if detail_parts else None,
                    "prompt_line": (
                        f"- id={row['id']} | vocab | {row['word']}"
                        f" | reading={row.get('reading') or ''}"
                        f" | meaning={meaning or ''}"
                    ),
                }
            )
        return out

    def _fetch_unknown_grammar(self, limit: int) -> list[dict]:
        if limit <= 0:
            return []
        rows = (
            self.db.table("grammars")
            .select("id, grammar_point")
            .eq("jlpt_level", "unknown")
            .order("grammar_point")
            .limit(limit)
            .execute()
        ).data or []
        if not rows:
            return []

        ids = [row["id"] for row in rows]
        usages = (
            self.db.table("grammar_usages")
            .select("grammar_id, sort_order, semantic_concept, meaning_zh")
            .in_("grammar_id", ids)
            .order("sort_order")
            .execute()
        ).data or []
        first: dict[str, str] = {}
        for u in usages:
            gid = u["grammar_id"]
            if gid in first:
                continue
            bits = [b for b in [u.get("semantic_concept"), u.get("meaning_zh")] if b]
            if bits:
                first[gid] = " — ".join(bits)

        out: list[dict] = []
        for row in rows:
            meaning = first.get(row["id"])
            out.append(
                {
                    "entity": "grammar",
                    "id": row["id"],
                    "label": row["grammar_point"],
                    "detail": meaning,
                    "prompt_line": (
                        f"- id={row['id']} | grammar | {row['grammar_point']}"
                        f" | meaning={meaning or ''}"
                    ),
                }
            )
        return out

    def _suggest_levels(self, candidates: list[dict]) -> dict[str, str]:
        lines = "\n".join(c["prompt_line"] for c in candidates)
        prompt = f"{_PROMPT}\n\n## 項目\n{lines}\n"
        try:
            client = _get_client()
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_AiBatch,
                    temperature=0.1,
                    max_output_tokens=8192,
                ),
            )
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, _AiBatch):
                batch = parsed
            elif isinstance(parsed, dict):
                batch = _AiBatch.model_validate(parsed)
            else:
                batch = _parse_batch(response.text)
        except HTTPException:
            raise
        except Exception as exc:
            _raise_gemini_http_error(exc)

        allowed = {c["id"] for c in candidates}
        out: dict[str, str] = {}
        for item in batch.items:
            if item.id in allowed and item.suggested_jlpt:
                out[item.id] = item.suggested_jlpt
        return out


jlpt_enrichment_service = JlptEnrichmentService()
