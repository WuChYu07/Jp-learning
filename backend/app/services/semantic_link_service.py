"""Auto-create same_meaning links via embedding similarity (JLPT-agnostic).

Each entity (grammar point / vocab word) can have multiple "senses"
(usages / definitions). Rather than blending every sense into one averaged
embedding — which can hide a real match on one sense behind unrelated other
senses — each sense gets its own vector, and matching keeps the best
cross-sense similarity per candidate entity. An exact-text-match pass (free,
no AI) also catches identical Chinese meanings that a diluted or borderline
embedding might miss.
"""

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
    build_grammar_sense_texts,
    build_vocab_sense_texts,
    content_text_hash,
    embedding_service,
)
from app.services.link_service import link_service

logger = logging.getLogger(__name__)

_AUTO_ORIGINS = ("embedding", "text_match")
_MIN_EXACT_MATCH_LEN = 2


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

        sense_texts = build_grammar_sense_texts(
            row.data["grammar_point"],
            usages,
            max_senses=settings.EMBEDDING_MAX_SENSES_PER_ENTITY,
        )
        raw_meanings = [
            (u.get("meaning_zh") or "").strip() for u in usages if (u.get("meaning_zh") or "").strip()
        ]
        return self._sync_entity(
            LinkEntityType.GRAMMAR,
            grammar_id,
            sense_texts,
            raw_meanings,
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
            .select("meaning_zh")
            .eq("vocabulary_id", str(vocabulary_id))
            .order("sort_order")
            .execute()
        ).data or []

        sense_texts = build_vocab_sense_texts(
            row.data["word"],
            row.data.get("reading"),
            definitions,
            max_senses=settings.EMBEDDING_MAX_SENSES_PER_ENTITY,
        )
        raw_meanings = [
            (d.get("meaning_zh") or "").strip()
            for d in definitions
            if (d.get("meaning_zh") or "").strip()
        ]
        return self._sync_entity(
            LinkEntityType.VOCABULARY,
            vocabulary_id,
            sense_texts,
            raw_meanings,
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
        sense_texts: list[str],
        raw_meanings: list[str],
        *,
        force: bool = False,
    ) -> dict:
        existing_rows = (
            self.db.table("content_embeddings")
            .select("sense_index, content_hash, embedding")
            .eq("entity_type", entity_type.value)
            .eq("entity_id", str(entity_id))
            .execute()
        ).data or []
        existing_by_index = {row["sense_index"]: row for row in existing_rows}

        vectors: list[list[float]] = []
        any_recomputed = False
        for idx, text in enumerate(sense_texts):
            text_hash = content_text_hash(text)
            existing_row = existing_by_index.get(idx)
            if (
                not force
                and existing_row
                and existing_row.get("content_hash") == text_hash
                and existing_row.get("embedding")
            ):
                vectors.append(self._parse_vector(existing_row["embedding"]))
                continue

            any_recomputed = True
            vector = embedding_service.embed_text(text)
            vectors.append(vector)
            self.db.table("content_embeddings").upsert(
                {
                    "entity_type": entity_type.value,
                    "entity_id": str(entity_id),
                    "sense_index": idx,
                    "embedding": vector,
                    "source_text": text,
                    "content_hash": text_hash,
                    "model": settings.GEMINI_EMBEDDING_MODEL,
                },
                on_conflict="entity_type,entity_id,sense_index",
            ).execute()

        # Drop sense rows beyond the current sense count (e.g. definitions removed).
        for idx in list(existing_by_index.keys()):
            if idx >= len(sense_texts):
                self.db.table("content_embeddings").delete().eq(
                    "entity_type", entity_type.value
                ).eq("entity_id", str(entity_id)).eq("sense_index", idx).execute()

        kept: dict[str, dict] = {}

        for target_id in self._find_exact_meaning_matches(entity_type, entity_id, raw_meanings):
            kept[target_id] = {
                "confidence": 1.0,
                "origin": "text_match",
                "note_zh": "中文意思完全相同",
            }

        best_by_target: dict[str, float] = {}
        matches_considered = 0
        for vector in vectors:
            for match in self._match_neighbors(entity_type, entity_id, vector):
                matches_considered += 1
                target_id = str(match["entity_id"])
                sim = float(match.get("similarity") or 0.0)
                if target_id not in best_by_target or sim > best_by_target[target_id]:
                    best_by_target[target_id] = sim

        strict_threshold = settings.EMBEDDING_SIMILARITY_THRESHOLD
        related_threshold = settings.EMBEDDING_RELATED_THRESHOLD
        gap = settings.EMBEDDING_MAX_SCORE_GAP

        strict_matches = {
            tid: sim for tid, sim in best_by_target.items() if sim >= strict_threshold
        }
        if strict_matches:
            best_strict = max(strict_matches.values())
            strict_matches = {
                tid: sim for tid, sim in strict_matches.items() if best_strict - sim <= gap
            }
        related_matches = {
            tid: sim
            for tid, sim in best_by_target.items()
            if related_threshold <= sim < strict_threshold
        }

        for tid, sim in strict_matches.items():
            kept.setdefault(
                tid,
                {"confidence": sim, "origin": "embedding", "note_zh": f"向量相似度 {sim:.2f}"},
            )
        for tid, sim in related_matches.items():
            kept.setdefault(
                tid,
                {
                    "confidence": sim,
                    "origin": "embedding",
                    "note_zh": f"向量相似度 {sim:.2f}（可能相關，非嚴格同義）",
                },
            )

        created = 0
        updated = 0
        for target_id_str, info in kept.items():
            target_id = UUID(target_id_str)
            payload = ContentLinkCreate(
                source_type=entity_type,
                source_id=entity_id,
                target_type=entity_type,
                target_id=target_id,
                relation_type=LinkRelationType.SAME_MEANING,
                label_zh="語意相近",
                note_zh=info["note_zh"],
                confidence=min(1.0, max(0.0, info["confidence"])),
                origin=info["origin"],
                bidirectional=True,
            )
            existing_link = self._find_auto_link(entity_type, entity_id, target_id)
            if existing_link:
                self.db.table("content_links").update(
                    {
                        "confidence": payload.confidence,
                        "note_zh": payload.note_zh,
                        "label_zh": payload.label_zh,
                        "origin": payload.origin,
                    }
                ).eq("id", existing_link["id"]).execute()
                updated += 1
            else:
                link_service.create_links_batch([payload])
                created += 1

        removed = self._prune_stale_auto_links(entity_type, entity_id, set(kept.keys()))

        return {
            "ok": True,
            "entity_type": entity_type.value,
            "entity_id": str(entity_id),
            "skipped_embed": not any_recomputed,
            "senses": len(sense_texts),
            "matches_considered": matches_considered,
            "matches_kept": len(kept),
            "links_created": created,
            "links_updated": updated,
            "links_removed": removed,
            "threshold": strict_threshold,
            "related_threshold": related_threshold,
        }

    def _find_exact_meaning_matches(
        self,
        entity_type: LinkEntityType,
        entity_id: UUID,
        raw_meanings: list[str],
    ) -> set[str]:
        """Free (no AI) same_meaning candidates: other entities of the same
        type sharing an exact-normalized Chinese meaning with any sense of
        this entity — catches identical meanings that a diluted or
        borderline embedding could otherwise miss.
        """
        normalized_targets = {
            m.strip().lower() for m in raw_meanings if len((m or "").strip()) >= _MIN_EXACT_MATCH_LEN
        }
        if not normalized_targets:
            return set()

        table = "grammar_usages" if entity_type == LinkEntityType.GRAMMAR else "vocabulary_definitions"
        id_column = "grammar_id" if entity_type == LinkEntityType.GRAMMAR else "vocabulary_id"

        try:
            rows = self.db.table(table).select(f"{id_column}, meaning_zh").execute().data or []
        except Exception:
            logger.warning("exact meaning-match lookup failed for %s", table)
            return set()

        self_id = str(entity_id)
        matched: set[str] = set()
        for row in rows:
            other_id = row.get(id_column)
            if not other_id or other_id == self_id:
                continue
            meaning = (row.get("meaning_zh") or "").strip().lower()
            if len(meaning) >= _MIN_EXACT_MATCH_LEN and meaning in normalized_targets:
                matched.add(other_id)
        return matched

    def prune_weak_embedding_links(
        self,
        *,
        min_confidence: float | None = None,
    ) -> dict:
        """Delete auto-generated same_meaning links below the confidence floor."""
        floor = (
            settings.EMBEDDING_RELATED_THRESHOLD if min_confidence is None else min_confidence
        )
        rows = (
            self.db.table("content_links")
            .select("id, confidence, origin")
            .eq("relation_type", LinkRelationType.SAME_MEANING.value)
            .in_("origin", list(_AUTO_ORIGINS))
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
        scope: str = "recent",
    ) -> dict:
        """Batch re-sync embeddings/links.

        scope="recent" (default): capped at `limit` total, split across
        entity types, never-embedded entities first (in updated_at desc
        order) so repeated calls make guaranteed progress instead of
        re-selecting the same already-processed rows; already-embedded
        entities fill any remaining budget (catches content changes).

        scope="all_new": ignores `limit` — processes every entity that has
        never been embedded at all, in one pass. Intended as a deliberate,
        cost-aware "catch up after a big import" action.
        """
        types = entity_types or [LinkEntityType.GRAMMAR, LinkEntityType.VOCABULARY]
        per_type = None if scope == "all_new" else max(1, limit // max(1, len(types)))
        results: list[dict] = []
        totals = {
            "entities": 0,
            "links_created": 0,
            "links_updated": 0,
            "links_removed": 0,
            "failed": 0,
        }

        if LinkEntityType.GRAMMAR in types:
            rows = self._select_priority_batch(
                "grammars", LinkEntityType.GRAMMAR, per_type, filter_archived=True
            )
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
            rows = self._select_priority_batch(
                "vocabularies", LinkEntityType.VOCABULARY, per_type, filter_archived=False
            )
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
            "scope": scope,
            "threshold": settings.EMBEDDING_SIMILARITY_THRESHOLD,
            "force": force,
            **totals,
        }

    def _select_priority_batch(
        self,
        table: str,
        entity_type: LinkEntityType,
        cap: int | None,
        *,
        filter_archived: bool,
    ) -> list[dict]:
        """Rows needing a semantic sync, never-embedded first (in updated_at
        desc order); already-embedded rows fill any remaining `cap` budget.
        cap=None returns every never-embedded row, uncapped.
        """
        query = self.db.table(table).select("id, updated_at")
        if filter_archived:
            query = query.neq("sync_status", "archived")
        all_rows = query.order("updated_at", desc=True).execute().data or []
        all_ids = [row["id"] for row in all_rows]

        embedded_ids: set[str] = set()
        for batch_start in range(0, len(all_ids), 200):
            batch = all_ids[batch_start : batch_start + 200]
            try:
                result = (
                    self.db.table("content_embeddings")
                    .select("entity_id")
                    .eq("entity_type", entity_type.value)
                    .in_("entity_id", batch)
                    .execute()
                )
            except Exception:
                logger.warning("content_embeddings lookup failed while selecting batch")
                continue
            embedded_ids.update(row["entity_id"] for row in (result.data or []))

        never_embedded = [row for row in all_rows if row["id"] not in embedded_ids]
        if cap is None:
            return never_embedded

        prioritized = never_embedded[:cap]
        remaining = cap - len(prioritized)
        if remaining > 0:
            already_embedded = [row for row in all_rows if row["id"] in embedded_ids]
            prioritized += already_embedded[:remaining]
        return prioritized

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
        """Python cosine fallback if RPC unavailable (slower, for small corpora).

        Dedupes to the best-scoring row per entity_id, matching the RPC's
        behavior now that an entity can have multiple sense rows.
        """
        rows = (
            self.db.table("content_embeddings")
            .select("entity_id, embedding")
            .eq("entity_type", entity_type.value)
            .neq("entity_id", str(entity_id))
            .limit(2000)
            .execute()
        ).data or []

        best_by_entity: dict[str, float] = {}
        for row in rows:
            other = self._parse_vector(row.get("embedding"))
            if not other:
                continue
            sim = self._cosine(vector, other)
            eid = row["entity_id"]
            if eid not in best_by_entity or sim > best_by_entity[eid]:
                best_by_entity[eid] = sim

        top = sorted(best_by_entity.items(), key=lambda x: -x[1])[: settings.EMBEDDING_MATCH_TOP_K]
        return [
            {"entity_type": entity_type.value, "entity_id": eid, "similarity": sim}
            for eid, sim in top
        ]

    def _find_auto_link(
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
                .in_("origin", list(_AUTO_ORIGINS))
                .maybe_single()
                .execute()
            )
            if result is not None and result.data:
                return result.data
        return None

    def _prune_stale_auto_links(
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
            .in_("origin", list(_AUTO_ORIGINS))
            .execute()
        ).data or []
        as_target = (
            self.db.table("content_links")
            .select("id, source_id")
            .eq("target_type", et)
            .eq("target_id", eid)
            .eq("relation_type", LinkRelationType.SAME_MEANING.value)
            .in_("origin", list(_AUTO_ORIGINS))
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
