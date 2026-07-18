"""AI practice: free speak Q&A and hint-assisted Chinese→Japanese translation."""

from __future__ import annotations

import json
import logging
import random
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException, status
from google.genai import types
from pydantic import BaseModel, Field
from supabase import Client

from app.core.config import settings
from app.db.supabase import get_supabase_client
from app.services.gemini_client import is_quota_error, run_with_key_failover
from app.services.owner_service import ensure_owner_user

logger = logging.getLogger(__name__)

PracticeMode = Literal["speak", "hint_translate"]
PracticeTopic = Literal["daily", "academic", "travel", "work", "random"]


class PracticeHint(BaseModel):
    kind: Literal["vocab", "grammar"]
    label: str
    detail: str | None = None


class PracticePromptOut(BaseModel):
    mode: PracticeMode
    topic: str
    prompt_zh: str | None = None
    prompt_ja: str | None = None
    hints: list[PracticeHint] = Field(default_factory=list)


class PracticeGradeRequest(BaseModel):
    mode: PracticeMode
    topic: str | None = None
    prompt_zh: str | None = None
    prompt_ja: str | None = None
    user_answer: str
    hints: list[PracticeHint] = Field(default_factory=list)


class PracticeGradeOut(BaseModel):
    id: UUID
    score: int = Field(ge=1, le=5)
    feedback_zh: str
    model_answer: str | None = None


class PracticeDialogueOut(BaseModel):
    id: UUID
    mode: str
    topic: str | None
    prompt_zh: str | None
    prompt_ja: str | None
    user_answer: str
    score: int | None
    feedback_zh: str | None
    model_answer: str | None
    hints_json: list[Any] = Field(default_factory=list)
    created_at: str


_SPEAK_PROMPT = """You are a Japanese conversation tutor for a Traditional Chinese speaker.
Generate ONE question in Japanese for the learner to answer in Japanese.

Topic hint: {topic}
Return ONLY valid JSON:
{{
  "prompt_ja": "<the Japanese question>",
  "prompt_zh": "<Traditional Chinese translation of the question>"
}}
Keep the question natural and answerable in 1–3 sentences.
"""

_HINT_TRANSLATE_PROMPT = """You are a Japanese teacher. Create a Chinese→Japanese translation exercise.
Topic: {topic}
Optional hint vocabulary (prefer using some): {vocab_hints}
Optional hint grammar (prefer using some): {grammar_hints}

Return ONLY valid JSON:
{{
  "prompt_zh": "<Chinese sentence to translate into Japanese>",
  "hints": [
    {{"kind": "vocab"|"grammar", "label": "<word or grammar>", "detail": "<brief Traditional Chinese tip>"}}
  ]
}}
Provide 1–3 hints. The Chinese sentence should be everyday or lightly academic as topic suggests.
"""

_GRADE_SPEAK = """Grade the learner's Japanese answer to a Japanese question.
Return ONLY valid JSON:
{
  "score": <1-5 integer>,
  "feedback_zh": "<2-3 sentences Traditional Chinese feedback>",
  "model_answer": "<a natural sample Japanese answer>"
}
Scoring: 5 natural/accurate, 4 minor issues, 3 understandable with errors, 2 partial, 1 wrong.
"""

_GRADE_HINT = """Grade the learner's Japanese translation of a Chinese sentence.
Hints were provided; using them well is good but not mandatory if the translation is natural.
Return ONLY valid JSON:
{
  "score": <1-5 integer>,
  "feedback_zh": "<2-3 sentences Traditional Chinese feedback>",
  "model_answer": "<natural Japanese translation>"
}
"""


