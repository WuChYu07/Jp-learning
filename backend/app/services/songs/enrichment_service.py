"""Gemini enrichment for song lyric lines (grammar + cultural notes)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import HTTPException, status
from google.genai import types

from app.core.config import settings
from app.services.gemini_client import is_quota_error, run_with_key_failover

logger = logging.getLogger(__name__)

_ENRICH_SYSTEM = """You are a Japanese teacher for Traditional Chinese speakers.
You explain song lyrics line by line for language learning.

For each lyric line, return:
- grammar_zh: concise Traditional Chinese explanation of noteworthy grammar / particles / conjugations / set phrases in THIS line. If the line is mostly English or trivial, still give a short note.
- note_zh: optional cultural / literary / wordplay / intertextual tip (e.g. 「君が綺麗だ」 echoing 夏目漱石「月が綺麗です」). Omit or use empty string when you are not confident.
- jlpt_hints: optional short strings like "N3:〜ている" (0–2 items).

Rules:
- Write ALL explanations in Traditional Chinese (Taiwan).
- Do NOT invent grammar that is not in the line.
- Prefer accuracy over cleverness; leave note_zh empty when unsure.
- Return ONLY valid JSON.
"""

_ENRICH_USER = """Song: {title} — {artist}

Return JSON:
{{
  "lines": [
    {{
      "line_no": <int>,
      "grammar_zh": "<Traditional Chinese>",
      "note_zh": "<Traditional Chinese or empty>",
      "jlpt_hints": ["N3:…"]
    }}
  ]
}}

Lines to analyze:
{payload}
"""

_TRANSLATE_SYSTEM = """You translate Japanese song lyrics into Traditional Chinese (Taiwan).
Return ONLY valid JSON: {{"lines":[{{"line_no":1,"text_zh":"…"}}]}}
Keep line_no aligned. Be natural and lyrical but faithful. Do not add commentary.
"""


class SongEnrichmentService:
    BATCH = 12

    def enrich_lines(
        self,
        *,
        title: str,
        artist: str,
        lines: list[dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:
        """Return map line_no -> {grammar_zh, note_zh, jlpt_hints}."""
        result: dict[int, dict[str, Any]] = {}
        for i in range(0, len(lines), self.BATCH):
            batch = lines[i : i + self.BATCH]
            payload = "\n".join(
                f"{ln['line_no']}. JA: {ln.get('text_ja') or ''}\n"
                f"   ZH: {ln.get('text_zh') or '(none)'}"
                for ln in batch
            )
            data = self._gemini_json(
                _ENRICH_SYSTEM,
                _ENRICH_USER.format(title=title, artist=artist, payload=payload),
                max_tokens=4096,
                temperature=0.4,
            )
            for item in data.get("lines") or []:
                try:
                    no = int(item.get("line_no"))
                except (TypeError, ValueError):
                    continue
                hints = item.get("jlpt_hints") or []
                if not isinstance(hints, list):
                    hints = []
                result[no] = {
                    "grammar_zh": str(item.get("grammar_zh") or "").strip() or None,
                    "note_zh": str(item.get("note_zh") or "").strip() or None,
                    "jlpt_hints": [str(h) for h in hints if h][:3],
                }
        return result

    def translate_missing_zh(
        self,
        lines: list[dict[str, Any]],
    ) -> dict[int, str]:
        """AI-translate lines that lack text_zh. Returns line_no -> text_zh."""
        need = [ln for ln in lines if not (ln.get("text_zh") or "").strip()]
        if not need:
            return {}
        out: dict[int, str] = {}
        for i in range(0, len(need), self.BATCH):
            batch = need[i : i + self.BATCH]
            payload = "\n".join(f"{ln['line_no']}. {ln.get('text_ja') or ''}" for ln in batch)
            data = self._gemini_json(
                _TRANSLATE_SYSTEM,
                f"Translate these Japanese lyric lines:\n{payload}",
                max_tokens=3072,
                temperature=0.3,
            )
            for item in data.get("lines") or []:
                try:
                    no = int(item.get("line_no"))
                except (TypeError, ValueError):
                    continue
                zh = str(item.get("text_zh") or "").strip()
                if zh:
                    out[no] = zh
        return out

    def _gemini_json(
        self,
        system: str,
        user_msg: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.4,
    ) -> dict:
        try:
            response = run_with_key_failover(
                lambda client: client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=[system, user_msg],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                )
            )
        except Exception as exc:
            if is_quota_error(exc):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Gemini API 額度已用完，請稍後再試或設定備援 key。",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gemini API error: {exc}",
            ) from exc

        raw = response.text or ""
        try:
            # Tolerate accidental markdown fences
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)
            parsed = json.loads(cleaned)
            if not isinstance(parsed, dict):
                raise ValueError("not an object")
            return parsed
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gemini returned invalid JSON: {raw[:200]}",
            ) from exc


song_enrichment_service = SongEnrichmentService()
