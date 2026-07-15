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
    grammar_due_count: int = 0
    streak_days: int
    daily_goal: int = 10
    review_points: int = 0
    review_score_avg: float = 0
    exam_vocab_avg: float | None = None
    exam_grammar_avg: float | None = None
    exam_vocab_count: int = 0
    exam_grammar_count: int = 0


class DashboardService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def get_stats(self, user_id: str | None = None) -> DashboardStats:
        vocab_total = self.db.table("vocabularies").select("id", count="exact").limit(1).execute().count or 0
        grammar_total = self.db.table("grammars").select("id", count="exact").limit(1).execute().count or 0

        vocab_due = 0
        grammar_due = 0
        streak = 0
        review_points = 0
        review_score_avg = 0.0
        exam_vocab_avg: float | None = None
        exam_grammar_avg: float | None = None
        exam_vocab_count = 0
        exam_grammar_count = 0

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
                .select("vocabulary_id, review_score")
                .eq("user_id", user_id)
                .execute()
            )
            rows = progress.data or []
            seen = len(rows)
            vocab_due += max(0, min(vocab_total - seen, 10))
            if rows:
                review_score_avg = round(
                    sum(float(r.get("review_score") or 0) for r in rows) / len(rows),
                    1,
                )

            g_due = (
                self.db.table("user_grammar_progress")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .lte("next_review_date", now_iso)
                .limit(1)
                .execute()
            )
            grammar_due = g_due.count or 0
            g_progress = (
                self.db.table("user_grammar_progress")
                .select("grammar_id")
                .eq("user_id", user_id)
                .execute()
            )
            g_seen = len(g_progress.data or [])
            grammar_due += max(0, min(grammar_total - g_seen, 10))

            profile = (
                self.db.table("users")
                .select("streak_days, review_points")
                .eq("id", user_id)
                .maybe_single()
                .execute()
            )
            if profile is not None and profile.data:
                streak = profile.data.get("streak_days") or 0
                review_points = int(profile.data.get("review_points") or 0)

            exam_vocab_avg, exam_vocab_count = self._exam_avg(user_id, "vocab")
            exam_grammar_avg, exam_grammar_count = self._exam_avg(user_id, "grammar")
        else:
            vocab_due = vocab_total
            grammar_due = grammar_total

        return DashboardStats(
            vocab_total=vocab_total,
            grammar_total=grammar_total,
            vocab_due_count=vocab_due,
            grammar_due_count=grammar_due,
            streak_days=streak,
            review_points=review_points,
            review_score_avg=review_score_avg,
            exam_vocab_avg=exam_vocab_avg,
            exam_grammar_avg=exam_grammar_avg,
            exam_vocab_count=exam_vocab_count,
            exam_grammar_count=exam_grammar_count,
        )

    def _exam_avg(self, user_id: str, subject: str) -> tuple[float | None, int]:
        rows = (
            self.db.table("exam_attempts")
            .select("score_percent")
            .eq("user_id", user_id)
            .eq("subject", subject)
            .order("completed_at", desc=True)
            .limit(20)
            .execute()
        ).data or []
        if not rows:
            return None, 0
        avg = round(sum(float(r.get("score_percent") or 0) for r in rows) / len(rows), 1)
        return avg, len(rows)


dashboard_service = DashboardService()
