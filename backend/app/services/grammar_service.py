"""Grammar read/write operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

from app.db.supabase import get_supabase_client
from app.models.schemas.common import JlptLevel, SourceType, SupplementaryBlock
from app.models.schemas.grammar import (
    GrammarOut,
    GrammarSummary,
    GrammarUsageOut,
    GrammarUsageWrite,
    GrammarWriteInput,
)
from app.services.grammar_enrichment_utils import needs_image_enrichment
from app.services.hash_service import grammar_entry_hash
from app.services.score_service import score_service
from app.services.srs_service import apply_review, default_srs_state, rating_to_quality
from app.services.text_sanitize import clean_text


@dataclass
class GrammarReviewBatch:
    items: list[GrammarOut]
    has_more: bool
    next_offset: int
    total: int


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _usage_rows_from_write(grammar_id: UUID, usages: list[GrammarUsageWrite]) -> list[dict]:
    rows: list[dict] = []
    for index, usage in enumerate(usages):
        meaning_zh = clean_text(usage.meaning_zh)
        meaning_blocks = (
            [{"text": meaning_zh, "variant": "default"}] if meaning_zh else []
        )
        rows.append(
            {
                "grammar_id": str(grammar_id),
                "sort_order": index,
                "semantic_concept": clean_text(usage.semantic_concept) or "（未命名用法）",
                "connection_rule": clean_text(usage.connection_rule) or "",
                "meaning_zh": meaning_zh,
                "meaning_en": None,
                "meaning_blocks": meaning_blocks,
                "example_sentences": [
                    {
                        "japanese": ex.japanese,
                        "reading": ex.reading,
                        "chinese": ex.chinese,
                        "highlight": getattr(ex, "highlight", None),
                    }
                    for ex in usage.example_sentences
                    if (ex.japanese or "").strip()
                ],
            }
        )
    return rows


class GrammarService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def list_grammar(
        self,
        jlpt: JlptLevel | None = None,
        limit: int = 50,
        offset: int = 0,
        q: str | None = None,
    ) -> tuple[list[GrammarSummary], int]:
        query = (
            self.db.table("grammars")
            .select(
                "id, grammar_point, jlpt_level, image_urls, sync_status, manual_edited_at",
                count="exact",
            )
            .neq("sync_status", "archived")
        )
        if jlpt:
            query = query.ilike("jlpt_level", f"%{jlpt.value}%")
        needle = (q or "").strip()
        if needle:
            safe = needle.replace(",", " ").replace("%", "")
            query = query.ilike("grammar_point", f"%{safe}%")
        result = query.order("grammar_point").range(offset, offset + limit - 1).execute()
        rows = result.data or []
        if not rows:
            return [], result.count or 0

        ids = [row["id"] for row in rows]
        usage_rows = (
            self.db.table("grammar_usages")
            .select("grammar_id")
            .in_("grammar_id", ids)
            .execute()
        ).data or []
        usage_counts: dict[str, int] = {}
        for u in usage_rows:
            gid = u["grammar_id"]
            usage_counts[gid] = usage_counts.get(gid, 0) + 1

        items: list[GrammarSummary] = []
        for row in rows:
            image_urls = row.get("image_urls") or []
            items.append(
                GrammarSummary(
                    id=UUID(row["id"]),
                    grammar_point=row["grammar_point"],
                    jlpt_level=row["jlpt_level"],
                    usage_count=usage_counts.get(row["id"], 0),
                    image_count=len(image_urls) if isinstance(image_urls, list) else 0,
                    sync_status=row.get("sync_status") or "synced",
                    needs_enrichment=needs_image_enrichment(image_urls=image_urls),
                    manual_edited=bool(row.get("manual_edited_at")),
                )
            )
        return items, result.count or len(items)

    def get_grammar(self, grammar_id: UUID) -> GrammarOut:
        exists = (
            self.db.table("grammars")
            .select("id, sync_status")
            .eq("id", str(grammar_id))
            .maybe_single()
            .execute()
        )
        if exists is None or not exists.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grammar not found")
        if exists.data.get("sync_status") == "archived":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grammar not found")
        return self._load_grammar_out(grammar_id)

    def random_grammar(
        self,
        user_id: str | None,
        *,
        exclude_id: UUID | None = None,
        jlpt: JlptLevel | None = None,
    ) -> GrammarOut:
        query = (
            self.db.table("grammars")
            .select("id")
            .neq("sync_status", "archived")
        )
        if jlpt:
            query = query.eq("jlpt_level", jlpt.value)
        rows = (query.execute()).data or []
        ids = [r["id"] for r in rows]
        if not ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No grammar available",
            )

        exclude = {str(exclude_id)} if exclude_id else set()
        score_map = (
            score_service.grammar_score_map_for_user(user_id) if user_id else {}
        )
        picked = score_service.weighted_sample_ids(
            ids, score_map, count=1, exclude_ids=exclude
        )
        if not picked and exclude:
            picked = score_service.weighted_sample_ids(ids, score_map, count=1)
        if not picked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No grammar available",
            )
        return self.get_grammar(UUID(picked[0]))

    def create_grammar(self, payload: GrammarWriteInput) -> GrammarOut:
        point = clean_text(payload.grammar_point) or payload.grammar_point.strip()
        entry_hash = grammar_entry_hash(point)
        conflict = (
            self.db.table("grammars")
            .select("id, sync_status")
            .eq("content_hash", entry_hash)
            .maybe_single()
            .execute()
        )
        if conflict is not None and conflict.data and conflict.data.get("sync_status") != "archived":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="已有相同標題的文法，請改用編輯，或先刪除舊的再新增。",
            )

        now = _now_iso()
        try:
            inserted = (
                self.db.table("grammars")
                .insert(
                    {
                        "grammar_point": point,
                        "jlpt_level": payload.jlpt_level,
                        "content_hash": entry_hash,
                        "source_type": SourceType.MANUAL.value,
                        "image_urls": [],
                        "supplementary_blocks": [],
                        "sync_status": "synced",
                        "manual_edited_at": now,
                    }
                )
                .execute()
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="已有相同標題的文法，請改用編輯，或先刪除舊的再新增。",
            ) from exc
        if not inserted.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create grammar",
            )
        grammar_id = UUID(inserted.data[0]["id"])
        rows = _usage_rows_from_write(grammar_id, payload.usages)
        if rows:
            self.db.table("grammar_usages").insert(rows).execute()
        return self._load_grammar_out(grammar_id)

    def update_grammar(self, grammar_id: UUID, payload: GrammarWriteInput) -> GrammarOut:
        existing = (
            self.db.table("grammars")
            .select("id, sync_status")
            .eq("id", str(grammar_id))
            .maybe_single()
            .execute()
        )
        if existing is None or not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grammar not found")
        if existing.data.get("sync_status") == "archived":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grammar not found")

        point = clean_text(payload.grammar_point) or payload.grammar_point.strip()
        now = _now_iso()
        self.db.table("grammars").update(
            {
                "grammar_point": point,
                "jlpt_level": payload.jlpt_level,
                "content_hash": grammar_entry_hash(point),
                "manual_edited_at": now,
                "sync_status": "synced",
            }
        ).eq("id", str(grammar_id)).execute()

        self.db.table("grammar_usages").delete().eq("grammar_id", str(grammar_id)).execute()
        rows = _usage_rows_from_write(grammar_id, payload.usages)
        if rows:
            self.db.table("grammar_usages").insert(rows).execute()
        return self._load_grammar_out(grammar_id)

    def archive_grammar(self, grammar_id: UUID) -> None:
        existing = (
            self.db.table("grammars")
            .select("id, sync_status, content_hash")
            .eq("id", str(grammar_id))
            .maybe_single()
            .execute()
        )
        if existing is None or not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grammar not found")
        if existing.data.get("sync_status") == "archived":
            return
        # Free unique content_hash so a corrected manual entry can reuse the title.
        old_hash = existing.data.get("content_hash") or str(grammar_id)
        self.db.table("grammars").update(
            {
                "sync_status": "archived",
                "manual_edited_at": _now_iso(),
                "content_hash": f"archived:{grammar_id}:{old_hash}",
            }
        ).eq("id", str(grammar_id)).execute()

    def get_due_reviews(
        self,
        user_id: str | None,
        limit: int = 10,
        offset: int = 0,
    ) -> GrammarReviewBatch:
        if user_id is None:
            return self._due_reviews_anonymous(limit, offset)
        return self._due_reviews_authenticated(user_id, limit, offset)

    def _due_reviews_anonymous(self, limit: int, offset: int) -> GrammarReviewBatch:
        count_result = (
            self.db.table("grammars")
            .select("id", count="exact")
            .neq("sync_status", "archived")
            .limit(1)
            .execute()
        )
        total = count_result.count or 0
        result = (
            self.db.table("grammars")
            .select("id")
            .neq("sync_status", "archived")
            .order("created_at")
            .range(offset, offset + limit - 1)
            .execute()
        )
        ids = [row["id"] for row in result.data or []]
        items = [self._load_grammar_out(UUID(gid)) for gid in ids]
        next_offset = offset + len(ids)
        return GrammarReviewBatch(
            items=items,
            has_more=next_offset < total,
            next_offset=next_offset,
            total=total,
        )

    def _due_reviews_authenticated(
        self, user_id: str, limit: int, offset: int
    ) -> GrammarReviewBatch:
        from app.services.review_queue import build_mixed_review_queue, daily_seed

        now_iso = datetime.now(UTC).isoformat()
        total_grammar = (
            self.db.table("grammars")
            .select("id", count="exact")
            .neq("sync_status", "archived")
            .limit(1)
            .execute()
        ).count or 0

        due_rows = (
            self.db.table("user_grammar_progress")
            .select("grammar_id")
            .eq("user_id", user_id)
            .lte("next_review_date", now_iso)
            .order("next_review_date")
            .execute()
        ).data or []
        due_ids = [r["grammar_id"] for r in due_rows]

        all_progress = (
            self.db.table("user_grammar_progress")
            .select("grammar_id, review_score")
            .eq("user_id", user_id)
            .execute()
        ).data or []
        seen_ids = {r["grammar_id"] for r in all_progress}
        score_map = {
            r["grammar_id"]: float(r.get("review_score") or 0) for r in all_progress
        }

        unseen_rows = (
            self.db.table("grammars")
            .select("id")
            .neq("sync_status", "archived")
            .order("created_at")
            .execute()
        ).data or []
        new_ids = [r["id"] for r in unseen_rows if r["id"] not in seen_ids]

        combined = build_mixed_review_queue(
            due_ids=due_ids,
            new_ids=new_ids,
            score_by_id=score_map,
            seed=daily_seed(user_id, "grammar"),
        )
        total_available = len(combined)
        page = combined[offset : offset + limit]
        items = [self._load_grammar_out(UUID(gid)) for gid in page]
        next_offset = offset + len(page)
        return GrammarReviewBatch(
            items=items,
            has_more=next_offset < total_available,
            next_offset=next_offset,
            total=total_grammar,
        )

    def submit_review(self, user_id: str | None, grammar_id: UUID, rating: str) -> dict:
        self.get_grammar(grammar_id)
        quality = rating_to_quality(rating)
        state = default_srs_state()
        update = apply_review(state, quality)

        if user_id is None:
            return {
                "grammar_id": str(grammar_id),
                "rating": rating,
                "next_review_date": update.next_review_date.isoformat(),
                "interval_days": update.interval_days,
                "persisted": False,
                "review_score": 0,
                "review_points": 0,
                "score_delta": 0,
                "points_delta": 0,
            }

        progress = (
            self.db.table("user_grammar_progress")
            .select(
                "id, easiness_factor, repetitions, interval_days, "
                "review_score, times_reviewed"
            )
            .eq("user_id", user_id)
            .eq("grammar_id", str(grammar_id))
            .maybe_single()
            .execute()
        )

        if progress is None or not progress.data:
            update = apply_review(state, quality)
            self.db.table("user_grammar_progress").insert(
                {
                    "user_id": user_id,
                    "grammar_id": str(grammar_id),
                    "easiness_factor": update.easiness_factor,
                    "repetitions": update.repetitions,
                    "interval_days": update.interval_days,
                    "next_review_date": update.next_review_date.isoformat(),
                    "last_reviewed_at": datetime.now(UTC).isoformat(),
                }
            ).execute()
            progress_row = None
        else:
            from app.services.srs_service import SrsState

            state = SrsState(
                easiness_factor=progress.data["easiness_factor"],
                repetitions=progress.data["repetitions"],
                interval_days=progress.data["interval_days"],
            )
            update = apply_review(state, quality)
            self.db.table("user_grammar_progress").update(
                {
                    "easiness_factor": update.easiness_factor,
                    "repetitions": update.repetitions,
                    "interval_days": update.interval_days,
                    "next_review_date": update.next_review_date.isoformat(),
                    "last_reviewed_at": datetime.now(UTC).isoformat(),
                }
            ).eq("id", progress.data["id"]).execute()
            progress_row = progress.data

        if progress_row is None:
            refreshed = (
                self.db.table("user_grammar_progress")
                .select("id, review_score, times_reviewed")
                .eq("user_id", user_id)
                .eq("grammar_id", str(grammar_id))
                .maybe_single()
                .execute()
            )
            progress_row = refreshed.data if refreshed is not None else None

        snap = score_service.apply_grammar_rating(
            user_id, grammar_id, rating, progress_row=progress_row
        )
        from app.services.review_activity_service import review_activity_service

        streak_days = review_activity_service.record_review(user_id)
        return {
            "grammar_id": str(grammar_id),
            "rating": rating,
            "next_review_date": update.next_review_date.isoformat(),
            "interval_days": update.interval_days,
            "persisted": True,
            "review_score": snap.review_score,
            "review_points": snap.review_points,
            "score_delta": snap.score_delta,
            "points_delta": snap.points_delta,
            "streak_days": streak_days,
        }

    def _load_grammar_out(self, grammar_id: UUID) -> GrammarOut:
        grammar = (
            self.db.table("grammars")
            .select(
                "id, grammar_point, jlpt_level, image_urls, sync_status, "
                "supplementary_blocks, manual_edited_at"
            )
            .eq("id", str(grammar_id))
            .single()
            .execute()
        )
        usages = (
            self.db.table("grammar_usages")
            .select(
                "id, sort_order, semantic_concept, connection_rule, "
                "meaning_zh, meaning_en, meaning_blocks, example_sentences"
            )
            .eq("grammar_id", str(grammar_id))
            .order("sort_order")
            .execute()
        )
        usage_rows = [
            GrammarUsageOut(
                id=UUID(row["id"]),
                sort_order=row["sort_order"],
                semantic_concept=row["semantic_concept"],
                connection_rule=row["connection_rule"],
                meaning_zh=row.get("meaning_zh"),
                meaning_en=row.get("meaning_en"),
                meaning_blocks=row.get("meaning_blocks") or [],
                example_sentences=row.get("example_sentences") or [],
            )
            for row in usages.data or []
        ]
        image_urls = grammar.data.get("image_urls") or []
        sync_status = grammar.data.get("sync_status") or "synced"
        grammar_point = grammar.data["grammar_point"]
        supplementary_blocks = [
            SupplementaryBlock.model_validate(block)
            for block in (grammar.data.get("supplementary_blocks") or [])
        ]
        return GrammarOut(
            id=UUID(grammar.data["id"]),
            grammar_point=grammar_point,
            jlpt_level=grammar.data["jlpt_level"],
            image_urls=image_urls,
            supplementary_blocks=supplementary_blocks,
            sync_status=sync_status,
            needs_enrichment=needs_image_enrichment(image_urls=image_urls),
            manual_edited=bool(grammar.data.get("manual_edited_at")),
            usages=usage_rows,
        )


grammar_service = GrammarService()
