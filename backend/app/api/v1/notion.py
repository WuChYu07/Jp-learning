"""Notion sync endpoints: preview → confirm."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

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
        force_refresh=body.force_refresh,
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
        force=body.force,
        force_overwrite_grammar_block_ids=body.force_overwrite_grammar_block_ids,
        archive_grammar_ids=body.archive_grammar_ids,
        archive_vocab_ids=body.archive_vocab_ids,
        vocab_field_overwrites=body.vocab_field_overwrites,
    )


@router.get("/status")
def notion_sync_status() -> dict:
    """Return latest Notion sync metadata."""
    return notion_sync_service.get_status()


@router.post("/scheduled-check")
def scheduled_notion_check(
    x_scheduled_sync_token: Annotated[str | None, Header()] = None,
) -> dict:
    """Preview-only check for unattended callers (e.g. a GitHub Actions cron).
    Never writes content; a human still confirms via the Upload page."""
    if not settings.SCHEDULED_SYNC_TOKEN or x_scheduled_sync_token != settings.SCHEDULED_SYNC_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid sync token")
    return notion_sync_service.run_scheduled_check()
