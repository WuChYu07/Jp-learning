from typing import Literal

from pydantic import BaseModel, Field

from app.models.schemas.ingestion import IngestionParseResult

NotionFocus = Literal["vocabulary", "grammar", "both"]


class NotionSyncRequest(BaseModel):
    focus: NotionFocus = "both"
    page_id: str | None = None
    upload_images: bool = True


class NotionPageSource(BaseModel):
    focus: Literal["vocabulary", "grammar"]
    page_id: str
    page_title: str
    content_hash: str
    last_edited_time: str | None = None
    image_count: int = 0
    section_count: int = 0


class NotionSyncPreview(BaseModel):
    focus: NotionFocus
    page_id: str
    page_title: str
    content_hash: str
    last_edited_time: str | None = None
    parsed: IngestionParseResult
    vocabulary_count: int
    grammar_count: int
    image_count: int = 0
    section_count: int = 0
    orphan_image_count: int = 0
    unchanged: bool = False
    grammar_new_count: int = 0
    grammar_updated_count: int = 0
    grammar_unchanged_count: int = 0
    sources: list[NotionPageSource] = Field(default_factory=list)


class NotionConfirmRequest(BaseModel):
    parsed: IngestionParseResult
    content_hash: str
    page_id: str
    page_title: str | None = None
    focus: NotionFocus = "both"
