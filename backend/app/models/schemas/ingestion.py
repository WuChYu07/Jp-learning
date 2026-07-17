from uuid import UUID

from pydantic import BaseModel, Field

from app.models.schemas.grammar import GrammarItemInput, GrammarOut
from app.models.schemas.vocab import VocabularyItemInput, VocabularyOut


class IngestionParseResult(BaseModel):
    """Strict JSON contract we ask Gemini to return."""

    vocabularies: list[VocabularyItemInput] = Field(default_factory=list)
    grammars: list[GrammarItemInput] = Field(default_factory=list)


class SyncReport(BaseModel):
    """Write-side quality breakdown surfaced after an import/sync confirm."""

    vocab_source_rows: int = 0
    vocab_new: int = 0
    vocab_updated: int = 0
    vocab_skipped: int = 0
    vocab_dedupe_removed: int = 0

    grammar_source_rows: int = 0
    grammar_new: int = 0
    grammar_updated: int = 0
    grammar_skipped: int = 0
    grammar_dedupe_removed: int = 0


class IngestionResponse(BaseModel):
    ingestion_id: UUID
    content_hash: str
    cached: bool
    vocabulary_count: int
    grammar_count: int
    vocabularies: list[VocabularyOut] = Field(default_factory=list)
    grammars: list[GrammarOut] = Field(default_factory=list)
    report: SyncReport | None = None
