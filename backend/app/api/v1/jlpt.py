"""JLPT batch enrichment: preview suggestions then apply confirmed levels."""

from fastapi import APIRouter

from app.models.schemas.jlpt import (
    JlptApplyRequest,
    JlptApplyResponse,
    JlptPreviewRequest,
    JlptPreviewResponse,
)
from app.services.jlpt_enrichment_service import jlpt_enrichment_service

router = APIRouter()


@router.post("/preview", response_model=JlptPreviewResponse)
def preview_jlpt(body: JlptPreviewRequest) -> JlptPreviewResponse:
    return jlpt_enrichment_service.preview(entity=body.entity, limit=body.limit)


@router.post("/apply", response_model=JlptApplyResponse)
def apply_jlpt(body: JlptApplyRequest) -> JlptApplyResponse:
    return jlpt_enrichment_service.apply(body.items)
