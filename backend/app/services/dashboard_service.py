"""Dashboard aggregate stats."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel
from supabase import Client

from app.db.supabase import get_supabase_client


class DashboardStats(BaseModel):
    vocab_total: int
    grammar_total: int
    vocab_due_count: int
    streak_days: int
    daily_goal: int = 10


class DashboardService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def get_stats(self, user_id: str | None = None) -> DashboardStats:
        vocab_total = self.db.table("vocabularies").select("id", count="exact").limit(1).execute().count or 0
        grammar_total = self.db.table("grammars").select("id", count="exact").limit(1).execute().count or 0

        vocab_due = 0
        streak = 0
        if user_id:
            now_iso = datetime.now(UTC).isoformat()
            due = (
                self.db.table("user_vocab_progress")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .lte("next_review_date", now_iso)
                .limit(1)
                .execute()
            )
            vocab_due = due.count or 0

            progress = (
                self.db.table("user_vocab_progress")
                .select("vocabulary_id")
                .eq("user_id", user_id)
                .execute()
            )
            seen = len(progress.data or [])
            vocab_due += max(0, min(vocab_total - seen, 10))

            profile = (
                self.db.table("users")
                .select("streak_days")
                .eq("id", user_id)
                .maybe_single()
                .execute()
            )
            if profile is not None and profile.data:
                streak = profile.data.get("streak_days") or 0
        else:
            # Single-user mode: all vocab available for practice
            vocab_due = vocab_total

        return DashboardStats(
            vocab_total=vocab_total,
            grammar_total=grammar_total,
            vocab_due_count=vocab_due,
            streak_days=streak,
        )


dashboard_service = DashboardService()
