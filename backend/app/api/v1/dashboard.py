from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_optional_user_id
from app.services.dashboard_service import DashboardStats, DashboardTrends, dashboard_service

router = APIRouter()


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
