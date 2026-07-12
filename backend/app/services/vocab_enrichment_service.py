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
- 不要輸出英文說明；例句不要填 english。

## 欄位規則
- example_sentences：若輸入標示 needs_examples=true，請給 1–2 句自然例句。
  每句 japanese 必填；盡量附 chinese；可選 reading（平假名）。
  例句應能自然用到該單字（活用形亦可）。
- notes_zh：若輸入標示 needs_notes=true，請寫簡潔補充（用法時機、與近義詞差別、助詞搭配等），風格像學習筆記，不要太長。
- 若 needs_examples=false，example_sentences 請回傳空陣列。
- 若 needs_notes=false，notes_zh 請回傳 null。
- part_of_speech：可選，僅在明顯可判斷時填（noun/verb/i_adjective/na_adjective/adverb/particle/counter/expression/other）。
- jlpt_level：可選，N5–N1 或 unknown。

## 禁止
- 不要改寫單字本身或發音。
- 不要改寫既有中文意思。
- 不要編造罕見或錯誤用法。

## JSON
- 只回傳可解析的 JSON，不要 markdown 圍欄。
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
            "existing_examples": [
                ex.model_dump(mode="json") for ex in (primary.example_sentences or [])
            ],
            "existing_notes_zh": primary.notes_zh,
        }
        contents: list[object] = [
            json.dumps(payload, ensure_ascii=False),
            "Return a single VocabEnrichmentOutput JSON object. Fill only requested gaps.",
            _ENRICH_PROMPT,
        ]

        client = _get_client()
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=VocabEnrichmentOutput,
                    temperature=0.2,
                    max_output_tokens=4096,
                ),
            )
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, VocabEnrichmentOutput):
                enriched = parsed
            elif isinstance(parsed, dict):
                enriched = VocabEnrichmentOutput.model_validate(parsed)
            else:
                enriched = _parse_enrichment_payload(response.text)
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
                    highlight=ex.highlight,
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
