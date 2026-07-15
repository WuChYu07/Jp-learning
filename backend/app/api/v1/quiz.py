"""Quiz endpoints: 4-choice vocab + translation grading."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from google.genai import types
from pydantic import BaseModel, Field

from app.api.deps import get_effective_user_id
from app.core.config import settings
from app.models.schemas.vocab import ExamAttemptCreate, ExamAttemptOut
from app.services.gemini_client import is_quota_error, run_with_key_failover
from app.services.quiz_service import quiz_service

router = APIRouter()


class ChoiceOptionOut(BaseModel):
    id: str
    text: str


class FourChoiceQuestionOut(BaseModel):
    question_id: str
    word: str
    reading: str | None
    prompt: str
    mode: str
    options: list[ChoiceOptionOut]
    correct_option_id: str


class QuizBatchOut(BaseModel):
    questions: list[FourChoiceQuestionOut]
    total_available: int


class TranslationPromptOut(BaseModel):
    question_id: str
    source_zh: str
    source_en: str | None
    hint_word: str
    hint_reading: str | None


class TranslationBatchOut(BaseModel):
    prompts: list[TranslationPromptOut]
    total_available: int


class TranslationGradeRequest(BaseModel):
    source_zh: str = Field(description="Original Chinese sentence")
    user_answer: str = Field(description="User's Japanese translation")
    hint_word: str | None = None


class TranslationGradeResponse(BaseModel):
    score: int = Field(ge=1, le=5, description="1=wrong, 5=perfect")
    feedback: str
    correction: str | None = None
    grammar_notes: str | None = None


@router.get("/vocab", response_model=QuizBatchOut)
def get_4choice_quiz(
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
    count: int = Query(default=10, ge=1, le=20),
) -> QuizBatchOut:
    batch = quiz_service.generate_4choice(count, user_id=user_id)
    return QuizBatchOut(
        questions=[
            FourChoiceQuestionOut(
                question_id=q.question_id,
                word=q.word,
                reading=q.reading,
                prompt=q.prompt,
                mode=q.mode,
                options=[ChoiceOptionOut(id=o.id, text=o.text) for o in q.options],
                correct_option_id=q.correct_option_id,
            )
            for q in batch.questions
        ],
        total_available=batch.total_available,
    )


@router.get("/grammar", response_model=QuizBatchOut)
def get_grammar_4choice_quiz(
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
    count: int = Query(default=10, ge=1, le=20),
) -> QuizBatchOut:
    batch = quiz_service.generate_grammar_4choice(count, user_id=user_id)
    return QuizBatchOut(
        questions=[
            FourChoiceQuestionOut(
                question_id=q.question_id,
                word=q.word,
                reading=q.reading,
                prompt=q.prompt,
                mode=q.mode,
                options=[ChoiceOptionOut(id=o.id, text=o.text) for o in q.options],
                correct_option_id=q.correct_option_id,
            )
            for q in batch.questions
        ],
        total_available=batch.total_available,
    )


@router.get("/translation/prompts", response_model=TranslationBatchOut)
def get_translation_prompts(
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
    count: int = Query(default=5, ge=1, le=10),
) -> TranslationBatchOut:
    batch = quiz_service.generate_translation_prompts(count, user_id=user_id)
    return TranslationBatchOut(
        prompts=[
            TranslationPromptOut(
                question_id=p.question_id,
                source_zh=p.source_zh,
                source_en=p.source_en,
                hint_word=p.hint_word,
                hint_reading=p.hint_reading,
            )
            for p in batch.prompts
        ],
        total_available=batch.total_available,
    )


@router.post("/results", response_model=ExamAttemptOut)
def submit_exam_result(
    body: ExamAttemptCreate,
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
) -> ExamAttemptOut:
    return quiz_service.save_exam_attempt(user_id, body)


_GRADE_PROMPT = """You are a strict but encouraging Japanese language teacher grading a student's translation.

The student was given a Chinese sentence and asked to translate it into Japanese.

Evaluate their answer and return ONLY valid JSON matching this schema:
{
  "score": <integer 1-5>,
  "feedback": "<2-3 sentence evaluation in Traditional Chinese>",
  "correction": "<correct Japanese translation if score < 4, else null>",
  "grammar_notes": "<brief grammar note in Traditional Chinese if relevant, else null>"
}

Scoring guide:
- 5: Perfect or near-perfect, natural Japanese
- 4: Minor issues but meaning is clear and grammar is mostly correct
- 3: Understandable but has noticeable grammar/vocabulary errors
- 2: Partially correct but significant errors affect meaning
- 1: Incorrect or incomprehensible
"""


@router.post("/translation/grade", response_model=TranslationGradeResponse)
def grade_translation(body: TranslationGradeRequest) -> TranslationGradeResponse:
    if not body.user_answer.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Answer cannot be empty",
        )

    user_prompt = f"""Chinese sentence: {body.source_zh}
Student's Japanese translation: {body.user_answer}"""

    if body.hint_word:
        user_prompt += f"\nTarget vocabulary: {body.hint_word}"

    try:
        response = run_with_key_failover(
            lambda client: client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[_GRADE_PROMPT, user_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                    max_output_tokens=1024,
                ),
            )
        )
    except Exception as exc:
        if is_quota_error(exc):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Gemini API 額度已用完（所有 key 皆無法使用）。"
                    "請設定 GEMINI_API_KEYS 備援 key 後再試。"
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API error: {exc}",
        ) from exc

    raw = response.text
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini returned empty response",
        )

    try:
        data = json.loads(raw)
        return TranslationGradeResponse(**data)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini returned invalid JSON: {raw[:200]}",
        ) from exc
