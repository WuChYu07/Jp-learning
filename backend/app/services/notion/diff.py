"""Classify parsed Notion items against DB state."""

from __future__ import annotations

from dataclasses import dataclass

from supabase import Client

from app.models.schemas.grammar import GrammarItemInput
from app.models.schemas.vocab import VocabularyItemInput
from app.services.hash_service import vocab_entry_hash, vocab_source_hash


@dataclass
class OrphanedGrammarRow:
    id: str
    grammar_point: str
    notion_block_id: str | None
    notion_page_id: str | None


def annotate_grammar_sync_changes(
    items: list[GrammarItemInput],
    db: Client,
    *,
    notion_page_id: str | None = None,
) -> tuple[int, int, int]:
    """Set sync_change on each item. Returns (new, updated, unchanged) counts."""
    if not items:
        return 0, 0, 0

    block_ids = [item.notion_block_id for item in items if item.notion_block_id]
    existing_by_block: dict[str, dict] = {}

    if block_ids:
        for batch_start in range(0, len(block_ids), 100):
            batch = block_ids[batch_start : batch_start + 100]
            result = (
                db.table("grammars")
                .select(
                    "id, notion_block_id, source_content_hash, grammar_point, "
                    "sync_status, manual_edited_at"
                )
                .in_("notion_block_id", batch)
                .execute()
            )
            for row in result.data or []:
                bid = row.get("notion_block_id")
                if bid:
                    existing_by_block[bid] = row

    new_count = updated_count = unchanged_count = 0

    for item in items:
        if not item.notion_block_id:
            item.sync_change = "new"
            new_count += 1
            continue

        row = existing_by_block.get(item.notion_block_id)
        if row is None:
            item.sync_change = "new"
            new_count += 1
            continue

        if row.get("sync_status") == "archived":
            item.sync_change = "unchanged"
            unchanged_count += 1
            continue

        stored_hash = row.get("source_content_hash")
        if stored_hash and item.source_content_hash and stored_hash == item.source_content_hash:
            item.sync_change = "unchanged"
            unchanged_count += 1
        else:
            item.sync_change = "updated"
            updated_count += 1

    return new_count, updated_count, unchanged_count


def annotate_vocab_sync_changes(
    items: list[VocabularyItemInput],
    db: Client,
) -> tuple[int, int, int]:
    """Set sync_change on vocab items. Returns (new, updated, unchanged) counts.

    Diffs against `vocabularies.notion_source_hash` — a snapshot of what Notion
    had at last sync — rather than the DB's current definitions, so AI-enriched
    content (meaning/notes/examples added after sync) never shows up as a false
    "updated".
    """
    if not items:
        return 0, 0, 0

    hash_map: dict[str, VocabularyItemInput] = {}
    for item in items:
        hash_map[vocab_entry_hash(item.word, item.reading)] = item

    existing_by_hash: dict[str, dict] = {}
    for batch_start in range(0, len(hash_map), 100):
        batch = list(hash_map.keys())[batch_start : batch_start + 100]
        result = (
            db.table("vocabularies")
            .select("id, content_hash, notion_source_hash")
            .in_("content_hash", batch)
            .execute()
        )
        for row in result.data or []:
            existing_by_hash[row["content_hash"]] = row

    new_count = updated_count = unchanged_count = 0
    backfill: list[dict] = []

    for entry_hash, item in hash_map.items():
        row = existing_by_hash.get(entry_hash)
        if row is None:
            item.sync_change = "new"
            new_count += 1
            continue

        notion_hash = vocab_source_hash(
            word=item.word,
            reading=item.reading,
            definitions=item.definitions,
        )
        stored = row.get("notion_source_hash")

        if stored is None:
            # No baseline yet (entry predates this column, e.g. already
            # AI-enriched). Freeze current Notion content as the baseline
            # instead of flagging a false "updated" this one time.
            item.sync_change = "unchanged"
            unchanged_count += 1
            backfill.append({"id": row["id"], "notion_source_hash": notion_hash})
        elif stored == notion_hash:
            item.sync_change = "unchanged"
            unchanged_count += 1
        else:
            item.sync_change = "updated"
            updated_count += 1

    for entry in backfill:
        try:
            db.table("vocabularies").update(
                {"notion_source_hash": entry["notion_source_hash"]}
            ).eq("id", entry["id"]).execute()
        except Exception:
            pass

    return new_count, updated_count, unchanged_count


def find_orphaned_notion_grammars(
    db: Client,
    *,
    notion_page_ids: list[str],
    present_block_ids: set[str],
) -> list[OrphanedGrammarRow]:
    """Grammars in DB for these Notion pages but absent from current parse."""
    if not notion_page_ids:
        return []

    orphans: list[OrphanedGrammarRow] = []
    for page_id in notion_page_ids:
        offset = 0
        page_size = 200
        while True:
            result = (
                db.table("grammars")
                .select("id, grammar_point, notion_block_id, notion_page_id, sync_status")
                .eq("notion_page_id", page_id)
                .neq("sync_status", "archived")
                .not_.is_("notion_block_id", "null")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            rows = result.data or []
            if not rows:
                break
            for row in rows:
                bid = row.get("notion_block_id")
                if bid and bid not in present_block_ids:
                    orphans.append(
                        OrphanedGrammarRow(
                            id=row["id"],
                            grammar_point=row.get("grammar_point") or "",
                            notion_block_id=bid,
                            notion_page_id=row.get("notion_page_id"),
                        )
                    )
            if len(rows) < page_size:
                break
            offset += page_size

    return orphans


def filter_sync_preview_items(
    grammars: list[GrammarItemInput],
    vocabularies: list[VocabularyItemInput],
) -> None:
    """Remove unchanged rows from preview payload (in-place on caller lists)."""
    grammars[:] = [g for g in grammars if g.sync_change != "unchanged"]
    vocabularies[:] = [v for v in vocabularies if v.sync_change != "unchanged"]
