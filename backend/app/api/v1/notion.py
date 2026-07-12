"""Notion sync endpoints: preview → confirm."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_effective_user_id
from app.core.config import settings
from app.models.schemas.ingestion import IngestionResponse
from app.models.schemas.notion import NotionConfirmRequest, NotionSyncPreview, NotionSyncRequest
from app.services.notion_sync_service import notion_sync_service

router = APIRouter()


@router.post("/sync", response_model=NotionSyncPreview | IngestionResponse)
def sync_notion_page(
    body: NotionSyncRequest,
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
) -> NotionSyncPreview | IngestionResponse:
    """Fetch Notion page, parse blocks, return preview (no DB write unless auto-approve)."""
    preview = notion_sync_service.sync_preview(
        focus=body.focus,
        page_id=body.page_id,
        upload_images=body.upload_images,
    )

    if settings.NOTION_AUTO_APPROVE:
        return notion_sync_service.confirm_sync(
            parsed=preview.parsed,
            content_hash=preview.content_hash,
            page_id=preview.page_id,
            page_title=preview.page_title,
            user_id=user_id,
            focus=body.focus,
            auto_approved=True,
        )

    return preview


@router.post("/confirm", response_model=IngestionResponse)
def confirm_notion_sync(
    body: NotionConfirmRequest,
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
) -> IngestionResponse:
    """Save reviewed Notion parse result to DB."""
    return notion_sync_service.confirm_sync(
        parsed=body.parsed,
        content_hash=body.content_hash,
        page_id=body.page_id,
        page_title=body.page_title,
        user_id=user_id,
        focus=body.focus,
        auto_approved=False,
    )


@router.get("/status")
def notion_sync_status() -> dict:
    """Return latest Notion sync metadata."""
    return notion_sync_service.get_status()
