"""
Bulk-load curated CSV files into Supabase.

Usage:
    cd backend
    python scripts/load_curated.py                  # load both vocab + grammar
    python scripts/load_curated.py --vocab-only      # load only vocabulary
    python scripts/load_curated.py --grammar-only    # load only grammar
    python scripts/load_curated.py --clear            # truncate before loading
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.supabase import get_supabase_client
from app.services.hash_service import grammar_entry_hash, vocab_entry_hash

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "curated"
VOCAB_CSV = DATA_DIR / "vocabulary.csv"
GRAMMAR_CSV = DATA_DIR / "grammar.csv"

db = get_supabase_client()


def load_vocabulary(clear: bool = False) -> int:
    if not VOCAB_CSV.exists():
        print(f"  [skip] {VOCAB_CSV} not found")
        return 0

    if clear:
        db.table("vocabulary_definitions").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        db.table("vocabularies").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print("  [clear] vocabulary tables truncated")

    rows = list(csv.DictReader(VOCAB_CSV.open(encoding="utf-8")))
    print(f"  Reading {len(rows)} vocabulary rows from CSV")

    inserted = 0
    for row in rows:
        word = (row.get("kanji") or "").strip()
        kana = (row.get("kana") or "").strip()
        if not word and not kana:
            continue

        display_word = word or kana
        reading = kana if word else None
        meaning = (row.get("meaning") or "").strip()
        if not meaning:
            continue

        pos = (row.get("part_of_speech") or "other").strip().lower().replace("-", "_").replace(" ", "_")
        jlpt = (row.get("jlpt_level") or "unknown").strip().upper()
        if jlpt not in ("N5", "N4", "N3", "N2", "N1"):
            jlpt = "unknown"

        content_hash = vocab_entry_hash(display_word, reading)

        existing = (
            db.table("vocabularies")
            .select("id")
            .eq("content_hash", content_hash)
            .maybe_single()
            .execute()
        )
        if existing and existing.data:
            continue

        vocab_row = db.table("vocabularies").insert({
            "word": display_word,
            "reading": reading,
            "jlpt_level": jlpt,
            "content_hash": content_hash,
            "source_type": "manual",
        }).execute()

        vocab_id = vocab_row.data[0]["id"]

        example_sentences = []
        ex_jp = (row.get("example_sentence") or "").strip()
        if ex_jp:
            example_sentences.append({
                "japanese": ex_jp,
                "reading": (row.get("example_reading") or "").strip() or None,
                "chinese": (row.get("example_chinese") or "").strip() or None,
            })

        valid_pos = [
            "noun", "verb", "i_adjective", "na_adjective",
            "adverb", "particle", "counter", "expression", "other",
        ]
        if pos not in valid_pos:
            pos = "other"

        db.table("vocabulary_definitions").insert({
            "vocabulary_id": vocab_id,
            "sort_order": 0,
            "part_of_speech": pos,
            "meaning_zh": meaning,
            "example_sentences": json.dumps(example_sentences, ensure_ascii=False),
        }).execute()

        inserted += 1

    print(f"  [vocab] Inserted {inserted} new entries (skipped {len(rows) - inserted} duplicates)")
    return inserted


def load_grammar(clear: bool = False) -> int:
    if not GRAMMAR_CSV.exists():
        print(f"  [skip] {GRAMMAR_CSV} not found")
        return 0

    if clear:
        db.table("grammar_usages").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        db.table("grammars").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print("  [clear] grammar tables truncated")

    rows = list(csv.DictReader(GRAMMAR_CSV.open(encoding="utf-8")))
    print(f"  Reading {len(rows)} grammar rows from CSV")

    inserted = 0
    for row in rows:
        grammar_point = (row.get("grammar_point") or "").strip()
        if not grammar_point:
            continue

        semantic_concept = (row.get("semantic_concept") or "").strip()
        connection_rule = (row.get("connection_rule") or "").strip()
        meaning_zh = (row.get("meaning_zh") or "").strip()
        jlpt = (row.get("jlpt_level") or "unknown").strip().upper()
        if jlpt not in ("N5", "N4", "N3", "N2", "N1"):
            jlpt = "unknown"

        content_hash = grammar_entry_hash(grammar_point)

        existing = (
            db.table("grammars")
            .select("id")
            .eq("content_hash", content_hash)
            .maybe_single()
            .execute()
        )

        if existing and existing.data:
            grammar_id = existing.data["id"]
        else:
            grammar_row = db.table("grammars").insert({
                "grammar_point": grammar_point,
                "jlpt_level": jlpt,
                "content_hash": content_hash,
                "source_type": "manual",
            }).execute()
            grammar_id = grammar_row.data[0]["id"]
            inserted += 1

        existing_usages = (
            db.table("grammar_usages")
            .select("id")
            .eq("grammar_id", grammar_id)
            .eq("semantic_concept", semantic_concept)
            .maybe_single()
            .execute()
        )
        if existing_usages and existing_usages.data:
            continue

        usage_count = (
            db.table("grammar_usages")
            .select("id", count="exact")
            .eq("grammar_id", grammar_id)
            .limit(1)
            .execute()
        ).count or 0

        example_sentences = []
        ex_jp = (row.get("example_japanese") or "").strip()
        if ex_jp:
            example_sentences.append({
                "japanese": ex_jp,
                "reading": (row.get("example_reading") or "").strip() or None,
                "chinese": (row.get("example_chinese") or "").strip() or None,
            })

        db.table("grammar_usages").insert({
            "grammar_id": grammar_id,
            "sort_order": usage_count,
            "semantic_concept": semantic_concept or grammar_point,
            "connection_rule": connection_rule or "",
            "meaning_zh": meaning_zh or None,
            "example_sentences": json.dumps(example_sentences, ensure_ascii=False),
        }).execute()

    print(f"  [grammar] Inserted {inserted} new grammar points (skipped duplicates)")
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Load curated CSV data into Supabase")
    parser.add_argument("--vocab-only", action="store_true")
    parser.add_argument("--grammar-only", action="store_true")
    parser.add_argument("--clear", action="store_true", help="Truncate tables before loading")
    args = parser.parse_args()

    print("=== Komorebi CSV Loader ===")

    if not args.grammar_only:
        load_vocabulary(clear=args.clear)
    if not args.vocab_only:
        load_grammar(clear=args.clear)

    print("=== Done ===")


if __name__ == "__main__":
    main()
