"""REST API for content knowledge-graph links."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.models.schemas.links import (
    ConfirmLinksRequest,
    ConfirmLinksResponse,
    ContentLinkCreate,
    ContentLinkOut,
    ForceGraphLink,
    ForceGraphNode,
    ForceGraphOut,
    LinkEntityType,
    LinkRelationType,
    RelationGraphOut,
    SuggestLinksResponse,
)
from app.services.link_service import link_service
from app.services.link_suggestion_service import link_suggestion_service
from app.services.semantic_link_service import semantic_link_service

router = APIRouter()


@router.get("", response_model=RelationGraphOut)
def get_global_graph(
    entity_types: str | None = Query(
        default="grammar,concept",
        description="Comma-separated: grammar,vocabulary,concept",
    ),
    jlpt: str | None = Query(
        default=None,
        description="Optional display filter only; does not affect how links were built",
    ),
    relation_types: str | None = Query(
        default=None,
        description="Comma-separated relation types",
    ),
    limit: int = Query(default=200, ge=1, le=500),
    min_confidence: float | None = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description="Hide edges below this confidence (display filter)",
    ),
) -> RelationGraphOut:
    etypes = _parse_entity_types(entity_types)
    rtypes = _parse_relation_types(relation_types)
    return link_service.get_global_graph(
        entity_types=etypes,
        jlpt=jlpt,
        relation_types=rtypes,
        limit=limit,
        min_confidence=min_confidence,
    )


@router.get("/force", response_model=ForceGraphOut)
def get_force_graph(
    entity_types: str | None = Query(default="grammar,vocabulary"),
    jlpt: str | None = Query(
        default=None,
        description="Optional display filter only",
    ),
    limit: int = Query(default=300, ge=1, le=500),
) -> ForceGraphOut:
    graph = link_service.get_global_graph(
        entity_types=_parse_entity_types(entity_types),
        jlpt=jlpt,
        limit=limit,
    )
    return ForceGraphOut(
        nodes=[
            ForceGraphNode(
                id=n.id,
                label=n.label,
                group=n.group or n.jlpt_level,
            )
            for n in graph.nodes
        ],
        links=[
            ForceGraphLink(
                source=e.source,
                target=e.target,
                value=float(e.confidence or 1.0),
            )
            for e in graph.edges
        ],
    )


@router.get(
    "/neighborhood/{entity_type}/{entity_id}",
    response_model=RelationGraphOut,
)
def get_entity_relations(
    entity_type: LinkEntityType,
    entity_id: UUID,
    depth: int = Query(default=1, ge=1, le=3),
    relation_types: str | None = None,
) -> RelationGraphOut:
    rtypes = _parse_relation_types(relation_types)
    return link_service.get_neighborhood(
        entity_type, entity_id, depth=depth, relation_types=rtypes
    )


@router.post("/links", response_model=ContentLinkOut, status_code=status.HTTP_201_CREATED)
def create_link(payload: ContentLinkCreate) -> ContentLinkOut:
    return link_service.create_link(payload)


@router.post("/links/confirm", response_model=ConfirmLinksResponse)
def confirm_links(payload: ConfirmLinksRequest) -> ConfirmLinksResponse:
    normalized: list[ContentLinkCreate] = []
    for link in payload.links:
        normalized.append(
            ContentLinkCreate(
                source_type=payload.source_type,
                source_id=payload.source_id,
                target_type=link.target_type,
                target_id=link.target_id,
                relation_type=link.relation_type,
                label_zh=link.label_zh,
                note_zh=link.note_zh,
                confidence=link.confidence,
                origin=link.origin or "ai",
                bidirectional=link.bidirectional,
            )
        )
    created, skipped = link_service.create_links_batch(normalized)
    return ConfirmLinksResponse(created=created, skipped=skipped)


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(link_id: UUID) -> Response:
    link_service.delete_link(link_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/suggest/grammar/{grammar_id}",
    response_model=SuggestLinksResponse,
)
def suggest_grammar_links(grammar_id: UUID) -> SuggestLinksResponse:
    return link_suggestion_service.suggest_for_grammar(grammar_id)


@router.post("/sync-semantic/grammar/{grammar_id}")
def sync_semantic_grammar(grammar_id: UUID) -> dict:
    return semantic_link_service.sync_grammar(grammar_id, force=True)


@router.post("/sync-semantic/vocabulary/{vocabulary_id}")
def sync_semantic_vocabulary(vocabulary_id: UUID) -> dict:
    return semantic_link_service.sync_vocabulary(vocabulary_id, force=True)


@router.post("/prune-weak")
def prune_weak_links(
    min_confidence: float | None = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description="Defaults to EMBEDDING_SIMILARITY_THRESHOLD",
    ),
) -> dict:
    """Remove weak auto-generated same_meaning links (Map maintenance)."""
    return semantic_link_service.prune_weak_embedding_links(min_confidence=min_confidence)


@router.post("/recompute-semantic")
def recompute_semantic_links(
    entity_types: str | None = Query(
        default="grammar,vocabulary",
        description="Comma-separated: grammar,vocabulary",
    ),
    limit: int = Query(default=40, ge=1, le=120),
    force: bool = Query(default=False),
) -> dict:
    """Batch recompute embeddings + same_meaning links for recent entities."""
    return semantic_link_service.recompute_semantic_links(
        entity_types=_parse_entity_types(entity_types),
        limit=limit,
        force=force,
    )


def _parse_entity_types(raw: str | None) -> list[LinkEntityType] | None:
    if not raw:
        return None
    out: list[LinkEntityType] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(LinkEntityType(part))
    return out or None


def _parse_relation_types(raw: str | None) -> list[LinkRelationType] | None:
    if not raw:
        return None
    out: list[LinkRelationType] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(LinkRelationType(part))
    return out or None
