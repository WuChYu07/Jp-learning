"""Dashboard aggregate stats."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel
from supabase import Client

from app.db.supabase import get_supabase_client
from app.services.review_activity_service import review_activity_service

_JLPT_ORDER = ["N5", "N4", "N3", "N2", "N1", "unknown"]


class DailyReviewCount(BaseModel):
    date: str
    count: int


class JlptMastery(BaseModel):
    jlpt_level: str
    total: int
    reviewed: int
    avg_score: float


class DashboardTrends(BaseModel):
    daily_counts: list[DailyReviewCount]
    vocab_jlpt: list[JlptMastery]
    grammar_jlpt: list[JlptMastery]


class DashboardStats(BaseModel):
    vocab_total: int
    grammar_total: int
    vocab_due_count: int
    grammar_due_count: int = 0
    streak_days: int
    daily_goal: int = 20
    reviewed_today: int = 0
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
        reviewed_today = 0
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

            today_start = datetime.now(UTC).replace(
                hour=0, minute=0, second=0, microsecond=0
            ).isoformat()
            vocab_today = (
                self.db.table("user_vocab_progress")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .gte("last_reviewed_at", today_start)
                .limit(1)
                .execute()
            )
            grammar_today = (
                self.db.table("user_grammar_progress")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .gte("last_reviewed_at", today_start)
                .limit(1)
                .execute()
            )
            reviewed_today = (vocab_today.count or 0) + (grammar_today.count or 0)

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
            reviewed_today=reviewed_today,
            review_points=review_points,
            review_score_avg=review_score_avg,
            exam_vocab_avg=exam_vocab_avg,
            exam_grammar_avg=exam_grammar_avg,
            exam_vocab_count=exam_vocab_count,
            exam_grammar_count=exam_grammar_count,
        )

    def get_trends(self, user_id: str | None, days: int = 14) -> DashboardTrends:
        if not user_id:
            return DashboardTrends(daily_counts=[], vocab_jlpt=[], grammar_jlpt=[])
        daily = review_activity_service.daily_counts(user_id, days)
        return DashboardTrends(
            daily_counts=[DailyReviewCount(**d) for d in daily],
            vocab_jlpt=self._jlpt_breakdown("vocabularies", "user_vocab_progress", "vocabulary_id", user_id),
            grammar_jlpt=self._jlpt_breakdown("grammars", "user_grammar_progress", "grammar_id", user_id),
        )

    def _jlpt_breakdown(
        self, content_table: str, progress_table: str, fk_col: str, user_id: str
    ) -> list[JlptMastery]:
        content_rows = self.db.table(content_table).select("id, jlpt_level").execute().data or []
        progress_rows = (
            self.db.table(progress_table)
            .select(f"{fk_col}, review_score")
            .eq("user_id", user_id)
            .execute()
        ).data or []
        score_map = {r[fk_col]: float(r.get("review_score") or 0) for r in progress_rows}

        scores_by_level: dict[str, list[float]] = {}
        reviewed_by_level: dict[str, int] = {}
        for row in content_rows:
            level = row.get("jlpt_level") or "unknown"
            score = score_map.get(row["id"])
            scores_by_level.setdefault(level, []).append(score if score is not None else 0.0)
            if score is not None:
                reviewed_by_level[level] = reviewed_by_level.get(level, 0) + 1

        result = []
        for level in _JLPT_ORDER:
            scores = scores_by_level.get(level)
            if not scores:
                continue
            result.append(
                JlptMastery(
                    jlpt_level=level,
                    total=len(scores),
                    reviewed=reviewed_by_level.get(level, 0),
                    avg_score=round(sum(scores) / len(scores), 1),
                )
            )
        return result

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
