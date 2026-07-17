"""Auto-create same_meaning links via embedding similarity (JLPT-agnostic)."""

from __future__ import annotations

import logging
from uuid import UUID

from supabase import Client

from app.core.config import settings
from app.db.supabase import get_supabase_client
from app.models.schemas.links import (
    ContentLinkCreate,
    LinkEntityType,
    LinkRelationType,
)
from app.services.embedding_service import (
    build_grammar_source_text,
    build_vocab_source_text,
    content_text_hash,
    embedding_service,
)
from app.services.link_service import link_service

logger = logging.getLogger(__name__)


class SemanticLinkService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def sync_grammar(self, grammar_id: UUID, *, force: bool = False) -> dict:
        row = (
            self.db.table("grammars")
            .select("id, grammar_point, sync_status")
            .eq("id", str(grammar_id))
            .maybe_single()
            .execute()
        )
        if row is None or not row.data or row.data.get("sync_status") == "archived":
            return {"ok": False, "reason": "not_found"}

        usages = (
            self.db.table("grammar_usages")
            .select("semantic_concept, meaning_zh, meaning_blocks")
            .eq("grammar_id", str(grammar_id))
            .order("sort_order")
            .execute()
        ).data or []

        source_text = build_grammar_source_text(row.data["grammar_point"], usages)
        return self._sync_entity(
            LinkEntityType.GRAMMAR,
            grammar_id,
            source_text,
            force=force,
        )

    def sync_vocabulary(self, vocabulary_id: UUID, *, force: bool = False) -> dict:
        row = (
            self.db.table("vocabularies")
            .select("id, word, reading")
            .eq("id", str(vocabulary_id))
            .maybe_single()
            .execute()
        )
        if row is None or not row.data:
            return {"ok": False, "reason": "not_found"}

        definitions = (
            self.db.table("vocabulary_definitions")
            .select("meaning_zh, example_sentences")
            .eq("vocabulary_id", str(vocabulary_id))
            .order("sort_order")
            .execute()
        ).data or []

        source_text = build_vocab_source_text(
            row.data["word"],
            row.data.get("reading"),
            definitions,
        )
        return self._sync_entity(
            LinkEntityType.VOCABULARY,
            vocabulary_id,
            source_text,
            force=force,
        )

    def sync_entity_safe(self, entity_type: LinkEntityType, entity_id: UUID) -> None:
        """Fire-and-forget wrapper for write hooks (never raises)."""
        try:
            if entity_type == LinkEntityType.GRAMMAR:
                self.sync_grammar(entity_id)
            elif entity_type == LinkEntityType.VOCABULARY:
                self.sync_vocabulary(entity_id)
        except Exception:
            logger.exception(
                "semantic sync failed for %s:%s", entity_type.value, entity_id
            )

    def _sync_entity(
        self,
        entity_type: LinkEntityType,
        entity_id: UUID,
        source_text: str,
        *,
        force: bool = False,
    ) -> dict:
        text_hash = content_text_hash(source_text)
        existing = (
            self.db.table("content_embeddings")
            .select("content_hash, embedding")
            .eq("entity_type", entity_type.value)
            .eq("entity_id", str(entity_id))
            .maybe_single()
            .execute()
        )
        existing_row = existing.data if existing is not None else None

        skipped_embed = False
        if (
            not force
            and existing_row
            and existing_row.get("content_hash") == text_hash
            and existing_row.get("embedding")
        ):
            vector = self._parse_vector(existing_row["embedding"])
            skipped_embed = True
        else:
            vector = embedding_service.embed_text(source_text)
            self.db.table("content_embeddings").upsert(
                {
                    "entity_type": entity_type.value,
                    "entity_id": str(entity_id),
                    "embedding": vector,
                    "source_text": source_text,
                    "content_hash": text_hash,
                    "model": settings.GEMINI_EMBEDDING_MODEL,
                },
                on_conflict="entity_type,entity_id",
            ).execute()

        matches = self._match_neighbors(entity_type, entity_id, vector)
        threshold = settings.EMBEDDING_SIMILARITY_THRESHOLD
        gap = settings.EMBEDDING_MAX_SCORE_GAP
        above = [
            m
            for m in matches
            if float(m.get("similarity") or 0.0) >= threshold
        ]
        if above:
            best = max(float(m.get("similarity") or 0.0) for m in above)
            above = [
                m
                for m in above
                if best - float(m.get("similarity") or 0.0) <= gap
            ]

        kept_ids: set[str] = set()
        created = 0
        updated = 0

        for match in above:
            sim = float(match.get("similarity") or 0.0)
            target_id = UUID(str(match["entity_id"]))
            kept_ids.add(str(target_id))
            payload = ContentLinkCreate(
                source_type=entity_type,
                source_id=entity_id,
                target_type=entity_type,
                target_id=target_id,
                relation_type=LinkRelationType.SAME_MEANING,
                label_zh="語意相近",
                note_zh=f"向量相似度 {sim:.2f}",
                confidence=min(1.0, max(0.0, sim)),
                origin="embedding",
                bidirectional=True,
            )
            existing_link = self._find_embedding_link(entity_type, entity_id, target_id)
            if existing_link:
                self.db.table("content_links").update(
                    {
                        "confidence": payload.confidence,
                        "note_zh": payload.note_zh,
                        "label_zh": payload.label_zh,
                    }
                ).eq("id", existing_link["id"]).execute()
                updated += 1
            else:
                link_service.create_links_batch([payload])
                created += 1

        removed = self._prune_stale_embedding_links(entity_type, entity_id, kept_ids)

        return {
            "ok": True,
            "entity_type": entity_type.value,
            "entity_id": str(entity_id),
            "skipped_embed": skipped_embed,
            "matches_considered": len(matches),
            "matches_kept": len(above),
            "links_created": created,
            "links_updated": updated,
            "links_removed": removed,
            "threshold": threshold,
        }

    def prune_weak_embedding_links(
        self,
        *,
        min_confidence: float | None = None,
    ) -> dict:
        """Delete embedding-origin same_meaning links below the confidence floor."""
        floor = (
            settings.EMBEDDING_SIMILARITY_THRESHOLD
            if min_confidence is None
            else min_confidence
        )
        rows = (
            self.db.table("content_links")
            .select("id, confidence")
            .eq("relation_type", LinkRelationType.SAME_MEANING.value)
            .eq("origin", "embedding")
            .execute()
        ).data or []

        to_delete = [
            row["id"]
            for row in rows
            if float(row.get("confidence") or 0.0) < floor
        ]
        for link_id in to_delete:
            self.db.table("content_links").delete().eq("id", link_id).execute()

        return {
            "ok": True,
            "min_confidence": floor,
            "scanned": len(rows),
            "removed": len(to_delete),
        }

    def recompute_semantic_links(
        self,
        *,
        entity_types: list[LinkEntityType] | None = None,
        limit: int = 50,
        force: bool = False,
    ) -> dict:
        """Batch re-sync embeddings/links for recent entities (Map maintenance)."""
        types = entity_types or [LinkEntityType.GRAMMAR, LinkEntityType.VOCABULARY]
        per_type = max(1, limit // max(1, len(types)))
        results: list[dict] = []
        totals = {
            "entities": 0,
            "links_created": 0,
            "links_updated": 0,
            "links_removed": 0,
            "failed": 0,
        }

        if LinkEntityType.GRAMMAR in types:
            rows = (
                self.db.table("grammars")
                .select("id")
                .neq("sync_status", "archived")
                .order("updated_at", desc=True)
                .limit(per_type)
                .execute()
            ).data or []
            for row in rows:
                totals["entities"] += 1
                try:
                    res = self.sync_grammar(UUID(row["id"]), force=force)
                    if res.get("ok"):
                        totals["links_created"] += int(res.get("links_created") or 0)
                        totals["links_updated"] += int(res.get("links_updated") or 0)
                        totals["links_removed"] += int(res.get("links_removed") or 0)
                    else:
                        totals["failed"] += 1
                    results.append(res)
                except Exception:
                    logger.exception("recompute grammar failed: %s", row["id"])
                    totals["failed"] += 1

        if LinkEntityType.VOCABULARY in types:
            rows = (
                self.db.table("vocabularies")
                .select("id")
                .order("updated_at", desc=True)
                .limit(per_type)
                .execute()
            ).data or []
            for row in rows:
                totals["entities"] += 1
                try:
                    res = self.sync_vocabulary(UUID(row["id"]), force=force)
                    if res.get("ok"):
                        totals["links_created"] += int(res.get("links_created") or 0)
                        totals["links_updated"] += int(res.get("links_updated") or 0)
                        totals["links_removed"] += int(res.get("links_removed") or 0)
                    else:
                        totals["failed"] += 1
                    results.append(res)
                except Exception:
                    logger.exception("recompute vocabulary failed: %s", row["id"])
                    totals["failed"] += 1

        return {
            "ok": True,
            "threshold": settings.EMBEDDING_SIMILARITY_THRESHOLD,
            "force": force,
            **totals,
        }

    def _match_neighbors(
        self,
        entity_type: LinkEntityType,
        entity_id: UUID,
        vector: list[float],
    ) -> list[dict]:
        try:
            result = self.db.rpc(
                "match_content_embeddings",
                {
                    "query_embedding": vector,
                    "match_entity_type": entity_type.value,
                    "match_count": settings.EMBEDDING_MATCH_TOP_K,
                    "exclude_id": str(entity_id),
                },
            ).execute()
            return result.data or []
        except Exception:
            logger.exception("match_content_embeddings RPC failed; falling back")
            return self._match_neighbors_fallback(entity_type, entity_id, vector)

    def _match_neighbors_fallback(
        self,
        entity_type: LinkEntityType,
        entity_id: UUID,
        vector: list[float],
    ) -> list[dict]:
        """Python cosine fallback if RPC unavailable (slower, for small corpora)."""
        rows = (
            self.db.table("content_embeddings")
            .select("entity_id, embedding")
            .eq("entity_type", entity_type.value)
            .neq("entity_id", str(entity_id))
            .limit(500)
            .execute()
        ).data or []

        scored: list[tuple[float, str]] = []
        for row in rows:
            other = self._parse_vector(row.get("embedding"))
            if not other:
                continue
            sim = self._cosine(vector, other)
            scored.append((sim, row["entity_id"]))
        scored.sort(key=lambda x: -x[0])
        top = scored[: settings.EMBEDDING_MATCH_TOP_K]
        return [
            {
                "entity_type": entity_type.value,
                "entity_id": eid,
                "similarity": sim,
            }
            for sim, eid in top
        ]

    def _find_embedding_link(
        self,
        entity_type: LinkEntityType,
        source_id: UUID,
        target_id: UUID,
    ) -> dict | None:
        et = entity_type.value
        sid, tid = str(source_id), str(target_id)
        for src, tgt in ((sid, tid), (tid, sid)):
            result = (
                self.db.table("content_links")
                .select("id")
                .eq("source_type", et)
                .eq("source_id", src)
                .eq("target_type", et)
                .eq("target_id", tgt)
                .eq("relation_type", LinkRelationType.SAME_MEANING.value)
                .eq("origin", "embedding")
                .maybe_single()
                .execute()
            )
            if result is not None and result.data:
                return result.data
        return None

    def _prune_stale_embedding_links(
        self,
        entity_type: LinkEntityType,
        entity_id: UUID,
        keep_target_ids: set[str],
    ) -> int:
        et = entity_type.value
        eid = str(entity_id)
        as_source = (
            self.db.table("content_links")
            .select("id, target_id")
            .eq("source_type", et)
            .eq("source_id", eid)
            .eq("relation_type", LinkRelationType.SAME_MEANING.value)
            .eq("origin", "embedding")
            .execute()
        ).data or []
        as_target = (
            self.db.table("content_links")
            .select("id, source_id")
            .eq("target_type", et)
            .eq("target_id", eid)
            .eq("relation_type", LinkRelationType.SAME_MEANING.value)
            .eq("origin", "embedding")
            .execute()
        ).data or []

        to_delete: list[str] = []
        for row in as_source:
            if row["target_id"] not in keep_target_ids:
                to_delete.append(row["id"])
        for row in as_target:
            if row["source_id"] not in keep_target_ids:
                to_delete.append(row["id"])

        for link_id in to_delete:
            self.db.table("content_links").delete().eq("id", link_id).execute()
        return len(to_delete)

    @staticmethod
    def _parse_vector(raw: object) -> list[float]:
        if raw is None:
            return []
        if isinstance(raw, list):
            return [float(x) for x in raw]
        if isinstance(raw, str):
            text = raw.strip().strip("[]")
            if not text:
                return []
            return [float(x.strip()) for x in text.split(",") if x.strip()]
        return []

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        n = min(len(a), len(b))
        if n == 0:
            return 0.0
        return sum(a[i] * b[i] for i in range(n))


semantic_link_service = SemanticLinkService()
