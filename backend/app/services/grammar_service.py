"""Grammar read/write operations."""

from __future__ import annotations

from datetime import datetime, timezone
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
from app.services.text_sanitize import clean_text
from app.models.schemas.links import LinkEntityType
from app.services.semantic_link_service import semantic_link_service


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
        semantic_link_service.sync_entity_safe(LinkEntityType.GRAMMAR, grammar_id)
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
        semantic_link_service.sync_entity_safe(LinkEntityType.GRAMMAR, grammar_id)
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
