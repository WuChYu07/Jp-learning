"""Classify parsed Notion grammar items against DB state."""

from __future__ import annotations

from supabase import Client

from app.models.schemas.grammar import GrammarItemInput, SyncChange


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

        # Soft-deleted tombstones never resurface in preview/persist.
        if row.get("sync_status") == "archived":
            item.sync_change = "unchanged"
            unchanged_count += 1
            continue

        stored_hash = row.get("source_content_hash")
        if stored_hash and item.source_content_hash and stored_hash == item.source_content_hash:
            item.sync_change = "unchanged"
            unchanged_count += 1
        else:
            # Includes manually edited rows: persist will meta-update images only.
            item.sync_change = "updated"
            updated_count += 1

    return new_count, updated_count, unchanged_count
