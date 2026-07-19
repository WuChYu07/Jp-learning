"""Song lyrics learning endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_effective_user_id
from app.services.songs.song_service import (
    SongCandidateOut,
    SongHistoryItem,
    SongListItem,
    SongOut,
    SongSelectRequest,
    song_service,
)

router = APIRouter()


@router.get("/search", response_model=list[SongCandidateOut])
def search_songs(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=12, ge=1, le=30),
) -> list[SongCandidateOut]:
    return song_service.search(q, limit=limit)


@router.get("/recommend", response_model=list[SongCandidateOut])
def recommend_songs(
    limit: int = Query(default=10, ge=1, le=30),
) -> list[SongCandidateOut]:
    return song_service.recommend(limit=limit)


@router.get("", response_model=list[SongListItem])
def list_songs(
    limit: int = Query(default=30, ge=1, le=100),
) -> list[SongListItem]:
    return song_service.list_cached(limit=limit)


@router.get("/history", response_model=list[SongHistoryItem])
def song_history(
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
    limit: int = Query(default=15, ge=1, le=50),
) -> list[SongHistoryItem]:
    return song_service.list_history(user_id=user_id, limit=limit)


@router.post("/select", response_model=SongOut)
def select_song(
    body: SongSelectRequest,
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
) -> SongOut:
    return song_service.select(body, user_id=user_id)


@router.get("/{song_id}", response_model=SongOut)
def get_song(
    song_id: str,
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
) -> SongOut:
    return song_service.get_song(song_id, user_id=user_id)
