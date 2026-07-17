"""Solo-user review streak and daily activity helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from supabase import Client

from app.db.supabase import get_supabase_client
from app.services.owner_service import ensure_owner_user


class ReviewActivityService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def record_review(self, user_id: str) -> int:
        """Advance the streak at most once per UTC calendar day."""
        ensure_owner_user(self.db)
        now = datetime.now(UTC)
        profile = (
            self.db.table("users")
            .select("streak_days, last_active_at")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        row = profile.data if profile is not None and profile.data else {}
        streak = int(row.get("streak_days") or 0)
        last_active_raw = row.get("last_active_at")

        if last_active_raw:
            last_active = datetime.fromisoformat(str(last_active_raw).replace("Z", "+00:00"))
            if last_active.date() == now.date():
                return streak
            streak = streak + 1 if last_active.date() == (now - timedelta(days=1)).date() else 1
        else:
            streak = 1

        self.db.table("users").update(
            {"streak_days": streak, "last_active_at": now.isoformat()}
        ).eq("id", user_id).execute()
        return streak


review_activity_service = ReviewActivityService()
