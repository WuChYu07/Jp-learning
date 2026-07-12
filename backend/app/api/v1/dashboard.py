from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_optional_user_id
from app.services.dashboard_service import DashboardStats, dashboard_service

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    user_id: Annotated[str | None, Depends(get_optional_user_id)] = None,
) -> DashboardStats:
    return dashboard_service.get_stats(user_id)
