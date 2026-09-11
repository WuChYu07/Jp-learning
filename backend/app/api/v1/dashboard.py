from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_optional_user_id
from app.services.dashboard_service import DashboardStats, DashboardTrends, dashboard_service
from app.services.grammar_service import grammar_service
from app.services.vocab_service import vocab_service

router = APIRouter()


class ReviewPoolCounts(BaseModel):
    due: int
    new: int
    early: int


class ReviewPools(BaseModel):
    vocab: ReviewPoolCounts
    grammar: ReviewPoolCounts


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    user_id: Annotated[str | None, Depends(get_optional_user_id)] = None,
) -> DashboardStats:
    return dashboard_service.get_stats(user_id)


@router.get("/trends", response_model=DashboardTrends)
def get_dashboard_trends(
    user_id: Annotated[str | None, Depends(get_optional_user_id)] = None,
    days: int = 14,
) -> DashboardTrends:
    return dashboard_service.get_trends(user_id, days=days)


@router.get("/review-pools", response_model=ReviewPools)
def get_review_pools(
    user_id: Annotated[str | None, Depends(get_optional_user_id)] = None,
) -> ReviewPools:
    if user_id is None:
        empty = ReviewPoolCounts(due=0, new=0, early=0)
        return ReviewPools(vocab=empty, grammar=empty)
    return ReviewPools(
        vocab=ReviewPoolCounts(**vocab_service.get_review_pool_counts(user_id)),
        grammar=ReviewPoolCounts(**grammar_service.get_review_pool_counts(user_id)),
    )
