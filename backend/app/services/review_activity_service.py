"""Solo-user review streak and daily activity helpers."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from supabase import Client

from app.db.supabase import get_supabase_client
from app.services.owner_service import ensure_owner_user

logger = logging.getLogger(__name__)


class ReviewActivityService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def log_review_event(
        self, user_id: str, entity_type: str, entity_id: UUID, rating: str
    ) -> None:
        """Append-only event for trend charts (does not affect streak/score)."""
        try:
            self.db.table("review_events").insert(
                {
                    "user_id": user_id,
                    "entity_type": entity_type,
                    "entity_id": str(entity_id),
                    "rating": rating,
                }
            ).execute()
        except Exception:
            # review_events may not exist until migration 023 is applied — trend
            # charts stay empty rather than breaking review submission.
            logger.warning(
                "review_events insert failed (migration 023 may not be applied yet)",
                exc_info=True,
            )

    def daily_counts(self, user_id: str, days: int = 14) -> list[dict]:
        """Review counts per UTC calendar day for the last `days` days, oldest first."""
        since = datetime.now(UTC) - timedelta(days=days - 1)
        since_start = since.replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            rows = (
                self.db.table("review_events")
                .select("reviewed_at")
                .eq("user_id", user_id)
                .gte("reviewed_at", since_start.isoformat())
                .execute()
            ).data or []
        except Exception:
            logger.debug("review_events query failed (migration 023 may not be applied yet)")
            rows = []

        counts: Counter[date] = Counter()
        for row in rows:
            reviewed_at = datetime.fromisoformat(str(row["reviewed_at"]).replace("Z", "+00:00"))
            counts[reviewed_at.date()] += 1

        today = datetime.now(UTC).date()
        return [
            {
                "date": (today - timedelta(days=offset)).isoformat(),
                "count": counts[today - timedelta(days=offset)],
            }
            for offset in range(days - 1, -1, -1)
        ]

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
