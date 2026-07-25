from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

from app.db.supabase import get_supabase_client
from app.models.schemas.common import SourceType
from app.models.schemas.grammar import GrammarItemInput, GrammarOut
from app.models.schemas.ingestion import IngestionParseResult, IngestionResponse, SyncReport
from app.models.schemas.vocab import (
    VocabularyDefinitionOut,
    VocabularyItemInput,
    VocabularyOut,
)
from app.services import gemini_service
from app.services.gemini_service import IngestionFocus
from app.services.grammar_service import grammar_service
from app.services.hash_service import (
    compute_upload_hash,
    grammar_entry_hash,
    vocab_entry_hash,
    vocab_source_hash,
)
from app.services.text_sanitize import clean_text


@dataclass
class PersistStats:
    """Write outcome for one entity type during a persist call."""

    source_rows: int = 0
    new: int = 0
    updated: int = 0
    skipped: int = 0
    dedupe_removed: int = 0

    @property
    def written(self) -> int:
        """Rows created or changed (used as the headline count)."""
        return self.new + self.updated


class IngestionService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def process_upload(
        self,
        file_bytes: bytes,
        mime_type: str,
        file_name: str | None,
        user_id: str | None,
        source_type: SourceType,
        focus: IngestionFocus = "both",
    ) -> IngestionResponse:
        content_hash = compute_upload_hash(file_bytes, mime_type)

        cached = self._find_cached_ingestion(content_hash)
        if cached:
            return IngestionResponse.model_validate({**cached, "cached": True})

        parsed = gemini_service.parse_content(file_bytes, mime_type, focus=focus)
        ingestion_id = self._create_ingestion_row(
            content_hash=content_hash,
            source_type=source_type,
            mime_type=mime_type,
            file_name=file_name,
            user_id=user_id,
        )

        vocab_stats = self._persist_vocabularies_bulk(
            parsed.vocabularies, ingestion_id, user_id, source_type
        )
        if source_type == SourceType.NOTION and any(
            item.notion_block_id for item in parsed.grammars
        ):
            try:
                grammar_stats = self._persist_notion_grammars_bulk(
                    parsed.grammars, ingestion_id, user_id
                )
            except Exception:
                grammar_stats = self._persist_grammars_bulk(
                    parsed.grammars, ingestion_id, user_id, source_type
                )
        else:
            grammar_stats = self._persist_grammars_bulk(
                parsed.grammars, ingestion_id, user_id, source_type
            )

        response = IngestionResponse(
            ingestion_id=ingestion_id,
            content_hash=content_hash,
            cached=False,
            vocabulary_count=vocab_stats.written,
            grammar_count=grammar_stats.written,
            vocabularies=[],
            grammars=[],
            report=_build_report(vocab_stats, grammar_stats),
        )
        self._save_parsed_payload(ingestion_id, response)
        return response

    def process_parsed_data(
        self,
        parsed: IngestionParseResult,
        content_hash: str,
        user_id: str | None,
        source_type: SourceType,
        mime_type: str = "text/plain",
        file_name: str | None = None,
        *,
        skip_ingestion_cache: bool = False,
    ) -> IngestionResponse:
        """Save pre-parsed data (from text preview confirm) to DB."""
        if not skip_ingestion_cache:
            cached = self._find_cached_ingestion(content_hash)
            if cached:
                return IngestionResponse.model_validate({**cached, "cached": True})

        ingestion_id = self._create_ingestion_row(
            content_hash=content_hash,
            source_type=source_type,
            mime_type=mime_type,
            file_name=file_name,
            user_id=user_id,
        )

        vocab_stats = self._persist_vocabularies_bulk(
            parsed.vocabularies, ingestion_id, user_id, source_type
        )
        if source_type == SourceType.NOTION and any(
            item.notion_block_id for item in parsed.grammars
        ):
            try:
                grammar_stats = self._persist_notion_grammars_bulk(
                    parsed.grammars, ingestion_id, user_id
                )
            except Exception:
                grammar_stats = self._persist_grammars_bulk(
                    parsed.grammars, ingestion_id, user_id, source_type
                )
        else:
            grammar_stats = self._persist_grammars_bulk(
                parsed.grammars, ingestion_id, user_id, source_type
            )

        response = IngestionResponse(
            ingestion_id=ingestion_id,
            content_hash=content_hash,
            cached=False,
            vocabulary_count=vocab_stats.written,
            grammar_count=grammar_stats.written,
            vocabularies=[],
            grammars=[],
            report=_build_report(vocab_stats, grammar_stats),
        )
        self._save_parsed_payload(ingestion_id, response)
        return response

    def _find_cached_ingestion(self, content_hash: str) -> dict | None:
        result = (
            self.db.table("content_ingestions")
            .select("id, content_hash, parsed_payload")
            .eq("content_hash", content_hash)
            .maybe_single()
            .execute()
        )
        if result is None or not result.data:
            return None

        payload = result.data.get("parsed_payload") or {}
        if not payload:
            return None

        return {
            "ingestion_id": result.data["id"],
            "content_hash": result.data["content_hash"],
            **payload,
        }

    def _create_ingestion_row(
        self,
        content_hash: str,
        source_type: SourceType,
        mime_type: str,
        file_name: str | None,
        user_id: str | None,
    ) -> UUID:
        result = (
            self.db.table("content_ingestions")
            .insert(
                {
                    "content_hash": content_hash,
                    "source_type": source_type.value,
                    "mime_type": mime_type,
                    "file_name": file_name,
                    "created_by": user_id,
                    "parsed_payload": {},
                }
            )
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create ingestion record",
            )
        return UUID(result.data[0]["id"])

    def _save_parsed_payload(self, ingestion_id: UUID, response: IngestionResponse) -> None:
        payload = response.model_dump(
            mode="json",
            exclude={"ingestion_id", "content_hash", "cached"},
        )
        # Keep cache payload small for large imports
        if response.vocabulary_count > 20:
            payload["vocabularies"] = payload["vocabularies"][:10]
        if response.grammar_count > 20:
            payload["grammars"] = payload["grammars"][:10]
        self.db.table("content_ingestions").update({"parsed_payload": payload}).eq(
            "id", str(ingestion_id)
        ).execute()

    def _persist_vocabularies_bulk(
        self,
        items: list[VocabularyItemInput],
        ingestion_id: UUID,
        user_id: str | None,
        source_type: SourceType,
    ) -> PersistStats:
        if not items:
            return PersistStats()

        hash_map = {vocab_entry_hash(item.word, item.reading): item for item in items}
        id_by_hash: dict[str, UUID] = {}
        for hash_batch in _chunks(list(hash_map.keys()), 100):
            existing = (
                self.db.table("vocabularies")
                .select("id, content_hash")
                .in_("content_hash", hash_batch)
                .execute()
            )
            for row in existing.data or []:
                id_by_hash[row["content_hash"]] = UUID(row["id"])

        new_rows = []
        for entry_hash, item in hash_map.items():
            if entry_hash in id_by_hash:
                continue
            new_rows.append(
                {
                    "word": clean_text(item.word),
                    "reading": clean_text(item.reading),
                    "jlpt_level": item.jlpt_level.value,
                    "content_hash": entry_hash,
                    "source_type": source_type.value,
                    "ingestion_id": str(ingestion_id),
                    "created_by": user_id,
                    "notion_source_hash": (
                        vocab_source_hash(
                            word=item.word, reading=item.reading, definitions=item.definitions
                        )
                        if source_type == SourceType.NOTION
                        else None
                    ),
                }
            )

        definition_rows = []
        newly_inserted: list[UUID] = []
        for row_batch in _chunks(new_rows, 100):
            inserted = self.db.table("vocabularies").insert(row_batch).execute()
            for row in inserted.data or []:
                id_by_hash[row["content_hash"]] = UUID(row["id"])
                newly_inserted.append(UUID(row["id"]))
                item = hash_map[row["content_hash"]]
                for index, definition in enumerate(item.definitions):
                    definition_rows.append(
                        {
                            "vocabulary_id": row["id"],
                            "sort_order": index,
                            "part_of_speech": definition.part_of_speech.value,
                            "meaning_zh": clean_text(definition.meaning_zh),
                            "meaning_en": clean_text(definition.meaning_en),
                            "example_sentences": [
                                ex.model_dump(mode="json")
                                for ex in definition.example_sentences
                            ],
                            "notes_zh": clean_text(definition.notes_zh),
                        }
                    )

        for def_batch in _chunks(definition_rows, 200):
            if def_batch:
                self.db.table("vocabulary_definitions").insert(def_batch).execute()

        # Existing rows: fill empty examples / notes from richer Notion parse (gap-only).
        existing_hashes = [
            h for h in hash_map if h in id_by_hash and id_by_hash[h] not in newly_inserted
        ]
        gap_updated = self._fill_vocab_definition_gaps(
            hash_map, id_by_hash, existing_hashes, source_type
        )

        existing_count = len(existing_hashes)
        return PersistStats(
            source_rows=len(items),
            new=len(newly_inserted),
            updated=gap_updated,
            skipped=existing_count - gap_updated,
            dedupe_removed=len(items) - len(hash_map),
        )

    def _fill_vocab_definition_gaps(
        self,
        hash_map: dict[str, VocabularyItemInput],
        id_by_hash: dict[str, UUID],
        existing_hashes: list[str],
        source_type: SourceType,
    ) -> int:
        """For already-synced vocab, write Notion examples/notes only into empty fields.

        Also refreshes `notion_source_hash` for Notion syncs so the next diff
        compares against what Notion has now, independent of AI-enriched content.

        Returns the number of existing rows that actually received a gap fill.
        """
        updated = 0
        for entry_hash in existing_hashes:
            item = hash_map.get(entry_hash)
            if not item or not item.definitions:
                continue

            vocab_id = id_by_hash[entry_hash]

            if source_type == SourceType.NOTION:
                notion_hash = vocab_source_hash(
                    word=item.word, reading=item.reading, definitions=item.definitions
                )
                (
                    self.db.table("vocabularies")
                    .update({"notion_source_hash": notion_hash})
                    .eq("id", str(vocab_id))
                    .execute()
                )

            parsed = item.definitions[0]
            has_examples = bool(parsed.example_sentences)
            has_notes = bool((parsed.notes_zh or "").strip())
            if not has_examples and not has_notes:
                continue

            existing_defs = (
                self.db.table("vocabulary_definitions")
                .select("id, example_sentences, notes_zh")
                .eq("vocabulary_id", str(vocab_id))
                .order("sort_order")
                .limit(1)
                .execute()
            ).data or []
            if not existing_defs:
                continue
            row = existing_defs[0]
            updates: dict = {}
            if has_examples and not (row.get("example_sentences") or []):
                updates["example_sentences"] = [
                    ex.model_dump(mode="json") for ex in parsed.example_sentences
                ]
            if has_notes and not (row.get("notes_zh") or "").strip():
                updates["notes_zh"] = clean_text(parsed.notes_zh)
            if updates:
                (
                    self.db.table("vocabulary_definitions")
                    .update(updates)
                    .eq("id", row["id"])
                    .execute()
                )
                updated += 1
        return updated

    def _persist_grammars_bulk(
        self,
        items: list[GrammarItemInput],
        ingestion_id: UUID,
        user_id: str | None,
        source_type: SourceType,
    ) -> PersistStats:
        if not items:
            return PersistStats()

        hash_map = {grammar_entry_hash(item.grammar_point): item for item in items}
        id_by_hash: dict[str, UUID] = {}
        for hash_batch in _chunks(list(hash_map.keys()), 100):
            existing = (
                self.db.table("grammars")
                .select("id, content_hash")
                .in_("content_hash", hash_batch)
                .execute()
            )
            for row in existing.data or []:
                id_by_hash[row["content_hash"]] = UUID(row["id"])

        new_rows = []
        for entry_hash, item in hash_map.items():
            if entry_hash in id_by_hash:
                continue
            new_rows.append(
                {
                    "grammar_point": clean_text(item.grammar_point),
                    "jlpt_level": item.jlpt_level,
                    "content_hash": entry_hash,
                    "source_type": source_type.value,
                    "ingestion_id": str(ingestion_id),
                    "created_by": user_id,
                    "image_urls": item.image_urls or [],
                }
            )

        usage_rows = []
        newly_inserted: list[UUID] = []
        for row_batch in _chunks(new_rows, 100):
            inserted = self.db.table("grammars").insert(row_batch).execute()
            for row in inserted.data or []:
                id_by_hash[row["content_hash"]] = UUID(row["id"])
                newly_inserted.append(UUID(row["id"]))
                item = hash_map[row["content_hash"]]
                for index, usage in enumerate(item.usages):
                    usage_rows.append(
                        {
                            "grammar_id": row["id"],
                            "sort_order": index,
                            "semantic_concept": clean_text(usage.semantic_concept),
                            "connection_rule": clean_text(usage.connection_rule),
                            "meaning_zh": clean_text(usage.meaning_zh),
                            "meaning_en": clean_text(usage.meaning_en),
                            "meaning_blocks": [
                                block.model_dump(mode="json") for block in usage.meaning_blocks
                            ],
                            "example_sentences": [
                                ex.model_dump(mode="json") for ex in usage.example_sentences
                            ],
                        }
                    )

        for usage_batch in _chunks(usage_rows, 200):
            if usage_batch:
                self.db.table("grammar_usages").insert(usage_batch).execute()

        # Non-Notion grammar persist creates new rows only; existing rows are left untouched.
        # Semantic links are maintained on-demand from Map / detail pages (P3).
        return PersistStats(
            source_rows=len(items),
            new=len(newly_inserted),
            updated=0,
            skipped=len(hash_map) - len(newly_inserted),
            dedupe_removed=len(items) - len(hash_map),
        )

    def _persist_notion_grammars_bulk(
        self,
        items: list[GrammarItemInput],
        ingestion_id: UUID,
        user_id: str | None,
    ) -> PersistStats:
        """Upsert Notion grammar units by notion_block_id; skip unchanged."""
        if not items:
            return PersistStats()

        block_ids = [item.notion_block_id for item in items if item.notion_block_id]
        existing_by_block: dict[str, dict] = {}
        if block_ids:
            for batch_start in range(0, len(block_ids), 100):
                batch = block_ids[batch_start : batch_start + 100]
                result = (
                    self.db.table("grammars")
                    .select(
                        "id, notion_block_id, source_content_hash, ai_content_hash, "
                        "sync_status, manual_edited_at"
                    )
                    .in_("notion_block_id", batch)
                    .execute()
                )
                for row in result.data or []:
                    bid = row.get("notion_block_id")
                    if bid:
                        existing_by_block[bid] = row

        stats = PersistStats(source_rows=len(items))
        for item in items:
            if item.sync_change == "unchanged":
                stats.skipped += 1
                continue

            existing = (
                existing_by_block.get(item.notion_block_id) if item.notion_block_id else None
            )

            # Soft-deleted tombstone: keep archived, never resurrect from Notion.
            if existing and existing.get("sync_status") == "archived":
                stats.skipped += 1
                continue

            entry_hash = grammar_entry_hash(item.grammar_point)
            sync_status = "needs_ai" if item.image_urls else "synced"
            base_row = {
                "grammar_point": clean_text(item.grammar_point),
                "jlpt_level": item.jlpt_level,
                "content_hash": entry_hash,
                "source_type": SourceType.NOTION.value,
                "ingestion_id": str(ingestion_id),
                "created_by": user_id,
                "image_urls": item.image_urls or [],
                "notion_block_id": item.notion_block_id,
                "notion_page_id": item.notion_page_id,
                "source_content_hash": item.source_content_hash,
                "block_ids": item.block_ids or [],
                "sync_status": sync_status,
            }

            if existing:
                grammar_id = UUID(existing["id"])
                meta_only = bool(existing.get("manual_edited_at")) or (
                    item.sync_change == "updated" and not item.force_overwrite
                )

                if meta_only:
                    self.db.table("grammars").update(
                        {
                            "image_urls": item.image_urls or [],
                            "source_content_hash": item.source_content_hash,
                            "block_ids": item.block_ids or [],
                            "notion_page_id": item.notion_page_id,
                            "ingestion_id": str(ingestion_id),
                        }
                    ).eq("id", str(grammar_id)).execute()
                    stats.updated += 1
                    continue

                ai_hash = existing.get("ai_content_hash")
                if ai_hash and ai_hash == item.source_content_hash:
                    base_row["sync_status"] = "synced"
                else:
                    base_row["sync_status"] = "needs_ai"

                self.db.table("grammars").update(base_row).eq("id", str(grammar_id)).execute()
                self._replace_grammar_usages(grammar_id, item)
                stats.updated += 1
                continue

            try:
                inserted = self.db.table("grammars").insert(base_row).execute()
            except Exception:
                fallback = (
                    self.db.table("grammars")
                    .select("id, sync_status, manual_edited_at")
                    .eq("content_hash", entry_hash)
                    .maybe_single()
                    .execute()
                )
                if fallback is None or not fallback.data:
                    stats.skipped += 1
                    continue
                if fallback.data.get("sync_status") == "archived":
                    stats.skipped += 1
                    continue
                grammar_id = UUID(fallback.data["id"])
                meta_only = bool(fallback.data.get("manual_edited_at")) or (
                    item.sync_change == "updated" and not item.force_overwrite
                )
                if meta_only:
                    self.db.table("grammars").update(
                        {
                            "image_urls": item.image_urls or [],
                            "source_content_hash": item.source_content_hash,
                            "block_ids": item.block_ids or [],
                            "notion_page_id": item.notion_page_id,
                            "ingestion_id": str(ingestion_id),
                        }
                    ).eq("id", str(grammar_id)).execute()
                else:
                    self.db.table("grammars").update(base_row).eq("id", str(grammar_id)).execute()
                    self._replace_grammar_usages(grammar_id, item)
                stats.updated += 1
                continue

            if not inserted.data:
                stats.skipped += 1
                continue
            grammar_id = UUID(inserted.data[0]["id"])
            self._insert_grammar_usages(grammar_id, item)
            if item.notion_block_id:
                existing_by_block[item.notion_block_id] = inserted.data[0]
            stats.new += 1

        return stats

    def _insert_grammar_usages(self, grammar_id: UUID, item: GrammarItemInput) -> None:
        rows = []
        for index, usage in enumerate(item.usages):
            rows.append(
                {
                    "grammar_id": str(grammar_id),
                    "sort_order": index,
                    "semantic_concept": clean_text(usage.semantic_concept),
                    "connection_rule": clean_text(usage.connection_rule),
                    "meaning_zh": clean_text(usage.meaning_zh),
                    "meaning_en": clean_text(usage.meaning_en),
                    "meaning_blocks": [
                        block.model_dump(mode="json") for block in usage.meaning_blocks
                    ],
                    "example_sentences": [
                        ex.model_dump(mode="json") for ex in usage.example_sentences
                    ],
                }
            )
        for batch in _chunks(rows, 200):
            if batch:
                self.db.table("grammar_usages").insert(batch).execute()

    def _replace_grammar_usages(self, grammar_id: UUID, item: GrammarItemInput) -> None:
        self.db.table("grammar_usages").delete().eq("grammar_id", str(grammar_id)).execute()
        self._insert_grammar_usages(grammar_id, item)

    def _persist_vocabulary(
        self,
        item: VocabularyItemInput,
        ingestion_id: UUID,
        user_id: str | None,
        source_type: SourceType,
    ) -> VocabularyOut:
        entry_hash = vocab_entry_hash(item.word, item.reading)
        existing = (
            self.db.table("vocabularies")
            .select("id")
            .eq("content_hash", entry_hash)
            .maybe_single()
            .execute()
        )
        if existing is not None and existing.data:
            return self._load_vocabulary_out(UUID(existing.data["id"]))

        vocab_result = (
            self.db.table("vocabularies")
            .insert(
                {
                    "word": item.word,
                    "reading": item.reading,
                    "jlpt_level": item.jlpt_level.value,
                    "content_hash": entry_hash,
                    "source_type": source_type.value,
                    "ingestion_id": str(ingestion_id),
                    "created_by": user_id,
                }
            )
            .execute()
        )
        vocab_id = UUID(vocab_result.data[0]["id"])
        self._insert_vocabulary_definitions(vocab_id, item)
        return self._load_vocabulary_out(vocab_id)

    def _insert_vocabulary_definitions(
        self, vocabulary_id: UUID, item: VocabularyItemInput
    ) -> None:
        rows = [
            {
                "vocabulary_id": str(vocabulary_id),
                "sort_order": index,
                "part_of_speech": definition.part_of_speech.value,
                "meaning_zh": definition.meaning_zh,
                "meaning_en": definition.meaning_en,
                "example_sentences": [
                    example.model_dump(mode="json") for example in definition.example_sentences
                ],
                "notes_zh": definition.notes_zh,
            }
            for index, definition in enumerate(item.definitions)
        ]
        self.db.table("vocabulary_definitions").insert(rows).execute()

    def _load_vocabulary_out(self, vocabulary_id: UUID) -> VocabularyOut:
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

    def _persist_grammar(
        self,
        item: GrammarItemInput,
        ingestion_id: UUID,
        user_id: str | None,
        source_type: SourceType,
    ) -> GrammarOut:
        entry_hash = grammar_entry_hash(item.grammar_point)
        existing = (
            self.db.table("grammars")
            .select("id")
            .eq("content_hash", entry_hash)
            .maybe_single()
            .execute()
        )
        if existing is not None and existing.data:
            return self._load_grammar_out(UUID(existing.data["id"]))

        grammar_result = (
            self.db.table("grammars")
            .insert(
                {
                    "grammar_point": item.grammar_point,
                    "jlpt_level": item.jlpt_level,
                    "content_hash": entry_hash,
                    "source_type": source_type.value,
                    "ingestion_id": str(ingestion_id),
                    "created_by": user_id,
                }
            )
            .execute()
        )
        grammar_id = UUID(grammar_result.data[0]["id"])
        self._insert_grammar_usages(grammar_id, item)
        return self._load_grammar_out(grammar_id)

    def _load_grammar_out(self, grammar_id: UUID) -> GrammarOut:
        return grammar_service.get_grammar(grammar_id)


ingestion_service = IngestionService()


def _build_report(vocab: PersistStats, grammar: PersistStats) -> SyncReport:
    return SyncReport(
        vocab_source_rows=vocab.source_rows,
        vocab_new=vocab.new,
        vocab_updated=vocab.updated,
        vocab_skipped=vocab.skipped,
        vocab_dedupe_removed=vocab.dedupe_removed,
        grammar_source_rows=grammar.source_rows,
        grammar_new=grammar.new,
        grammar_updated=grammar.updated,
        grammar_skipped=grammar.skipped,
        grammar_dedupe_removed=grammar.dedupe_removed,
    )


def _chunks(items: list, size: int) -> list[list]:
    return [items[index : index + size] for index in range(0, len(items), size)]

