from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class JlptLevel(str, Enum):
    N5 = "N5"
    N4 = "N4"
    N3 = "N3"
    N2 = "N2"
    N1 = "N1"
    UNKNOWN = "unknown"


class SourceType(str, Enum):
    IMAGE = "image"
    PDF = "pdf"
    MANUAL = "manual"
    API = "api"
    NOTION = "notion"


class PartOfSpeech(str, Enum):
    NOUN = "noun"
    VERB = "verb"
    I_ADJECTIVE = "i_adjective"
    NA_ADJECTIVE = "na_adjective"
    ADVERB = "adverb"
    PARTICLE = "particle"
    COUNTER = "counter"
    EXPRESSION = "expression"
    OTHER = "other"


class ExampleSentence(BaseModel):
    japanese: str
    reading: str | None = None
    chinese: str | None = None
    english: str | None = None
    # Substring of japanese that is the target grammar form (for UI highlight).
    highlight: str | None = None
    acceptable_patterns: list[str] = Field(default_factory=list)


MeaningBlockVariant = Literal["emphasis", "note", "caution", "default"]


class MeaningBlock(BaseModel):
    """Colored Chinese explanation segment for grammar usages."""

    text: str
    variant: MeaningBlockVariant = "default"


class SupplementaryBlock(BaseModel):
    """Summary block from supplemental note images."""

    title: str = "補充說明"
    summary_zh: str
    example_sentences: list[ExampleSentence] = Field(default_factory=list)
