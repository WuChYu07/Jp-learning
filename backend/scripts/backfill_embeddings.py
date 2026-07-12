"""
Backfill Gemini embeddings + same_meaning links for existing content.

Usage (from backend/):
  python -m scripts.backfill_embeddings
  python -m scripts.backfill_embeddings --grammar-only --limit 50
  python -m scripts.backfill_embeddings --vocab-only
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.supabase import get_supabase_client  # noqa: E402
from app.services.semantic_link_service import semantic_link_service  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill content embeddings")
    parser.add_argument("--grammar-only", action="store_true")
    parser.add_argument("--vocab-only", action="store_true")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--sleep", type=float, default=0.35, help="Delay between embeds")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    db = get_supabase_client()
    do_grammar = not args.vocab_only
    do_vocab = not args.grammar_only

    if do_grammar:
        rows = (
            db.table("grammars")
            .select("id, grammar_point")
            .neq("sync_status", "archived")
            .order("grammar_point")
            .limit(args.limit)
            .execute()
        ).data or []
        print(f"Grammar to sync: {len(rows)}")
        for i, row in enumerate(rows, 1):
            result = semantic_link_service.sync_grammar(UUID(row["id"]), force=args.force)
            print(f"  [{i}/{len(rows)}] {row['grammar_point'][:40]!r} -> {result}")
            time.sleep(args.sleep)

    if do_vocab:
        rows = (
            db.table("vocabularies")
            .select("id, word")
            .order("word")
            .limit(args.limit)
            .execute()
        ).data or []
        print(f"Vocab to sync: {len(rows)}")
        for i, row in enumerate(rows, 1):
            result = semantic_link_service.sync_vocabulary(UUID(row["id"]), force=args.force)
            print(f"  [{i}/{len(rows)}] {row['word'][:40]!r} -> {result}")
            time.sleep(args.sleep)

    print("Done.")


if __name__ == "__main__":
    main()
