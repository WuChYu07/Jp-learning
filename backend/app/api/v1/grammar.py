from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from pydantic import BaseModel, Field

from app.api.deps import get_effective_user_id
from app.models.schemas.common import JlptLevel
from app.models.schemas.grammar import GrammarOut, GrammarSummary, GrammarWriteInput
from app.models.schemas.links import LinkEntityType, RelationGraphOut, SuggestLinksResponse
from app.services.grammar_enrichment_service import grammar_enrichment_service
from app.services.grammar_service import GrammarReviewBatch, grammar_service
from app.services.link_service import link_service
from app.services.link_suggestion_service import link_suggestion_service
from app.services.semantic_link_service import semantic_link_service

router = APIRouter()


class GrammarListResponse(BaseModel):
    items: list[GrammarSummary]
    total: int
    limit: int
    offset: int


class GrammarReviewBatchResponse(BaseModel):
    items: list[GrammarOut]
    has_more: bool
    next_offset: int
    total: int


class GrammarReviewSubmitRequest(BaseModel):
    grammar_id: UUID
    rating: str = Field(description="again | hard | good | easy")


class AddExampleFromPracticeRequest(BaseModel):
    japanese: str
    chinese: str | None = None


@router.get("", response_model=GrammarListResponse)
def list_grammar(
    jlpt: JlptLevel | None = None,
    q: str | None = Query(default=None, description="Search grammar_point"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> GrammarListResponse:
    items, total = grammar_service.list_grammar(
        jlpt=jlpt, limit=limit, offset=offset, q=q
    )
    return GrammarListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=GrammarOut, status_code=status.HTTP_201_CREATED)
def create_grammar(payload: GrammarWriteInput, background_tasks: BackgroundTasks) -> GrammarOut:
    result = grammar_service.create_grammar(payload)
    background_tasks.add_task(
        semantic_link_service.sync_entity_safe, LinkEntityType.GRAMMAR, result.id
    )
    return result


@router.get("/review/due", response_model=GrammarReviewBatchResponse)
def get_due_grammar_reviews(
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
    limit: int = Query(default=10, ge=1, le=30),
    offset: int = Query(default=0, ge=0),
) -> GrammarReviewBatch:
    return grammar_service.get_due_reviews(user_id, limit=limit, offset=offset)


@router.post("/review")
def submit_grammar_review(
    body: GrammarReviewSubmitRequest,
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
) -> dict:
    return grammar_service.submit_review(user_id, body.grammar_id, body.rating)


@router.get("/random", response_model=GrammarOut)
def random_grammar(
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
    exclude_id: UUID | None = None,
    jlpt: JlptLevel | None = None,
) -> GrammarOut:
    return grammar_service.random_grammar(user_id, exclude_id=exclude_id, jlpt=jlpt)


@router.get("/{grammar_id}", response_model=GrammarOut)
def get_grammar(grammar_id: UUID) -> GrammarOut:
    return grammar_service.get_grammar(grammar_id)


@router.put("/{grammar_id}", response_model=GrammarOut)
def update_grammar(
    grammar_id: UUID,
    payload: GrammarWriteInput,
    background_tasks: BackgroundTasks,
) -> GrammarOut:
    result = grammar_service.update_grammar(grammar_id, payload)
    background_tasks.add_task(
        semantic_link_service.sync_entity_safe, LinkEntityType.GRAMMAR, grammar_id
    )
    return result


@router.delete("/{grammar_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grammar(grammar_id: UUID) -> Response:
    grammar_service.archive_grammar(grammar_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{grammar_id}/examples/from-practice", response_model=GrammarOut)
def add_grammar_example_from_practice(
    grammar_id: UUID,
    payload: AddExampleFromPracticeRequest,
    background_tasks: BackgroundTasks,
) -> GrammarOut:
    result = grammar_service.add_example_from_practice(
        grammar_id, japanese=payload.japanese, chinese=payload.chinese
    )
    background_tasks.add_task(
        semantic_link_service.sync_entity_safe, LinkEntityType.GRAMMAR, grammar_id
    )
    return result


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
    return semantic_link_service.sync_grammar(grammar_id, force=True)
