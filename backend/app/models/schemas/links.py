"""Schemas for content knowledge-graph links."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class LinkEntityType(str, Enum):
    GRAMMAR = "grammar"
    VOCABULARY = "vocabulary"
    CONCEPT = "concept"


class LinkRelationType(str, Enum):
    SAME_MEANING = "same_meaning"
    CONTRAST = "contrast"
    CONFUSABLE = "confusable"
    PREREQUISITE = "prerequisite"
    DERIVED = "derived"


class ContentLinkCreate(BaseModel):
    source_type: LinkEntityType
    source_id: UUID
    target_type: LinkEntityType
    target_id: UUID
    relation_type: LinkRelationType
    label_zh: str | None = None
    note_zh: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    origin: str = "manual"
    bidirectional: bool = True


class ContentLinkOut(BaseModel):
    id: UUID
    source_type: LinkEntityType
    source_id: UUID
    target_type: LinkEntityType
    target_id: UUID
    relation_type: LinkRelationType
    label_zh: str | None = None
    note_zh: str | None = None
    confidence: float = 1.0
    origin: str = "manual"
    bidirectional: bool = True


class GraphNode(BaseModel):
    id: str
    type: LinkEntityType
    label: str
    jlpt_level: str | None = None
    group: str | None = None  # JLPT band for force-graph coloring only


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation_type: LinkRelationType
    label_zh: str | None = None
    note_zh: str | None = None
    confidence: float = 1.0


class RelationGraphOut(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    center_id: str


class ForceGraphNode(BaseModel):
    id: str
    label: str
    group: str | None = None


class ForceGraphLink(BaseModel):
    source: str
    target: str
    value: float = 1.0


class ForceGraphOut(BaseModel):
    nodes: list[ForceGraphNode]
    links: list[ForceGraphLink]


class SuggestedLink(BaseModel):
    target_type: LinkEntityType = LinkEntityType.GRAMMAR
    target_id: UUID | None = None
    target_label: str
    relation_type: LinkRelationType
    label_zh: str | None = None
    note_zh: str | None = None
    confidence: float = Field(default=0.7, ge=0, le=1)


class SuggestLinksResponse(BaseModel):
    suggestions: list[SuggestedLink]
    center_id: UUID
    center_label: str


class ConfirmLinksRequest(BaseModel):
    source_type: LinkEntityType
    source_id: UUID
    links: list[ContentLinkCreate]


class ConfirmLinksResponse(BaseModel):
    created: list[ContentLinkOut]
    skipped: int = 0


class SemanticConceptOut(BaseModel):
    id: UUID
    title_zh: str
    description_zh: str | None = None
    jlpt_level: str | None = None
