"""Review score deltas, daily view bonus, and low-score weighted sampling."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from supabase import Client

from app.db.supabase import get_supabase_client
from app.services.owner_service import ensure_owner_user

# Flashcard / view deltas (plan defaults)
GOOD_SCORE_DELTA = 8.0
GOOD_POINTS_DELTA = 5
AGAIN_SCORE_DELTA = -10.0
AGAIN_POINTS_DELTA = -3
VIEW_SCORE_DELTA = 2.0
VIEW_POINTS_DELTA = 1

RATING_SCORE_DELTAS: dict[str, tuple[float, int]] = {
    "good": (GOOD_SCORE_DELTA, GOOD_POINTS_DELTA),
    "easy": (GOOD_SCORE_DELTA + 2, GOOD_POINTS_DELTA + 1),
    "hard": (AGAIN_SCORE_DELTA / 2, -1),
    "again": (AGAIN_SCORE_DELTA, AGAIN_POINTS_DELTA),
}


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def clamp_points(value: int) -> int:
    return max(0, value)


def sample_weight(score: float) -> float:
    """Higher weight for lower scores. Missing progress treated as 0.

    Linear (not squared) so a couple of rock-bottom scores don't monopolize
    every draw and crowd out other below-average words.
    """
    return 100.0 - float(score) + 1.0


@dataclass
class ScoreSnapshot:
    review_score: float
    review_points: int
    score_delta: float
    points_delta: int
    viewed_bonus_applied: bool = False


class ScoreService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def get_review_points(self, user_id: str) -> int:
        row = (
            self.db.table("users")
            .select("review_points")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        if row is None or not row.data:
            return 0
        return int(row.data.get("review_points") or 0)

    def get_vocab_score(self, user_id: str, vocabulary_id: UUID | str) -> float:
        row = (
            self.db.table("user_vocab_progress")
            .select("review_score")
            .eq("user_id", user_id)
            .eq("vocabulary_id", str(vocabulary_id))
            .maybe_single()
            .execute()
        )
        if row is None or not row.data:
            return 0.0
        return float(row.data.get("review_score") or 0)

    def score_map_for_user(self, user_id: str) -> dict[str, float]:
        rows = (
            self.db.table("user_vocab_progress")
            .select("vocabulary_id, review_score")
            .eq("user_id", user_id)
            .execute()
        ).data or []
        return {r["vocabulary_id"]: float(r.get("review_score") or 0) for r in rows}

    def grammar_score_map_for_user(self, user_id: str) -> dict[str, float]:
        rows = (
            self.db.table("user_grammar_progress")
            .select("grammar_id, review_score")
            .eq("user_id", user_id)
            .execute()
        ).data or []
        return {r["grammar_id"]: float(r.get("review_score") or 0) for r in rows}

    def apply_grammar_rating(
        self,
        user_id: str,
        grammar_id: UUID | str,
        rating: str,
        *,
        progress_row: dict | None = None,
    ) -> ScoreSnapshot:
        ensure_owner_user(self.db)
        score_delta, points_delta = RATING_SCORE_DELTAS.get(rating, (0.0, 0))
        return self._apply_grammar_deltas(
            user_id,
            grammar_id,
            score_delta,
            points_delta,
            progress_row=progress_row,
            bump_times_reviewed=True,
        )

    def _apply_grammar_deltas(
        self,
        user_id: str,
        grammar_id: UUID | str,
        score_delta: float,
        points_delta: int,
        *,
        progress_row: dict | None = None,
        bump_times_reviewed: bool = False,
    ) -> ScoreSnapshot:
        if progress_row is None:
            progress = (
                self.db.table("user_grammar_progress")
                .select("id, review_score, times_reviewed, proficiency_score")
                .eq("user_id", user_id)
                .eq("grammar_id", str(grammar_id))
                .maybe_single()
                .execute()
            )
            progress_row = progress.data if progress is not None else None

        current_score = float((progress_row or {}).get("review_score") or 0)
        new_score = clamp_score(current_score + score_delta)
        applied_score_delta = new_score - current_score

        current_points = self.get_review_points(user_id)
        new_points = clamp_points(current_points + points_delta)
        applied_points_delta = new_points - current_points

        patch: dict = {
            "review_score": new_score,
            "proficiency_score": new_score,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if bump_times_reviewed:
            times = int((progress_row or {}).get("times_reviewed") or 0) + 1
            patch["times_reviewed"] = times
            patch["last_reviewed_at"] = datetime.now(UTC).isoformat()

        if progress_row and progress_row.get("id"):
            self.db.table("user_grammar_progress").update(patch).eq(
                "id", progress_row["id"]
            ).execute()
        else:
            self.db.table("user_grammar_progress").insert(
                {
                    "user_id": user_id,
                    "grammar_id": str(grammar_id),
                    "review_score": new_score,
                    "proficiency_score": new_score,
                    "times_reviewed": 1 if bump_times_reviewed else 0,
                    "easiness_factor": 2.5,
                    "repetitions": 0,
                    "interval_days": 1,
                    "next_review_date": datetime.now(UTC).isoformat(),
                    "last_reviewed_at": datetime.now(UTC).isoformat()
                    if bump_times_reviewed
                    else None,
                }
            ).execute()

        if applied_points_delta != 0:
            self.db.table("users").update({"review_points": new_points}).eq(
                "id", user_id
            ).execute()

        return ScoreSnapshot(
            review_score=new_score,
            review_points=new_points,
            score_delta=applied_score_delta,
            points_delta=applied_points_delta,
        )

    def weighted_sample_ids(
        self,
        vocabulary_ids: list[str],
        score_by_id: dict[str, float],
        *,
        count: int = 1,
        exclude_ids: set[str] | None = None,
    ) -> list[str]:
        exclude = exclude_ids or set()
        pool = [vid for vid in vocabulary_ids if vid not in exclude]
        if not pool:
            return []
        count = min(count, len(pool))
        weights = [sample_weight(score_by_id.get(vid, 0.0)) for vid in pool]
        # Without replacement: pick one at a time
        chosen: list[str] = []
        remaining = list(pool)
        remaining_weights = list(weights)
        for _ in range(count):
            if not remaining:
                break
            pick = random.choices(remaining, weights=remaining_weights, k=1)[0]
            idx = remaining.index(pick)
            chosen.append(pick)
            remaining.pop(idx)
            remaining_weights.pop(idx)
        return chosen

    def apply_rating(
        self,
        user_id: str,
        vocabulary_id: UUID | str,
        rating: str,
        *,
        progress_row: dict | None = None,
    ) -> ScoreSnapshot:
        ensure_owner_user(self.db)
        score_delta, points_delta = RATING_SCORE_DELTAS.get(rating, (0.0, 0))
        return self._apply_deltas(
            user_id,
            vocabulary_id,
            score_delta,
            points_delta,
            progress_row=progress_row,
            bump_times_reviewed=True,
        )

    def record_view(self, user_id: str, vocabulary_id: UUID | str) -> ScoreSnapshot:
        ensure_owner_user(self.db)
        today = datetime.now(UTC).date()
        progress = (
            self.db.table("user_vocab_progress")
            .select("id, review_score, last_view_bonus_date")
            .eq("user_id", user_id)
            .eq("vocabulary_id", str(vocabulary_id))
            .maybe_single()
            .execute()
        )
        row = progress.data if progress is not None else None
        last_bonus = None
        if row and row.get("last_view_bonus_date"):
            raw = row["last_view_bonus_date"]
            last_bonus = date.fromisoformat(str(raw)[:10]) if raw else None

        now_iso = datetime.now(UTC).isoformat()
        if row and last_bonus == today:
            # Touch last_viewed_at only
            self.db.table("user_vocab_progress").update(
                {"last_viewed_at": now_iso}
            ).eq("id", row["id"]).execute()
            return ScoreSnapshot(
                review_score=float(row.get("review_score") or 0),
                review_points=self.get_review_points(user_id),
                score_delta=0.0,
                points_delta=0,
                viewed_bonus_applied=False,
            )

        snap = self._apply_deltas(
            user_id,
            vocabulary_id,
            VIEW_SCORE_DELTA,
            VIEW_POINTS_DELTA,
            progress_row=row,
            bump_times_reviewed=False,
            view_bonus_date=today,
            last_viewed_at=now_iso,
        )
        return ScoreSnapshot(
            review_score=snap.review_score,
            review_points=snap.review_points,
            score_delta=snap.score_delta,
            points_delta=snap.points_delta,
            viewed_bonus_applied=True,
        )

    def _apply_deltas(
        self,
        user_id: str,
        vocabulary_id: UUID | str,
        score_delta: float,
        points_delta: int,
        *,
        progress_row: dict | None = None,
        bump_times_reviewed: bool = False,
        view_bonus_date: date | None = None,
        last_viewed_at: str | None = None,
    ) -> ScoreSnapshot:
        if progress_row is None:
            progress = (
                self.db.table("user_vocab_progress")
                .select("id, review_score, times_reviewed")
                .eq("user_id", user_id)
                .eq("vocabulary_id", str(vocabulary_id))
                .maybe_single()
                .execute()
            )
            progress_row = progress.data if progress is not None else None

        current_score = float((progress_row or {}).get("review_score") or 0)
        new_score = clamp_score(current_score + score_delta)
        applied_score_delta = new_score - current_score

        current_points = self.get_review_points(user_id)
        new_points = clamp_points(current_points + points_delta)
        applied_points_delta = new_points - current_points

        patch: dict = {
            "review_score": new_score,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if bump_times_reviewed:
            times = int((progress_row or {}).get("times_reviewed") or 0) + 1
            patch["times_reviewed"] = times
        if view_bonus_date is not None:
            patch["last_view_bonus_date"] = view_bonus_date.isoformat()
        if last_viewed_at is not None:
            patch["last_viewed_at"] = last_viewed_at

        if progress_row and progress_row.get("id"):
            self.db.table("user_vocab_progress").update(patch).eq(
                "id", progress_row["id"]
            ).execute()
        else:
            insert_row = {
                "user_id": user_id,
                "vocabulary_id": str(vocabulary_id),
                "review_score": new_score,
                "times_reviewed": 1 if bump_times_reviewed else 0,
                "easiness_factor": 2.5,
                "repetitions": 0,
                "interval_days": 1,
                "next_review_date": datetime.now(UTC).isoformat(),
            }
            if view_bonus_date is not None:
                insert_row["last_view_bonus_date"] = view_bonus_date.isoformat()
            if last_viewed_at is not None:
                insert_row["last_viewed_at"] = last_viewed_at
            self.db.table("user_vocab_progress").insert(insert_row).execute()

        if applied_points_delta != 0:
            self.db.table("users").update({"review_points": new_points}).eq(
                "id", user_id
            ).execute()

        return ScoreSnapshot(
            review_score=new_score,
            review_points=new_points,
            score_delta=applied_score_delta,
            points_delta=applied_points_delta,
        )


score_service = ScoreService()
