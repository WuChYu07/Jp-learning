import json
from typing import Literal

from fastapi import HTTPException, status
from google.genai import types

from app.core.config import settings
from app.models.schemas.ingestion import IngestionParseResult
from app.services import local_pdf_parser
from app.services.gemini_client import is_quota_error, run_with_key_failover
from app.services.hash_service import extract_pdf_text

IngestionFocus = Literal["vocabulary", "grammar", "both"]

_BASE_PROMPT = """You are a Japanese language expert parsing study materials.

CRITICAL rules:
- Japanese has one-to-many meanings/usages.
- Return ONLY valid JSON matching the schema. No markdown fences.
- Use jlpt_level: N5, N4, N3, N2, N1, or unknown.
- part_of_speech must be one of: noun, verb, i_adjective, na_adjective, adverb, particle, counter, expression, other.
"""

_FOCUS_PROMPTS: dict[IngestionFocus, str] = {
    "vocabulary": _BASE_PROMPT
    + """
Extract VOCABULARY ONLY (単語): kanji/kana, reading, part_of_speech, Chinese meaning, example sentences.
Each word MUST have a `definitions` array (at least one).
Set `grammars` to [].
If a row has 平仮名/漢字/中国語 format, map reading→word forms correctly.
""",
    "grammar": _BASE_PROMPT
    + """
Extract GRAMMAR ONLY (文法): patterns, connection rules, semantic concepts, example sentences.
Each grammar point MUST have a `usages` array (at least one).
Set `vocabularies` to [].
""",
    "both": _BASE_PROMPT
    + """
Extract vocabulary (definitions array) and grammar (usages array).
If nothing is found for a category, return an empty array for it.
""",
}

_CHUNK_CHAR_LIMIT = 12_000


def _chunk_text(text: str, max_chars: int = _CHUNK_CHAR_LIMIT) -> list[str]:
    lines = text.splitlines()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1
        if current and current_len + line_len > max_chars:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len

    if current:
        chunks.append("\n".join(current))
    return chunks or [text]


def _parse_once(contents: list, focus: IngestionFocus) -> IngestionParseResult:
    try:
        response = run_with_key_failover(
            lambda client: client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=IngestionParseResult,
                    temperature=0.2,
                    max_output_tokens=8192,
                ),
            )
        )
    except Exception as exc:
        if is_quota_error(exc):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Gemini API 額度已用完（所有 key 皆無法使用）。"
                    "請在 .env / Render 設定 GEMINI_API_KEYS 備援 key。"
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API error: {exc}",
        ) from exc

    raw_text = response.text
    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini returned an empty response",
        )

    try:
        return IngestionParseResult.model_validate(json.loads(raw_text))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini returned invalid JSON",
        ) from exc


def _merge_results(results: list[IngestionParseResult]) -> IngestionParseResult:
    vocabularies = []
    grammars = []
    seen_vocab: set[tuple[str, str | None]] = set()
    seen_grammar: set[str] = set()

    for result in results:
        for item in result.vocabularies:
            key = (item.word.strip(), (item.reading or "").strip() or None)
            if key in seen_vocab:
                continue
            seen_vocab.add(key)
            vocabularies.append(item)

        for item in result.grammars:
            key = item.grammar_point.strip()
            if key in seen_grammar:
                continue
            seen_grammar.add(key)
            grammars.append(item)

    return IngestionParseResult(vocabularies=vocabularies, grammars=grammars)


def parse_content(
    file_bytes: bytes,
    mime_type: str,
    focus: IngestionFocus = "both",
) -> IngestionParseResult:
    if mime_type == "text/plain":
        text = file_bytes.decode("utf-8", errors="replace").strip()
        return _parse_text_with_gemini(text, focus)

    if mime_type == "application/pdf":
        text = extract_pdf_text(file_bytes).strip()
        if len(text) >= 100:
            local = _parse_locally(text, focus)
            if local.vocabularies or local.grammars:
                return local

    return _parse_with_gemini(file_bytes, mime_type, focus)


def _parse_text_with_gemini(text: str, focus: IngestionFocus) -> IngestionParseResult:
    prompt = _FOCUS_PROMPTS[focus]
    chunks = _chunk_text(text)
    results = [
        _parse_once(
            [f"Study notes (part {i + 1}/{len(chunks)}):\n\n{chunk}", prompt],
            focus,
        )
        for i, chunk in enumerate(chunks)
    ]
    return _merge_results(results)


def _parse_locally(text: str, focus: IngestionFocus) -> IngestionParseResult:
    if focus == "vocabulary":
        return local_pdf_parser.parse_vocabulary_pdf(text)
    if focus == "grammar":
        return local_pdf_parser.parse_grammar_pdf(text)

    vocab = local_pdf_parser.parse_vocabulary_pdf(text)
    grammar = local_pdf_parser.parse_grammar_pdf(text)
    return IngestionParseResult(
        vocabularies=vocab.vocabularies,
        grammars=grammar.grammars,
    )


def _parse_with_gemini(
    file_bytes: bytes,
    mime_type: str,
    focus: IngestionFocus,
) -> IngestionParseResult:
    prompt = _FOCUS_PROMPTS[focus]

    if mime_type == "application/pdf":
        text = extract_pdf_text(file_bytes).strip()
        if len(text) >= 100:
            chunks = _chunk_text(text)
            results = [
                _parse_once(
                    [f"Study material (part {index + 1}/{len(chunks)}):\n\n{chunk}", prompt],
                    focus,
                )
                for index, chunk in enumerate(chunks)
            ]
            return _merge_results(results)

    file_part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
    return _parse_once([file_part, prompt], focus)
