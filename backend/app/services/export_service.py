"""Full-data JSON backup export (read-only; no re-import path)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from supabase import Client

from app.db.supabase import get_supabase_client

_PAGE_SIZE = 1000

# Core learning content + irreplaceable user history. Vector embeddings and
# caches (content_embeddings, content_ingestions, notion_heading_classifications)
# are excluded — they're regenerable from this data via backfill_embeddings.py
# and Notion re-sync, and would dominate the file size for no backup value.
_TABLES = [
    "vocabularies",
    "vocabulary_definitions",
    "grammars",
    "grammar_usages",
    "user_vocab_progress",
    "user_grammar_progress",
    "exam_attempts",
    "practice_dialogues",
    "songs",
    "song_lines",
    "user_song_history",
    "content_links",
]


class ExportService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def _fetch_all(self, table: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            result = (
                self.db.table(table)
                .select("*")
                .range(offset, offset + _PAGE_SIZE - 1)
                .execute()
            )
            batch = result.data or []
            rows.extend(batch)
            if len(batch) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
        return rows

    def export_all(self) -> dict[str, Any]:
        return {
            "exported_at": datetime.now(UTC).isoformat(),
            "app": "komorebi-japanese",
            "schema_version": 1,
            "note": (
                "Read-only backup. Vector embeddings excluded (regenerate via "
                "backend/scripts/backfill_embeddings.py --force)."
            ),
            "tables": {table: self._fetch_all(table) for table in _TABLES},
        }


export_service = ExportService()
