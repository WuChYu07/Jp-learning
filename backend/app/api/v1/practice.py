"""AI practice endpoints: prompt → grade → history."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_effective_user_id
from app.services.practice_service import (
    PracticeDialogueOut,
    PracticeGradeOut,
    PracticeGradeRequest,
    PracticePromptOut,
    practice_service,
)

router = APIRouter()

PracticeMode = Literal["speak", "hint_translate"]
PracticeTopic = Literal["daily", "academic", "travel", "work", "random"]


class PracticeSessionRequest(BaseModel):
    mode: PracticeMode = "speak"
    topic: PracticeTopic = "random"


@router.post("/session", response_model=PracticePromptOut)
def create_practice_session(
    body: PracticeSessionRequest,
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
) -> PracticePromptOut:
    return practice_service.create_prompt(
        user_id=user_id,
        mode=body.mode,
        topic=body.topic,
    )


@router.post("/grade", response_model=PracticeGradeOut)
def grade_practice(
    body: PracticeGradeRequest,
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
) -> PracticeGradeOut:
    return practice_service.grade(user_id=user_id, body=body)


@router.get("/history", response_model=list[PracticeDialogueOut])
def practice_history(
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
    limit: int = Query(default=20, ge=1, le=50),
) -> list[PracticeDialogueOut]:
    return practice_service.list_recent(user_id=user_id, limit=limit)
