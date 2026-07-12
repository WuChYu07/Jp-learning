"""Vocabulary read + SRS review operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

from app.db.supabase import get_supabase_client
from app.models.schemas.common import JlptLevel
from app.models.schemas.vocab import (
    VocabularyDefinitionOut,
    VocabularyOut,
    VocabularySummary,
    VocabularyWriteInput,
)
from app.services.hash_service import vocab_entry_hash
from app.services.srs_service import apply_review, default_srs_state, rating_to_quality
from app.services.text_sanitize import clean_text


@dataclass
class ReviewBatch:
    items: list[VocabularyOut]
    has_more: bool
    next_offset: int
    total: int


class VocabService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def list_vocab(
        self,
        jlpt: JlptLevel | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[VocabularySummary], int]:
        query = self.db.table("vocabularies").select(
            "id, word, reading, jlpt_level", count="exact"
        )
        if jlpt:
            query = query.eq("jlpt_level", jlpt.value)
        result = query.order("word").range(offset, offset + limit - 1).execute()
        rows = result.data or []
        if not rows:
            return [], result.count or 0

        ids = [row["id"] for row in rows]
        defs = (
            self.db.table("vocabulary_definitions")
            .select("vocabulary_id, sort_order, meaning_zh")
            .in_("vocabulary_id", ids)
            .order("sort_order")
            .execute()
        ).data or []
        first_meaning: dict[str, str] = {}
        for d in defs:
            vid = d["vocabulary_id"]
            if vid not in first_meaning and d.get("meaning_zh"):
                first_meaning[vid] = d["meaning_zh"]

        items = [
            VocabularySummary(
                id=UUID(row["id"]),
                word=row["word"],
                reading=row.get("reading"),
                jlpt_level=row["jlpt_level"],
                meaning_zh=first_meaning.get(row["id"]),
            )
            for row in rows
        ]
        return items, result.count or len(items)

    def get_vocab(self, vocabulary_id: UUID) -> VocabularyOut:
        exists = (
            self.db.table("vocabularies")
            .select("id")
            .eq("id", str(vocabulary_id))
            .maybe_single()
            .execute()
        )
        if exists is None or not exists.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary not found")
        return self._load_vocab_out(vocabulary_id)

    def update_vocab(self, vocabulary_id: UUID, payload: VocabularyWriteInput) -> VocabularyOut:
        current = self.get_vocab(vocabulary_id)
        word = clean_text(payload.word) or payload.word.strip()
        reading = clean_text(payload.reading)
        new_hash = vocab_entry_hash(word, reading)

        conflict = (
            self.db.table("vocabularies")
            .select("id")
            .eq("content_hash", new_hash)
            .neq("id", str(vocabulary_id))
            .maybe_single()
            .execute()
        )
        if conflict is not None and conflict.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="已有相同單字與發音的條目。",
            )

        self.db.table("vocabularies").update(
            {
                "word": word,
                "reading": reading,
                "jlpt_level": payload.jlpt_level.value
                if isinstance(payload.jlpt_level, JlptLevel)
                else payload.jlpt_level,
                "content_hash": new_hash,
            }
        ).eq("id", str(vocabulary_id)).execute()

        examples = [
            {
                "japanese": clean_text(ex.japanese) or "",
                "reading": clean_text(ex.reading),
                "chinese": clean_text(ex.chinese),
                "english": None,
                "highlight": ex.highlight,
            }
            for ex in payload.example_sentences
            if (ex.japanese or "").strip()
        ]
        def_update = {
            "meaning_zh": clean_text(payload.meaning_zh) or payload.meaning_zh.strip(),
            "part_of_speech": payload.part_of_speech.value,
            "example_sentences": examples,
            "notes_zh": clean_text(payload.notes_zh),
        }

        if current.definitions:
            (
                self.db.table("vocabulary_definitions")
                .update(def_update)
                .eq("id", str(current.definitions[0].id))
                .execute()
            )
        else:
            self.db.table("vocabulary_definitions").insert(
                {
                    "vocabulary_id": str(vocabulary_id),
                    "sort_order": 0,
                    **def_update,
                }
            ).execute()

        return self._load_vocab_out(vocabulary_id)

    # ── Review batch ────────────────────────────────────────────────────────

    def get_due_reviews(
        self,
        user_id: str | None,
        limit: int = 10,
        offset: int = 0,
    ) -> ReviewBatch:
        if user_id is None:
            return self._due_reviews_anonymous(limit, offset)
        return self._due_reviews_authenticated(user_id, limit, offset)

    def _due_reviews_anonymous(self, limit: int, offset: int) -> ReviewBatch:
        """Single-user mode: paginate all vocab by created_at."""
        count_result = (
            self.db.table("vocabularies")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )
        total = count_result.count or 0

        result = (
            self.db.table("vocabularies")
            .select("id")
            .order("created_at")
            .range(offset, offset + limit - 1)
            .execute()
        )
        ids = [row["id"] for row in result.data or []]
        items = [self._load_vocab_out(UUID(vid)) for vid in ids]
        next_offset = offset + len(ids)

        return ReviewBatch(
            items=items,
            has_more=next_offset < total,
            next_offset=next_offset,
            total=total,
        )

    def _due_reviews_authenticated(
        self, user_id: str, limit: int, offset: int
    ) -> ReviewBatch:
        """
        Multi-user SRS review algorithm:
          1. Overdue reviews (next_review_date <= now), most overdue first
          2. New cards never reviewed, by created_at
        Offset skips within the combined stream.
        """
        now_iso = datetime.now(UTC).isoformat()

        total_vocab = (
            self.db.table("vocabularies")
            .select("id", count="exact")
            .limit(1)
            .execute()
        ).count or 0

        due_rows = (
            self.db.table("user_vocab_progress")
            .select("vocabulary_id")
            .eq("user_id", user_id)
            .lte("next_review_date", now_iso)
            .order("next_review_date")
            .execute()
        ).data or []
        due_ids = [r["vocabulary_id"] for r in due_rows]

        all_progress = (
            self.db.table("user_vocab_progress")
            .select("vocabulary_id")
            .eq("user_id", user_id)
            .execute()
        ).data or []
        seen_ids = {r["vocabulary_id"] for r in all_progress}

        unseen_rows = (
            self.db.table("vocabularies")
            .select("id")
            .order("created_at")
            .execute()
        ).data or []
        new_ids = [r["id"] for r in unseen_rows if r["id"] not in seen_ids]

        combined = due_ids + new_ids
        total_available = len(combined)
        page = combined[offset : offset + limit]
        items = [self._load_vocab_out(UUID(vid)) for vid in page]
        next_offset = offset + len(page)

        return ReviewBatch(
            items=items,
            has_more=next_offset < total_available,
            next_offset=next_offset,
            total=total_vocab,
        )

    # ── Submit review ───────────────────────────────────────────────────────

    def submit_review(self, user_id: str | None, vocabulary_id: UUID, rating: str) -> dict:
        quality = rating_to_quality(rating)
        state = default_srs_state()
        update = apply_review(state, quality)

        if user_id is None:
            return {
                "vocabulary_id": str(vocabulary_id),
                "rating": rating,
                "next_review_date": update.next_review_date.isoformat(),
                "interval_days": update.interval_days,
                "persisted": False,
            }

        progress = (
            self.db.table("user_vocab_progress")
            .select("id, easiness_factor, repetitions, interval_days")
            .eq("user_id", user_id)
            .eq("vocabulary_id", str(vocabulary_id))
            .maybe_single()
            .execute()
        )

        if progress is None or not progress.data:
            update = apply_review(state, quality)
            self.db.table("user_vocab_progress").insert(
                {
                    "user_id": user_id,
                    "vocabulary_id": str(vocabulary_id),
                    "easiness_factor": update.easiness_factor,
                    "repetitions": update.repetitions,
                    "interval_days": update.interval_days,
                    "next_review_date": update.next_review_date.isoformat(),
                    "last_reviewed_at": datetime.now(UTC).isoformat(),
                }
            ).execute()
        else:
            from app.services.srs_service import SrsState

            state = SrsState(
                easiness_factor=progress.data["easiness_factor"],
                repetitions=progress.data["repetitions"],
                interval_days=progress.data["interval_days"],
            )
            update = apply_review(state, quality)
            self.db.table("user_vocab_progress").update(
                {
                    "easiness_factor": update.easiness_factor,
                    "repetitions": update.repetitions,
                    "interval_days": update.interval_days,
                    "next_review_date": update.next_review_date.isoformat(),
                    "last_reviewed_at": datetime.now(UTC).isoformat(),
                }
            ).eq("id", progress.data["id"]).execute()

        return {
            "vocabulary_id": str(vocabulary_id),
            "rating": rating,
            "next_review_date": update.next_review_date.isoformat(),
            "interval_days": update.interval_days,
            "persisted": True,
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _load_vocab_out(self, vocabulary_id: UUID) -> VocabularyOut:
        vocab = (
            self.db.table("vocabularies")
            .select("id, word, reading, jlpt_level")
            .eq("id", str(vocabulary_id))
            .single()
            .execute()
        )
        definitions = (
            self.db.table("vocabulary_definitions")
            .select(
                "id, sort_order, part_of_speech, meaning_zh, meaning_en, "
                "example_sentences, notes_zh"
            )
            .eq("vocabulary_id", str(vocabulary_id))
            .order("sort_order")
            .execute()
        )
        return VocabularyOut(
            id=UUID(vocab.data["id"]),
            word=vocab.data["word"],
            reading=vocab.data.get("reading"),
            jlpt_level=vocab.data["jlpt_level"],
            definitions=[
                VocabularyDefinitionOut(
                    id=UUID(row["id"]),
                    sort_order=row["sort_order"],
                    part_of_speech=row["part_of_speech"],
                    meaning_zh=row["meaning_zh"],
                    meaning_en=row.get("meaning_en"),
                    example_sentences=row.get("example_sentences") or [],
                    notes_zh=row.get("notes_zh"),
                )
                for row in definitions.data or []
            ],
        )


vocab_service = VocabService()
