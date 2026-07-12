"""Fill missing vocabulary examples / notes via Gemini (gap-only merge)."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import HTTPException, status
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.http_client import create_sync_client
from app.models.schemas.common import ExampleSentence, JlptLevel, PartOfSpeech
from app.models.schemas.vocab import (
    VocabEnrichmentOutput,
    VocabularyDefinitionOut,
    VocabularyOut,
)
from app.services.text_sanitize import clean_text
from app.services.vocab_service import vocab_service

_ENRICH_PROMPT = """你是一位日文單字老師，請為學習者補齊筆記中缺少的「例句」與「補充」。

你會收到：單字、發音、中文意思，以及目前是否已有例句／補充。
請回傳單一 VocabEnrichmentOutput JSON。

## 語言
- notes_zh、例句 chinese 使用繁體中文。
- 不要輸出英文。

## 欄位規則
- example_sentences：若 needs_examples=true，給 1–2 句短例句。
  每句只要 japanese（必填）與 chinese（建議）；reading 可選。
  不要填 english、highlight、acceptable_patterns。
- notes_zh：若 needs_notes=true，寫 1–3 句簡潔補充（用法／近義／助詞），總長勿超過 120 字。
- 若 needs_examples=false，example_sentences 回傳 []。
- 若 needs_notes=false，notes_zh 回傳 null。
- part_of_speech / jlpt_level：僅在需要且明顯可判斷時填。

## 禁止
- 不要改寫單字或既有中文意思。
- 不要寫長文或多餘欄位。

## JSON
- 只回傳可解析的短 JSON，不要 markdown。
- 字串內勿出現未跳脫換行。
"""


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


def _parse_enrichment_payload(raw: str | None) -> VocabEnrichmentOutput:
    payload = _normalize_json_payload(raw)
    try:
        return VocabEnrichmentOutput.model_validate_json(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"AI 回傳的 JSON 不完整或格式錯誤：{exc}") from exc


def _generate_enrichment(
    client: genai.Client,
    contents: list[object],
    *,
    max_output_tokens: int,
) -> VocabEnrichmentOutput:
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=VocabEnrichmentOutput,
            temperature=0.2,
            max_output_tokens=max_output_tokens,
        ),
    )
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, VocabEnrichmentOutput):
        return parsed
    if isinstance(parsed, dict):
        return VocabEnrichmentOutput.model_validate(parsed)
    return _parse_enrichment_payload(response.text)


def _raise_gemini_http_error(exc: Exception) -> None:
    message = str(exc)
    if "429" in message or "RESOURCE_EXHAUSTED" in message:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Gemini API 額度已用完。請到 Google AI Studio 充值或更換 API key，"
                "之後再按「AI 補充」。"
            ),
        ) from exc
    if (
        "JSON" in message
        or "Unterminated string" in message
        or "EOF while parsing" in message
        or "json_invalid" in message
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 補充失敗：回傳內容過長被截斷，請再試一次。",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"AI 補充失敗：{message}",
    ) from exc


class VocabEnrichmentService:
    def preview_enrich(self, vocabulary_id: UUID) -> VocabularyOut:
        """Generate gap-fill draft without writing to DB (user confirms in modal)."""
        current = vocab_service.get_vocab(vocabulary_id)
        if not current.definitions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="此單字尚無釋義，無法補充。",
            )

        primary = current.definitions[0]
        needs_examples = len(primary.example_sentences or []) == 0
        needs_notes = not (primary.notes_zh or "").strip()
        needs_pos = primary.part_of_speech == PartOfSpeech.OTHER
        needs_jlpt = current.jlpt_level == JlptLevel.UNKNOWN

        if not needs_examples and not needs_notes and not needs_pos and not needs_jlpt:
            return current

        payload = {
            "word": current.word,
            "reading": current.reading,
            "meaning_zh": primary.meaning_zh,
            "jlpt_level": current.jlpt_level.value
            if isinstance(current.jlpt_level, JlptLevel)
            else current.jlpt_level,
            "part_of_speech": primary.part_of_speech.value
            if isinstance(primary.part_of_speech, PartOfSpeech)
            else primary.part_of_speech,
            "needs_examples": needs_examples,
            "needs_notes": needs_notes,
            "needs_pos": needs_pos,
            "needs_jlpt": needs_jlpt,
            "existing_examples_count": len(primary.example_sentences or []),
            "existing_notes_zh": primary.notes_zh,
        }
        contents: list[object] = [
            json.dumps(payload, ensure_ascii=False),
            "Return a single VocabEnrichmentOutput JSON object. Fill only requested gaps. Keep it short.",
            _ENRICH_PROMPT,
        ]

        client = _get_client()
        try:
            enriched: VocabEnrichmentOutput | None = None
            last_error: Exception | None = None
            for max_tokens in (8192, 12288):
                try:
                    enriched = _generate_enrichment(
                        client, contents, max_output_tokens=max_tokens
                    )
                    break
                except ValueError as exc:
                    last_error = exc
                    continue
            if enriched is None:
                raise ValueError(str(last_error or "AI 補充失敗"))
        except HTTPException:
            raise
        except Exception as exc:
            _raise_gemini_http_error(exc)

        new_examples = list(primary.example_sentences or [])
        if needs_examples and enriched.example_sentences:
            cleaned = [
                ExampleSentence(
                    japanese=clean_text(ex.japanese) or "",
                    reading=clean_text(ex.reading),
                    chinese=clean_text(ex.chinese),
                    english=None,
                )
                for ex in enriched.example_sentences
                if (ex.japanese or "").strip()
            ]
            if cleaned:
                new_examples = cleaned

        new_notes = primary.notes_zh
        if needs_notes and (enriched.notes_zh or "").strip():
            new_notes = clean_text(enriched.notes_zh)

        new_pos = primary.part_of_speech
        if needs_pos and enriched.part_of_speech and enriched.part_of_speech != PartOfSpeech.OTHER:
            new_pos = enriched.part_of_speech

        new_jlpt = current.jlpt_level
        if needs_jlpt and enriched.jlpt_level and enriched.jlpt_level != JlptLevel.UNKNOWN:
            new_jlpt = enriched.jlpt_level

        merged_primary = VocabularyDefinitionOut(
            id=primary.id,
            sort_order=primary.sort_order,
            part_of_speech=new_pos,
            meaning_zh=primary.meaning_zh,
            meaning_en=primary.meaning_en,
            example_sentences=new_examples,
            notes_zh=new_notes,
        )
        rest = current.definitions[1:]
        return VocabularyOut(
            id=current.id,
            word=current.word,
            reading=current.reading,
            jlpt_level=new_jlpt,
            definitions=[merged_primary, *rest],
        )


vocab_enrichment_service = VocabEnrichmentService()
