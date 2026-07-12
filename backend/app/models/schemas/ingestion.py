from uuid import UUID

from pydantic import BaseModel, Field

from app.models.schemas.grammar import GrammarItemInput, GrammarOut
from app.models.schemas.vocab import VocabularyItemInput, VocabularyOut


class IngestionParseResult(BaseModel):
    """Strict JSON contract we ask Gemini to return."""

    vocabularies: list[VocabularyItemInput] = Field(default_factory=list)
    grammars: list[GrammarItemInput] = Field(default_factory=list)


class IngestionResponse(BaseModel):
    ingestion_id: UUID
    content_hash: str
    cached: bool
    vocabulary_count: int
    grammar_count: int
    vocabularies: list[VocabularyOut] = Field(default_factory=list)
    grammars: list[GrammarOut] = Field(default_factory=list)
