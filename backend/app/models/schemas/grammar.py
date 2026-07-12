import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.schemas.common import (
    ExampleSentence,
    JlptLevel,
    MeaningBlock,
    SupplementaryBlock,
)

SyncChange = Literal["new", "updated", "unchanged"]
SyncStatus = Literal["synced", "needs_ai", "archived"]

_JLPT_PART = re.compile(r"^N[1-5]$")


def coerce_grammar_jlpt(value: object) -> str:
    """Accept N5–N1, unknown, or combined labels like N3/N2."""
    if isinstance(value, JlptLevel):
        return value.value
    if value is None or value == "":
        return "unknown"
    raw = str(value).strip()
    if raw.lower() == "unknown":
        return "unknown"

    parts = re.split(r"[/、,，\s]+", raw.upper())
    levels: list[str] = []
    for part in parts:
        token = part.strip()
        if _JLPT_PART.match(token) and token not in levels:
            levels.append(token)
    if levels:
        return "/".join(levels)

    upper = raw.upper()
    if _JLPT_PART.match(upper):
        return upper
    return "unknown"


class GrammarUsageBase(BaseModel):
    semantic_concept: str
    connection_rule: str
    meaning_zh: str | None = None
    meaning_en: str | None = None
    meaning_blocks: list[MeaningBlock] = Field(default_factory=list)
    example_sentences: list[ExampleSentence] = Field(default_factory=list)


class GrammarUsageWrite(BaseModel):
    """Core fields for manual create/edit forms."""

    semantic_concept: str
    connection_rule: str
    meaning_zh: str | None = None
    example_sentences: list[ExampleSentence] = Field(default_factory=list)


class GrammarWriteInput(BaseModel):
    """Manual create/update payload — Chinese-first core fields."""

    grammar_point: str
    jlpt_level: str = "unknown"
    usages: list[GrammarUsageWrite] = Field(min_length=1)

    @field_validator("jlpt_level", mode="before")
    @classmethod
    def normalize_jlpt(cls, value: object) -> str:
        return coerce_grammar_jlpt(value)

    @field_validator("grammar_point")
    @classmethod
    def require_grammar_point(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("grammar_point is required")
        return cleaned


class GrammarItemInput(BaseModel):
    """Gemini / Notion output shape — one grammar point, many usages."""

    grammar_point: str
    jlpt_level: str = "unknown"
    usages: list[GrammarUsageBase] = Field(min_length=1)
    image_urls: list[str] = Field(default_factory=list)
    notion_block_id: str | None = None
    notion_page_id: str | None = None
    source_content_hash: str | None = None
    block_ids: list[str] = Field(default_factory=list)
    sync_change: SyncChange | None = None

    @field_validator("jlpt_level", mode="before")
    @classmethod
    def normalize_jlpt(cls, value: object) -> str:
        return coerce_grammar_jlpt(value)


class GrammarEnrichmentOutput(BaseModel):
    """Gemini image-enrichment response — Chinese-only structured content."""

    grammar_point: str
    jlpt_level: str = "unknown"
    usages: list[GrammarUsageBase] = Field(min_length=1)
    supplementary_blocks: list[SupplementaryBlock] = Field(default_factory=list)

    @field_validator("jlpt_level", mode="before")
    @classmethod
    def normalize_jlpt(cls, value: object) -> str:
        return coerce_grammar_jlpt(value)


class GrammarUsageOut(GrammarUsageBase):
    id: UUID
    sort_order: int


class GrammarOut(BaseModel):
    id: UUID
    grammar_point: str
    jlpt_level: str
    usages: list[GrammarUsageOut]
    image_urls: list[str] = Field(default_factory=list)
    supplementary_blocks: list[SupplementaryBlock] = Field(default_factory=list)
    sync_status: SyncStatus = "synced"
    needs_enrichment: bool = False
    manual_edited: bool = False


class GrammarSummary(BaseModel):
    """Lightweight list row — no usages/images payload."""

    id: UUID
    grammar_point: str
    jlpt_level: str
    usage_count: int = 0
    image_count: int = 0
    sync_status: SyncStatus = "synced"
    needs_enrichment: bool = False
    manual_edited: bool = False
