"""Truncate learning content tables via Supabase service role."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.supabase import get_supabase_client

TABLES = [
    "user_vocab_progress",
    "user_grammar_progress",
    "vocabulary_definitions",
    "grammar_usages",
    "vocabularies",
    "grammars",
    "content_ingestions",
]


def main() -> None:
    db = get_supabase_client()
    print("Truncating learning content (delete all rows per table) ...")

    for table in TABLES:
        db.table(table).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        count = db.table(table).select("id", count="exact").limit(1).execute().count
        print(f"  {table}: {count} rows")

    print("Done. Schema and users preserved.")


if __name__ == "__main__":
    main()
