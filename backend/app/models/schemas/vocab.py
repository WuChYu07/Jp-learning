from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.schemas.common import ExampleSentence, JlptLevel, PartOfSpeech


class VocabularyDefinitionBase(BaseModel):
    part_of_speech: PartOfSpeech = PartOfSpeech.OTHER
    meaning_zh: str
    meaning_en: str | None = None
    example_sentences: list[ExampleSentence] = Field(default_factory=list)
    notes_zh: str | None = None

    @field_validator("part_of_speech", mode="before")
    @classmethod
    def coerce_part_of_speech(cls, value: object) -> PartOfSpeech:
        if isinstance(value, PartOfSpeech):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
            try:
                return PartOfSpeech(normalized)
            except ValueError:
                return PartOfSpeech.OTHER
        return PartOfSpeech.OTHER


class VocabularyItemInput(BaseModel):
    """Gemini output shape — one word, many definitions."""

    word: str
    reading: str | None = None
    jlpt_level: JlptLevel = JlptLevel.UNKNOWN
    definitions: list[VocabularyDefinitionBase] = Field(min_length=1)

    @field_validator("jlpt_level", mode="before")
    @classmethod
    def coerce_jlpt(cls, value: object) -> JlptLevel:
        if isinstance(value, JlptLevel):
            return value
        if isinstance(value, str):
            upper = value.strip().upper()
            try:
                return JlptLevel(upper)
            except ValueError:
                return JlptLevel.UNKNOWN
        return JlptLevel.UNKNOWN


class VocabularyDefinitionOut(VocabularyDefinitionBase):
    id: UUID
    sort_order: int


class VocabularyOut(BaseModel):
    id: UUID
    word: str
    reading: str | None = None
    jlpt_level: JlptLevel
    definitions: list[VocabularyDefinitionOut]


class VocabularySummary(BaseModel):
    """Lightweight list row — no full definitions/examples."""

    id: UUID
    word: str
    reading: str | None = None
    jlpt_level: JlptLevel
    meaning_zh: str | None = None


class VocabEnrichmentOutput(BaseModel):
    """Gemini fill-gap payload for one vocabulary entry (does not rewrite headword)."""

    example_sentences: list[ExampleSentence] = Field(default_factory=list)
    notes_zh: str | None = None
    part_of_speech: PartOfSpeech | None = None
    jlpt_level: JlptLevel | None = None


class VocabularyWriteInput(BaseModel):
    """Manual / confirmed edit payload — primary definition fields."""

    word: str
    reading: str | None = None
    jlpt_level: JlptLevel = JlptLevel.UNKNOWN
    meaning_zh: str
    part_of_speech: PartOfSpeech = PartOfSpeech.OTHER
    example_sentences: list[ExampleSentence] = Field(default_factory=list)
    notes_zh: str | None = None

    @field_validator("jlpt_level", mode="before")
    @classmethod
    def coerce_jlpt(cls, value: object) -> JlptLevel:
        if isinstance(value, JlptLevel):
            return value
        if isinstance(value, str):
            upper = value.strip().upper()
            try:
                return JlptLevel(upper)
            except ValueError:
                return JlptLevel.UNKNOWN
        return JlptLevel.UNKNOWN

    @field_validator("word")
    @classmethod
    def require_word(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("word is required")
        return cleaned

    @field_validator("meaning_zh")
    @classmethod
    def require_meaning(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("meaning_zh is required")
        return cleaned
