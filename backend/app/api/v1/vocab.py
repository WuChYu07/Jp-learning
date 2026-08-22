from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from pydantic import BaseModel, Field

from app.api.deps import get_effective_user_id
from app.models.schemas.common import JlptLevel
from app.models.schemas.links import LinkEntityType, RelationGraphOut
from app.models.schemas.vocab import ReviewScoreOut, VocabularyOut, VocabularySummary, VocabularyWriteInput
from app.services.link_service import link_service
from app.services.semantic_link_service import semantic_link_service
from app.services.vocab_enrichment_service import vocab_enrichment_service
from app.services.vocab_service import vocab_service

router = APIRouter()


class VocabListResponse(BaseModel):
    items: list[VocabularySummary]
    total: int
    limit: int
    offset: int


class ReviewBatchResponse(BaseModel):
    items: list[VocabularyOut]
    has_more: bool
    next_offset: int
    total: int


class ReviewSubmitRequest(BaseModel):
    vocabulary_id: UUID
    rating: str = Field(description="again | hard | good | easy")


@router.get("", response_model=VocabListResponse)
def list_vocabulary(
    jlpt: JlptLevel | None = None,
    q: str | None = Query(default=None, description="Search word / reading"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> VocabListResponse:
    items, total = vocab_service.list_vocab(jlpt=jlpt, limit=limit, offset=offset, q=q)
    return VocabListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/review/due", response_model=ReviewBatchResponse)
def get_due_reviews(
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
    limit: int = Query(default=10, ge=1, le=30),
    offset: int = Query(default=0, ge=0),
) -> ReviewBatchResponse:
    return vocab_service.get_due_reviews(user_id, limit=limit, offset=offset)


@router.post("/review")
def submit_review(
    body: ReviewSubmitRequest,
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
) -> dict:
    return vocab_service.submit_review(user_id, body.vocabulary_id, body.rating)


@router.get("/random", response_model=VocabularyOut)
def random_vocabulary(
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
    exclude_id: UUID | None = None,
    jlpt: JlptLevel | None = None,
) -> VocabularyOut:
    return vocab_service.random_vocab(user_id, exclude_id=exclude_id, jlpt=jlpt)


@router.post("/{vocabulary_id}/view", response_model=ReviewScoreOut)
def record_vocabulary_view(
    vocabulary_id: UUID,
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
) -> ReviewScoreOut:
    return vocab_service.record_view(user_id, vocabulary_id)


@router.get("/{vocabulary_id}/relations", response_model=RelationGraphOut)
def get_vocab_relations(
    vocabulary_id: UUID,
    depth: int = Query(default=1, ge=1, le=3),
) -> RelationGraphOut:
    vocab_service.get_vocab(vocabulary_id)
    return link_service.get_neighborhood(
        LinkEntityType.VOCABULARY, vocabulary_id, depth=depth
    )


@router.post("/{vocabulary_id}/sync-semantic-links")
def sync_vocab_semantic_links(vocabulary_id: UUID) -> dict:
    vocab_service.get_vocab(vocabulary_id)
    return semantic_link_service.sync_vocabulary(vocabulary_id, force=True)


@router.post("/{vocabulary_id}/ai-enrich", response_model=VocabularyOut)
def ai_enrich_vocabulary(vocabulary_id: UUID) -> VocabularyOut:
    """Preview AI gap-fill draft only — does not write DB until client PUT."""
    return vocab_enrichment_service.preview_enrich(vocabulary_id)


@router.put("/{vocabulary_id}", response_model=VocabularyOut)
def update_vocabulary(
    vocabulary_id: UUID,
    payload: VocabularyWriteInput,
    background_tasks: BackgroundTasks,
) -> VocabularyOut:
    result = vocab_service.update_vocab(vocabulary_id, payload)
    background_tasks.add_task(
        semantic_link_service.sync_entity_safe, LinkEntityType.VOCABULARY, vocabulary_id
    )
    return result


@router.get("/{vocabulary_id}", response_model=VocabularyOut)
def get_vocabulary(
    vocabulary_id: UUID,
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
) -> VocabularyOut:
    return vocab_service.get_vocab(vocabulary_id, user_id=user_id)


@router.delete("/{vocabulary_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vocabulary(vocabulary_id: UUID) -> Response:
    vocab_service.archive_vocabulary(vocabulary_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
