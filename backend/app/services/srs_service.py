"""SM-2 spaced repetition helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import settings


@dataclass
class SrsState:
    easiness_factor: float
    repetitions: int
    interval_days: int


@dataclass
class SrsUpdate:
    easiness_factor: float
    repetitions: int
    interval_days: int
    next_review_date: datetime


def rating_to_quality(rating: str) -> int:
    mapping = {"again": 1, "hard": 3, "good": 4, "easy": 5}
    return mapping.get(rating.lower(), 3)


def apply_review(state: SrsState, quality: int) -> SrsUpdate:
    ef = state.easiness_factor
    reps = state.repetitions
    interval = state.interval_days

    if quality < 3:
        reps = 0
        interval = 1
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = max(1, round(interval * ef))
        reps += 1
        ef = max(
            1.3,
            ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)),
        )

    next_review = datetime.now(UTC) + timedelta(days=interval)
    return SrsUpdate(
        easiness_factor=round(ef, 2),
        repetitions=reps,
        interval_days=interval,
        next_review_date=next_review,
    )


def default_srs_state() -> SrsState:
    return SrsState(
        easiness_factor=settings.SRS_DEFAULT_EASINESS_FACTOR,
        repetitions=0,
        interval_days=settings.SRS_DEFAULT_INTERVAL_DAYS,
    )
