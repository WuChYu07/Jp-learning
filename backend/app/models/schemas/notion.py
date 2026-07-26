from typing import Literal

from pydantic import BaseModel, Field

from app.models.schemas.ingestion import IngestionParseResult

NotionFocus = Literal["vocabulary", "grammar", "both"]


class NotionSyncRequest(BaseModel):
    focus: NotionFocus = "both"
    page_id: str | None = None
    upload_images: bool = True
    # Bypass the last_edited_time unchanged-skip and re-fetch every block.
    force_refresh: bool = False


class NotionPageSource(BaseModel):
    focus: Literal["vocabulary", "grammar"]
    page_id: str
    page_title: str
    content_hash: str
    last_edited_time: str | None = None
    image_count: int = 0
    section_count: int = 0


class NotionOrphanedGrammar(BaseModel):
    id: str
    grammar_point: str
    notion_block_id: str | None = None
    notion_page_id: str | None = None


class NotionOrphanedVocab(BaseModel):
    id: str
    word: str
    reading: str | None = None
    notion_page_id: str | None = None


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
    vocab_new_count: int = 0
    vocab_updated_count: int = 0
    vocab_unchanged_count: int = 0
    orphaned_grammars: list[NotionOrphanedGrammar] = Field(default_factory=list)
    orphaned_vocabularies: list[NotionOrphanedVocab] = Field(default_factory=list)
    sources: list[NotionPageSource] = Field(default_factory=list)


class NotionConfirmRequest(BaseModel):
    parsed: IngestionParseResult
    content_hash: str
    page_id: str
    page_title: str | None = None
    focus: NotionFocus = "both"
    force: bool = False
    force_overwrite_grammar_block_ids: list[str] = Field(default_factory=list)
    archive_grammar_ids: list[str] = Field(default_factory=list)
    archive_vocab_ids: list[str] = Field(default_factory=list)
    # vocabulary_id -> field names ("meaning_zh" | "notes_zh" | "example_sentences")
    # to force-overwrite with Notion's value even if the DB field is non-empty.
    vocab_field_overwrites: dict[str, list[str]] = Field(default_factory=dict)
