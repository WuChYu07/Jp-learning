"""Song library: search / recommend / select / cache / enrich."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.core.config import settings
from app.db.supabase import get_supabase_client
from app.services.owner_service import ensure_owner_user
from app.services.songs.enrichment_service import song_enrichment_service
from app.services.songs.marumaru_client import (
    MarumaruCandidate,
    MarumaruLine,
    extract_marumaru_id,
    fetch_song,
    parse_pasted_lyrics,
    play_url,
    recommend as marumaru_recommend,
    search_listings,
)

logger = logging.getLogger(__name__)

SongStatus = Literal["pending", "lyrics_ready", "enriching", "enriched", "failed"]


class SongCandidateOut(BaseModel):
    marumaru_id: str
    title: str
    artist: str = ""
    source_url: str = ""
    release_date: str | None = None
    category: str | None = None
    cached_song_id: UUID | None = None
    cached_status: str | None = None


class SongLineOut(BaseModel):
    id: UUID | None = None
    line_no: int
    text_ja: str
    text_zh: str | None = None
    grammar_zh: str | None = None
    note_zh: str | None = None
    jlpt_hints: list[str] = Field(default_factory=list)


class SongOut(BaseModel):
    id: UUID
    title: str
    artist: str
    release_date: str | None = None
    marumaru_id: str | None = None
    source_url: str | None = None
    category: str | None = None
    difficulty: int | None = None
    youtube_url: str | None = None
    status: str
    lyrics_source: str | None = None
    zh_source: str | None = None
    overview_zh: str | None = None
    error_message: str | None = None
    fetched_at: str | None = None
    enriched_at: str | None = None
    created_at: str | None = None
    lines: list[SongLineOut] = Field(default_factory=list)


class SongSelectRequest(BaseModel):
    marumaru_id: str | None = None
    source_url: str | None = None
    title: str | None = None
    artist: str | None = None
    # Paste fallback
    paste_ja: str | None = None
    paste_zh: str | None = None
    enrich: bool = True


class SongListItem(BaseModel):
    id: UUID
    title: str
    artist: str
    status: str
    marumaru_id: str | None = None
    source_url: str | None = None
    enriched_at: str | None = None
    updated_at: str | None = None
    line_count: int = 0


class SongHistoryItem(BaseModel):
    song_id: UUID
    title: str
    artist: str
    status: str
    last_opened_at: str


class SongService:
    def __init__(self) -> None:
        self._db: Client | None = None

    @property
    def db(self) -> Client:
        if self._db is None:
            self._db = get_supabase_client()
        return self._db

    def search(self, q: str, *, limit: int = 12) -> list[SongCandidateOut]:
        q = (q or "").strip()
        if not q:
            raise HTTPException(status_code=400, detail="請輸入歌名或歌手")

        candidates: list[MarumaruCandidate] = []

        # Direct play URL / bare marumaru id
        mid = extract_marumaru_id(q)
        if mid and ("play-" in q.lower() or "marumaru" in q.lower() or "://" in q or mid == q):
            candidates.append(
                MarumaruCandidate(
                    marumaru_id=mid,
                    title=mid,
                    artist="",
                    source_url=play_url(mid),
                )
            )
            # For pure URL/id queries, still try listings if title-like text remains
            if "://" in q or "play-" in q.lower() or mid == q:
                # Attempt to upgrade title from cache / leave as id until select
                return self._annotate_cache(candidates[:limit])

        try:
            candidates.extend(search_listings(q, limit=max(limit, 20)))
        except Exception as exc:
            logger.exception("MARUMARU search failed")
            if not candidates:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"無法搜尋 MARUMARU：{exc}",
                ) from exc

        seen: set[str] = set()
        uniq: list[MarumaruCandidate] = []
        for c in candidates:
            if c.marumaru_id in seen:
                continue
            seen.add(c.marumaru_id)
            uniq.append(c)
        return self._annotate_cache(uniq[:limit])

    def recommend(self, *, limit: int = 10) -> list[SongCandidateOut]:
        try:
            items = marumaru_recommend(limit=limit)
        except Exception as exc:
            logger.exception("MARUMARU recommend failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"無法取得推薦歌曲：{exc}",
            ) from exc
        return self._annotate_cache(items)

    def list_cached(self, *, limit: int = 30) -> list[SongListItem]:
        try:
            rows = (
                self.db.table("songs")
                .select("id,title,artist,status,marumaru_id,source_url,enriched_at,updated_at")
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            ).data or []
        except Exception as exc:
            logger.exception("songs list failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="無法讀取曲庫。請確認已執行 migrations/015_songs.sql。",
            ) from exc

        out: list[SongListItem] = []
        for row in rows:
            line_count = 0
            try:
                lc = (
                    self.db.table("song_lines")
                    .select("id", count="exact")
                    .eq("song_id", row["id"])
                    .execute()
                )
                line_count = lc.count or 0
            except Exception:
                line_count = 0
            out.append(
                SongListItem(
                    id=row["id"],
                    title=row.get("title") or "",
                    artist=row.get("artist") or "",
                    status=row.get("status") or "pending",
                    marumaru_id=row.get("marumaru_id"),
                    source_url=row.get("source_url"),
                    enriched_at=row.get("enriched_at"),
                    updated_at=row.get("updated_at"),
                    line_count=line_count,
                )
            )
        return out

    def list_history(self, *, user_id: str | None, limit: int = 15) -> list[SongHistoryItem]:
        owner = user_id or settings.SINGLETON_OWNER_ID
        try:
            rows = (
                self.db.table("user_song_history")
                .select("song_id,last_opened_at")
                .eq("user_id", owner)
                .order("last_opened_at", desc=True)
                .limit(limit)
                .execute()
            ).data or []
        except Exception:
            logger.exception("song history list failed")
            return []
        if not rows:
            return []

        song_ids = [r["song_id"] for r in rows]
        songs_map: dict[str, dict] = {}
        try:
            songs = (
                self.db.table("songs")
                .select("id,title,artist,status")
                .in_("id", song_ids)
                .execute()
            ).data or []
            songs_map = {str(s["id"]): s for s in songs}
        except Exception:
            logger.exception("song history songs fetch failed")
            return []

        out: list[SongHistoryItem] = []
        for r in rows:
            song = songs_map.get(str(r["song_id"]))
            if not song:
                continue
            out.append(
                SongHistoryItem(
                    song_id=r["song_id"],
                    title=song.get("title") or "",
                    artist=song.get("artist") or "",
                    status=song.get("status") or "pending",
                    last_opened_at=r.get("last_opened_at") or "",
                )
            )
        return out

    def get_song(self, song_id: str, *, user_id: str | None = None) -> SongOut:
        row = self._get_song_row(song_id)
        lines = self._get_lines(song_id)
        self._touch_history(user_id, song_id)
        return self._to_song_out(row, lines)

    def select(self, body: SongSelectRequest, *, user_id: str | None) -> SongOut:
        ensure_owner_user()

        # Paste path
        if body.paste_ja and body.paste_ja.strip():
            return self._select_paste(body, user_id=user_id)

        mid = extract_marumaru_id(body.marumaru_id or body.source_url or "")
        if not mid:
            raise HTTPException(
                status_code=400,
                detail="請提供 marumaru_id／play 網址，或貼上日文歌詞（paste_ja）。",
            )

        # Cache hit
        existing = self._find_by_marumaru(mid)
        if existing and existing.get("status") == "enriched":
            sid = str(existing["id"])
            self._touch_history(user_id, sid)
            return self._to_song_out(existing, self._get_lines(sid))

        # Re-enrich failed / partial
        if existing and existing.get("status") in ("lyrics_ready", "failed", "enriching", "pending"):
            song_id = str(existing["id"])
            if existing.get("status") != "lyrics_ready":
                self._fetch_and_store_marumaru(mid, song_id=song_id, body=body)
            if body.enrich:
                self._run_enrich(song_id)
            row = self._get_song_row(song_id)
            self._touch_history(user_id, song_id)
            return self._to_song_out(row, self._get_lines(song_id))

        # New song
        song_id = self._fetch_and_store_marumaru(mid, song_id=None, body=body)
        if body.enrich:
            self._run_enrich(song_id)
        row = self._get_song_row(song_id)
        self._touch_history(user_id, song_id)
        return self._to_song_out(row, self._get_lines(song_id))

    # ── internals ──────────────────────────────────────────────

    def _annotate_cache(self, items: list[MarumaruCandidate]) -> list[SongCandidateOut]:
        cache_map: dict[str, dict] = {}
        ids = [c.marumaru_id for c in items]
        if ids:
            try:
                rows = (
                    self.db.table("songs")
                    .select("id,marumaru_id,status")
                    .in_("marumaru_id", ids)
                    .execute()
                ).data or []
                for r in rows:
                    if r.get("marumaru_id"):
                        cache_map[r["marumaru_id"]] = r
            except Exception:
                pass
        out: list[SongCandidateOut] = []
        for c in items:
            hit = cache_map.get(c.marumaru_id)
            out.append(
                SongCandidateOut(
                    marumaru_id=c.marumaru_id,
                    title=c.title,
                    artist=c.artist,
                    source_url=c.source_url or play_url(c.marumaru_id),
                    release_date=c.release_date,
                    category=c.category,
                    cached_song_id=hit["id"] if hit else None,
                    cached_status=hit.get("status") if hit else None,
                )
            )
        return out

    def _select_paste(self, body: SongSelectRequest, *, user_id: str | None) -> SongOut:
        lines = parse_pasted_lyrics(body.paste_ja or "", body.paste_zh)
        if not lines:
            raise HTTPException(status_code=400, detail="貼上的歌詞是空的")

        title = (body.title or "").strip() or "自訂歌詞"
        artist = (body.artist or "").strip()
        zh_source = "paste" if body.paste_zh and body.paste_zh.strip() else None

        row = {
            "title": title,
            "artist": artist,
            "marumaru_id": None,
            "source_url": None,
            "status": "lyrics_ready",
            "lyrics_source": "paste",
            "zh_source": zh_source,
            "fetched_at": datetime.now(UTC).isoformat(),
            "error_message": None,
        }
        try:
            inserted = self.db.table("songs").insert(row).execute()
            song = (inserted.data or [None])[0]
        except Exception as exc:
            logger.exception("paste song insert failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="無法寫入曲庫。請確認已執行 migrations/015_songs.sql。",
            ) from exc
        if not song:
            raise HTTPException(status_code=500, detail="Failed to create song")

        song_id = str(song["id"])
        self._replace_lines(song_id, lines)

        # Fill missing ZH via AI
        if not zh_source:
            self._fill_zh_ai(song_id)
            self.db.table("songs").update({"zh_source": "ai"}).eq("id", song_id).execute()

        if body.enrich:
            self._run_enrich(song_id)

        row = self._get_song_row(song_id)
        self._touch_history(user_id, song_id)
        return self._to_song_out(row, self._get_lines(song_id))

    def _fetch_and_store_marumaru(
        self,
        mid: str,
        *,
        song_id: str | None,
        body: SongSelectRequest,
    ) -> str:
        try:
            detail = fetch_song(mid)
        except Exception as exc:
            logger.exception("MARUMARU fetch failed for %s", mid)
            if song_id:
                self.db.table("songs").update(
                    {
                        "status": "failed",
                        "error_message": f"抓取歌詞失敗：{exc}",
                    }
                ).eq("id", song_id).execute()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"無法從 MARUMARU 取得歌詞：{exc}",
            ) from exc

        if not detail.lines:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="MARUMARU 頁面沒有解析到歌詞，可改用貼上歌詞。",
            )

        title = (body.title or detail.title or "").strip() or mid
        artist = (body.artist or detail.artist or "").strip()
        zh_source = "marumaru" if detail.has_chinese else None
        payload: dict[str, Any] = {
            "title": title,
            "artist": artist,
            "marumaru_id": mid,
            "source_url": detail.source_url,
            "category": detail.category,
            "youtube_url": detail.youtube_url,
            "release_date": detail.release_date.isoformat() if detail.release_date else None,
            "status": "lyrics_ready",
            "lyrics_source": "marumaru",
            "zh_source": zh_source,
            "fetched_at": datetime.now(UTC).isoformat(),
            "error_message": None,
        }

        try:
            if song_id:
                self.db.table("songs").update(payload).eq("id", song_id).execute()
                sid = song_id
            else:
                inserted = self.db.table("songs").insert(payload).execute()
                song = (inserted.data or [None])[0]
                if not song:
                    raise RuntimeError("insert returned empty")
                sid = str(song["id"])
        except HTTPException:
            raise
        except Exception as exc:
            # Unique conflict → fetch existing
            existing = self._find_by_marumaru(mid)
            if existing:
                sid = str(existing["id"])
                self.db.table("songs").update(payload).eq("id", sid).execute()
            else:
                logger.exception("song insert failed")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="無法寫入曲庫。請確認已執行 migrations/015_songs.sql。",
                ) from exc

        self._replace_lines(sid, detail.lines)

        if not detail.has_chinese:
            self._fill_zh_ai(sid)
            self.db.table("songs").update({"zh_source": "ai"}).eq("id", sid).execute()

        return sid

    def _fill_zh_ai(self, song_id: str) -> None:
        lines = self._get_lines(song_id)
        payload = [
            {"line_no": ln["line_no"], "text_ja": ln.get("text_ja"), "text_zh": ln.get("text_zh")}
            for ln in lines
        ]
        translated = song_enrichment_service.translate_missing_zh(payload)
        for no, zh in translated.items():
            self.db.table("song_lines").update({"text_zh": zh}).eq("song_id", song_id).eq(
                "line_no", no
            ).execute()

    def _run_enrich(self, song_id: str) -> None:
        self.db.table("songs").update({"status": "enriching", "error_message": None}).eq(
            "id", song_id
        ).execute()
        row = self._get_song_row(song_id)
        lines = self._get_lines(song_id)
        self._generate_overview(song_id, row, lines)
        try:
            enriched = song_enrichment_service.enrich_lines(
                title=row.get("title") or "",
                artist=row.get("artist") or "",
                lines=[
                    {
                        "line_no": ln["line_no"],
                        "text_ja": ln.get("text_ja"),
                        "text_zh": ln.get("text_zh"),
                    }
                    for ln in lines
                ],
            )
            for no, data in enriched.items():
                self.db.table("song_lines").update(
                    {
                        "grammar_zh": data.get("grammar_zh"),
                        "note_zh": data.get("note_zh"),
                        "jlpt_hints": data.get("jlpt_hints") or [],
                    }
                ).eq("song_id", song_id).eq("line_no", no).execute()
            self.db.table("songs").update(
                {
                    "status": "enriched",
                    "enriched_at": datetime.now(UTC).isoformat(),
                    "error_message": None,
                }
            ).eq("id", song_id).execute()
        except HTTPException as exc:
            self.db.table("songs").update(
                {
                    "status": "failed",
                    "error_message": str(exc.detail),
                }
            ).eq("id", song_id).execute()
            raise
        except Exception as exc:
            logger.exception("enrich failed for %s", song_id)
            self.db.table("songs").update(
                {
                    "status": "failed",
                    "error_message": str(exc),
                }
            ).eq("id", song_id).execute()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI 解釋失敗：{exc}",
            ) from exc

    def _generate_overview(self, song_id: str, row: dict, lines: list[dict]) -> None:
        """Generate song-level intro; skip silently if already present or column missing."""
        if (row.get("overview_zh") or "").strip():
            return
        overview = song_enrichment_service.generate_overview(
            title=row.get("title") or "",
            artist=row.get("artist") or "",
            release_date=row.get("release_date"),
            category=row.get("category"),
            lines=[
                {"line_no": ln["line_no"], "text_ja": ln.get("text_ja")}
                for ln in lines
            ],
        )
        if not overview:
            return
        try:
            self.db.table("songs").update({"overview_zh": overview}).eq("id", song_id).execute()
        except Exception:
            # Column missing (016 not applied yet) — feature degrades gracefully.
            logger.warning(
                "overview_zh update failed; run migrations/016_song_overview.sql",
                exc_info=True,
            )

    def _replace_lines(self, song_id: str, lines: list[MarumaruLine]) -> None:
        self.db.table("song_lines").delete().eq("song_id", song_id).execute()
        rows = [
            {
                "song_id": song_id,
                "line_no": ln.line_no,
                "text_ja": ln.text_ja,
                "text_zh": ln.text_zh,
                "grammar_zh": None,
                "note_zh": None,
                "jlpt_hints": [],
            }
            for ln in lines
        ]
        if rows:
            # chunk inserts
            for i in range(0, len(rows), 50):
                self.db.table("song_lines").insert(rows[i : i + 50]).execute()

    def _find_by_marumaru(self, mid: str) -> dict | None:
        try:
            rows = (
                self.db.table("songs").select("*").eq("marumaru_id", mid).limit(1).execute()
            ).data or []
            return rows[0] if rows else None
        except Exception:
            return None

    def _get_song_row(self, song_id: str) -> dict:
        try:
            rows = (
                self.db.table("songs").select("*").eq("id", song_id).limit(1).execute()
            ).data or []
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="無法讀取曲庫。請確認已執行 migrations/015_songs.sql。",
            ) from exc
        if not rows:
            raise HTTPException(status_code=404, detail="找不到這首歌")
        return rows[0]

    def _get_lines(self, song_id: str) -> list[dict]:
        try:
            return (
                self.db.table("song_lines")
                .select("*")
                .eq("song_id", song_id)
                .order("line_no")
                .execute()
            ).data or []
        except Exception:
            return []

    def _touch_history(self, user_id: str | None, song_id: str) -> None:
        try:
            ensure_owner_user()
            now = datetime.now(UTC).isoformat()
            owner = user_id or settings.SINGLETON_OWNER_ID
            existing = (
                self.db.table("user_song_history")
                .select("id")
                .eq("user_id", owner)
                .eq("song_id", song_id)
                .limit(1)
                .execute()
            ).data or []
            if existing:
                self.db.table("user_song_history").update({"last_opened_at": now}).eq(
                    "id", existing[0]["id"]
                ).execute()
            else:
                self.db.table("user_song_history").insert(
                    {"user_id": owner, "song_id": song_id, "last_opened_at": now}
                ).execute()
        except Exception:
            logger.debug("user_song_history touch skipped", exc_info=True)

    def _to_song_out(self, row: dict, lines: list[dict]) -> SongOut:
        return SongOut(
            id=row["id"],
            title=row.get("title") or "",
            artist=row.get("artist") or "",
            release_date=row.get("release_date"),
            marumaru_id=row.get("marumaru_id"),
            source_url=row.get("source_url"),
            category=row.get("category"),
            difficulty=row.get("difficulty"),
            youtube_url=row.get("youtube_url"),
            status=row.get("status") or "pending",
            lyrics_source=row.get("lyrics_source"),
            zh_source=row.get("zh_source"),
            overview_zh=row.get("overview_zh"),
            error_message=row.get("error_message"),
            fetched_at=row.get("fetched_at"),
            enriched_at=row.get("enriched_at"),
            created_at=row.get("created_at"),
            lines=[
                SongLineOut(
                    id=ln.get("id"),
                    line_no=ln["line_no"],
                    text_ja=ln.get("text_ja") or "",
                    text_zh=ln.get("text_zh"),
                    grammar_zh=ln.get("grammar_zh"),
                    note_zh=ln.get("note_zh"),
                    jlpt_hints=list(ln.get("jlpt_hints") or []),
                )
                for ln in lines
            ],
        )


song_service = SongService()
