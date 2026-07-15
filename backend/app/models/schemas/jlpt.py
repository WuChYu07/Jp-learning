"""Schemas for batch JLPT level suggestions."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

JlptEntity = Literal["vocab", "grammar"]
JlptPreviewEntity = Literal["vocab", "grammar", "both"]


class JlptPreviewRequest(BaseModel):
    entity: JlptPreviewEntity = "both"
    limit: int = Field(default=20, ge=1, le=40)


class JlptSuggestionItem(BaseModel):
    entity: JlptEntity
    id: UUID
    label: str
    detail: str | None = None
    current: str = "unknown"
    suggested_jlpt: str


class JlptPreviewResponse(BaseModel):
    items: list[JlptSuggestionItem]
    remaining_unknown: int


class JlptApplyItem(BaseModel):
    entity: JlptEntity
    id: UUID
    jlpt_level: str


class JlptApplyRequest(BaseModel):
    items: list[JlptApplyItem] = Field(default_factory=list, max_length=40)


class JlptApplyResponse(BaseModel):
    updated: int
