"""Ingestion endpoints: file upload, text paste, CSV upload."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.api.deps import get_effective_user_id
from app.models.schemas.common import SourceType
from app.models.schemas.ingestion import IngestionParseResult, IngestionResponse
from app.services.hash_service import ALLOWED_MIME_TYPES, MAX_UPLOAD_BYTES, sha256_hex
from app.services.gemini_service import IngestionFocus
from app.services.ingestion_service import ingestion_service

router = APIRouter()


# ── File upload (PDF / Image) ────────────────────────────────────────────────

@router.post("/upload", response_model=IngestionResponse)
async def upload_study_material(
    file: Annotated[UploadFile, File(description="PDF or image (JPEG/PNG/WebP)")],
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
    focus: IngestionFocus = "both",
) -> IngestionResponse:
    if not file.content_type or file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_MIME_TYPES)}",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
        )

    return ingestion_service.process_upload(
        file_bytes=file_bytes,
        mime_type=file.content_type,
        file_name=file.filename,
        user_id=user_id,
        source_type=ALLOWED_MIME_TYPES[file.content_type],
        focus=focus,
    )


# ── Text paste (Gemini parse) ────────────────────────────────────────────────

class TextParseRequest(BaseModel):
    text: str = Field(min_length=5, max_length=30000)
    focus: IngestionFocus = "both"


class TextParsePreview(BaseModel):
    """Preview before confirming — parsed but NOT yet saved to DB."""
    parsed: IngestionParseResult
    content_hash: str
    vocabulary_count: int
    grammar_count: int


class TextConfirmRequest(BaseModel):
    parsed: IngestionParseResult
    content_hash: str
    focus: IngestionFocus = "both"


@router.post("/text/parse", response_model=TextParsePreview)
def parse_text_preview(
    body: TextParseRequest,
) -> TextParsePreview:
    """Parse pasted text via Gemini and return preview (does NOT save to DB)."""
    from app.services import gemini_service

    text_bytes = body.text.encode("utf-8")
    content_hash = sha256_hex(text_bytes)

    cached = ingestion_service._find_cached_ingestion(content_hash)
    if cached:
        payload = cached.get("parsed_payload") or cached
        parsed = IngestionParseResult(
            vocabularies=[],
            grammars=[],
        )
        return TextParsePreview(
            parsed=parsed,
            content_hash=content_hash,
            vocabulary_count=payload.get("vocabulary_count", 0),
            grammar_count=payload.get("grammar_count", 0),
        )

    parsed = gemini_service.parse_content(
        file_bytes=text_bytes,
        mime_type="text/plain",
        focus=body.focus,
    )

    return TextParsePreview(
        parsed=parsed,
        content_hash=content_hash,
        vocabulary_count=len(parsed.vocabularies),
        grammar_count=len(parsed.grammars),
    )


@router.post("/text/confirm", response_model=IngestionResponse)
def confirm_text_import(
    body: TextConfirmRequest,
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
) -> IngestionResponse:
    """Confirm and save previously parsed text data to DB."""
    return ingestion_service.process_parsed_data(
        parsed=body.parsed,
        content_hash=body.content_hash,
        user_id=user_id,
        source_type=SourceType.MANUAL,
        mime_type="text/plain",
        file_name="text-paste",
    )
