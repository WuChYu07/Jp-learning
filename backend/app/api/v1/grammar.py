from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel

from app.models.schemas.common import JlptLevel
from app.models.schemas.grammar import GrammarOut, GrammarSummary, GrammarWriteInput
from app.models.schemas.links import LinkEntityType, RelationGraphOut, SuggestLinksResponse
from app.services.grammar_enrichment_service import grammar_enrichment_service
from app.services.grammar_service import grammar_service
from app.services.link_service import link_service
from app.services.link_suggestion_service import link_suggestion_service

router = APIRouter()


class GrammarListResponse(BaseModel):
    items: list[GrammarSummary]
    total: int
    limit: int
    offset: int


@router.get("", response_model=GrammarListResponse)
def list_grammar(
    jlpt: JlptLevel | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> GrammarListResponse:
    items, total = grammar_service.list_grammar(jlpt=jlpt, limit=limit, offset=offset)
    return GrammarListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=GrammarOut, status_code=status.HTTP_201_CREATED)
def create_grammar(payload: GrammarWriteInput) -> GrammarOut:
    return grammar_service.create_grammar(payload)


@router.get("/{grammar_id}", response_model=GrammarOut)
def get_grammar(grammar_id: UUID) -> GrammarOut:
    return grammar_service.get_grammar(grammar_id)


@router.put("/{grammar_id}", response_model=GrammarOut)
def update_grammar(grammar_id: UUID, payload: GrammarWriteInput) -> GrammarOut:
    return grammar_service.update_grammar(grammar_id, payload)


@router.delete("/{grammar_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grammar(grammar_id: UUID) -> Response:
    grammar_service.archive_grammar(grammar_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{grammar_id}/enrich-image", response_model=GrammarOut)
def enrich_grammar_image(
    grammar_id: UUID,
    dry_run: bool = Query(default=True),
) -> GrammarOut:
    return grammar_enrichment_service.enrich_grammar(grammar_id, dry_run=dry_run)


@router.post("/{grammar_id}/ai-explain", response_model=GrammarOut)
def ai_explain_grammar(
    grammar_id: UUID,
    dry_run: bool = Query(default=True),
) -> GrammarOut:
    """Text-only AI teacher rewrite; dry_run (default) returns draft for user confirm."""
    return grammar_enrichment_service.explain_grammar(grammar_id, dry_run=dry_run)


@router.get("/{grammar_id}/relations", response_model=RelationGraphOut)
def get_grammar_relations(
    grammar_id: UUID,
    depth: int = Query(default=1, ge=1, le=3),
) -> RelationGraphOut:
    grammar_service.get_grammar(grammar_id)  # 404 if missing/archived
    return link_service.get_neighborhood(
        LinkEntityType.GRAMMAR, grammar_id, depth=depth
    )


@router.post("/{grammar_id}/suggest-links", response_model=SuggestLinksResponse)
def suggest_grammar_links(grammar_id: UUID) -> SuggestLinksResponse:
    grammar_service.get_grammar(grammar_id)
    return link_suggestion_service.suggest_for_grammar(grammar_id)


@router.post("/{grammar_id}/sync-semantic-links")
def sync_grammar_semantic_links(grammar_id: UUID) -> dict:
    grammar_service.get_grammar(grammar_id)
    from app.services.semantic_link_service import semantic_link_service

    return semantic_link_service.sync_grammar(grammar_id, force=True)
