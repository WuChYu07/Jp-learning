"""Single-tenant owner id used when AUTH_ENABLED=false."""

from __future__ import annotations

import logging

from supabase import Client

from app.db.supabase import get_supabase_client

# Fixed UUID — do not change after progress rows exist in production.
SINGLETON_OWNER_ID = "a0000000-0000-4000-8000-000000000001"

logger = logging.getLogger(__name__)


def ensure_owner_user(db: Client | None = None) -> str:
    """Ensure the singleton owner row exists in public.users. Returns owner id."""
    client = db or get_supabase_client()
    existing = (
        client.table("users")
        .select("id")
        .eq("id", SINGLETON_OWNER_ID)
        .maybe_single()
        .execute()
    )
    if existing is not None and existing.data:
        return SINGLETON_OWNER_ID

    try:
        client.table("users").insert(
            {
                "id": SINGLETON_OWNER_ID,
                "username": "owner",
                "display_name": "Komorebi Owner",
            }
        ).execute()
    except Exception as exc:
        # Race or migration 012 not applied yet — log and continue;
        # score writes will surface a clearer DB error.
        logger.warning("Could not ensure singleton owner user: %s", exc)

    return SINGLETON_OWNER_ID
