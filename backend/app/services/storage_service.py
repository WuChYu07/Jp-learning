"""Upload Notion images to Supabase Storage for permanent URLs."""

from __future__ import annotations

import mimetypes
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import settings
from app.db.supabase import get_supabase_client


def upload_image(file_bytes: bytes, *, content_type: str | None = None, suffix: str = ".jpg") -> str:
    bucket = settings.NOTION_STORAGE_BUCKET
    mime = content_type or mimetypes.guess_type(f"x{suffix}")[0] or "application/octet-stream"
    filename = f"{uuid4().hex}{suffix}"
    client = get_supabase_client()

    try:
        client.storage.from_(bucket).upload(
            filename,
            file_bytes,
            file_options={"content-type": mime, "upsert": "true"},
        )
        public = client.storage.from_(bucket).get_public_url(filename)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase Storage upload failed: {exc}. Ensure bucket '{bucket}' exists and is public.",
        ) from exc

    return public