class PracticeService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def create_prompt(
        self,
        *,
        user_id: str | None,
        mode: PracticeMode,
        topic: PracticeTopic = "random",
    ) -> PracticePromptOut:
        self._check_daily_limit(user_id)
        resolved_topic = self._resolve_topic(topic)
        if mode == "speak":
            return self._prompt_speak(resolved_topic)
        return self._prompt_hint_translate(resolved_topic)

    def grade(
        self,
        *,
        user_id: str | None,
        body: PracticeGradeRequest,
    ) -> PracticeGradeOut:
        if not body.user_answer.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Answer cannot be empty",
            )
        self._check_daily_limit(user_id)
        ensure_owner_user(self.db)
        owner = user_id or settings.SINGLETON_OWNER_ID

        if body.mode == "speak":
            system = _GRADE_SPEAK
            user_msg = (
                f"Question (JA): {body.prompt_ja or ''}\n"
                f"Question (ZH): {body.prompt_zh or ''}\n"
                f"Student answer: {body.user_answer}"
            )
        else:
            system = _GRADE_HINT
            hints = "; ".join(
                f"{h.kind}:{h.label}" + (f"({h.detail})" if h.detail else "")
                for h in body.hints
            )
            user_msg = (
                f"Chinese: {body.prompt_zh or ''}\n"
                f"Hints: {hints or '(none)'}\n"
                f"Student Japanese: {body.user_answer}"
            )

        data = self._gemini_json(system, user_msg)
        score = int(data.get("score") or 1)
        score = max(1, min(5, score))
        feedback = str(data.get("feedback_zh") or "請再試一次。")
        model_answer = data.get("model_answer")
        if model_answer is not None:
            model_answer = str(model_answer)

        row = {
            "user_id": owner,
            "mode": body.mode,
            "topic": body.topic,
            "prompt_zh": body.prompt_zh,
            "prompt_ja": body.prompt_ja,
            "user_answer": body.user_answer.strip(),
            "score": score,
            "feedback_zh": feedback,
            "model_answer": model_answer,
            "hints_json": [h.model_dump(mode="json") for h in body.hints],
        }
        try:
            inserted = self.db.table("practice_dialogues").insert(row).execute()
        except Exception as exc:
            logger.exception("practice_dialogues insert failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "無法寫入練習紀錄。請確認已執行 migrations/014_practice_dialogues.sql。"
                ),
            ) from exc

        data_row = (inserted.data or [None])[0]
        if not data_row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save practice dialogue",
            )
        return PracticeGradeOut(
            id=UUID(data_row["id"]),
            score=score,
            feedback_zh=feedback,
            model_answer=model_answer,
        )

    def list_recent(
        self, *, user_id: str | None, limit: int = 20
    ) -> list[PracticeDialogueOut]:
        owner = user_id or settings.SINGLETON_OWNER_ID
        try:
            rows = (
                self.db.table("practice_dialogues")
                .select("*")
                .eq("user_id", owner)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            ).data or []
        except Exception:
            logger.exception("practice_dialogues list failed")
            return []

        out: list[PracticeDialogueOut] = []
        for row in rows:
            hints = row.get("hints_json") or []
            if not isinstance(hints, list):
                hints = []
            out.append(
                PracticeDialogueOut(
                    id=UUID(row["id"]),
                    mode=row.get("mode") or "",
                    topic=row.get("topic"),
                    prompt_zh=row.get("prompt_zh"),
                    prompt_ja=row.get("prompt_ja"),
                    user_answer=row.get("user_answer") or "",
                    score=row.get("score"),
                    feedback_zh=row.get("feedback_zh"),
                    model_answer=row.get("model_answer"),
                    hints_json=hints,
                    created_at=str(row.get("created_at") or ""),
                )
            )
        return out

    def _prompt_speak(self, topic: str) -> PracticePromptOut:
        data = self._gemini_json(
            _SPEAK_PROMPT.format(topic=topic),
            "Generate one question now.",
        )
        return PracticePromptOut(
            mode="speak",
            topic=topic,
            prompt_ja=str(data.get("prompt_ja") or "").strip() or None,
            prompt_zh=str(data.get("prompt_zh") or "").strip() or None,
            hints=[],
        )

    def _prompt_hint_translate(self, topic: str) -> PracticePromptOut:
        vocab_hints, grammar_hints = self._sample_library_hints()
        data = self._gemini_json(
            _HINT_TRANSLATE_PROMPT.format(
                topic=topic,
                vocab_hints=", ".join(vocab_hints) or "(none)",
                grammar_hints=", ".join(grammar_hints) or "(none)",
            ),
            "Generate one exercise now.",
        )
        raw_hints = data.get("hints") or []
        hints: list[PracticeHint] = []
        if isinstance(raw_hints, list):
            for h in raw_hints[:3]:
                if not isinstance(h, dict):
                    continue
                kind = h.get("kind") if h.get("kind") in {"vocab", "grammar"} else "vocab"
                label = str(h.get("label") or "").strip()
                if not label:
                    continue
                hints.append(
                    PracticeHint(
                        kind=kind,  # type: ignore[arg-type]
                        label=label,
                        detail=(str(h["detail"]) if h.get("detail") else None),
                    )
                )
        # Fallback hints from library if model omitted them
        if not hints:
            for w in vocab_hints[:2]:
                hints.append(PracticeHint(kind="vocab", label=w))
            for g in grammar_hints[:1]:
                hints.append(PracticeHint(kind="grammar", label=g))

        return PracticePromptOut(
            mode="hint_translate",
            topic=topic,
            prompt_zh=str(data.get("prompt_zh") or "").strip() or None,
            prompt_ja=None,
            hints=hints,
        )

    def _sample_library_hints(self) -> tuple[list[str], list[str]]:
        vocab: list[str] = []
        grammar: list[str] = []
        try:
            vrows = (
                self.db.table("vocabularies")
                .select("word")
                .limit(80)
                .execute()
            ).data or []
            vocab = [r["word"] for r in vrows if r.get("word")]
            grows = (
                self.db.table("grammars")
                .select("grammar_point")
                .neq("sync_status", "archived")
                .limit(80)
                .execute()
            ).data or []
            grammar = [r["grammar_point"] for r in grows if r.get("grammar_point")]
        except Exception:
            logger.exception("failed to sample library hints")
        random.shuffle(vocab)
        random.shuffle(grammar)
        return vocab[:5], grammar[:5]

    def _resolve_topic(self, topic: PracticeTopic) -> str:
        if topic != "random":
            return topic
        return random.choice(["daily", "academic", "travel", "work"])

    def _check_daily_limit(self, user_id: str | None) -> None:
        owner = user_id or settings.SINGLETON_OWNER_ID
        since = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
        try:
            rows = (
                self.db.table("practice_dialogues")
                .select("id")
                .eq("user_id", owner)
                .gte("created_at", since)
                .execute()
            ).data or []
        except Exception:
            # Table missing → skip limit (grade will still fail clearly on insert)
            return
        # Each graded answer counts; leave headroom for prompt+grade pairs
        if len(rows) >= settings.DAILY_AI_REQUEST_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"今日 AI 練習已達上限（{settings.DAILY_AI_REQUEST_LIMIT}）。明天再試。",
            )

    def _gemini_json(self, system: str, user_msg: str) -> dict:
        try:
            response = run_with_key_failover(
                lambda client: client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=[system, user_msg],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.6,
                        max_output_tokens=1024,
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
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("not an object")
            return parsed
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gemini returned invalid JSON: {raw[:200]}",
            ) from exc


practice_service = PracticeService()
