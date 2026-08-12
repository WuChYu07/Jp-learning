"""Reusable writer: persist Claude's manually-authored grammar content
(read directly from Notion images) without any AI call. Mirrors the shape
grammar_enrichment_service._persist_enrichment writes, minus the Gemini call.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.supabase import get_supabase_client  # noqa: E402

db = get_supabase_client()


def write_content(grammar_id: str, jlpt_level: str, usages: list[dict]) -> None:
    """usages: list of {semantic_concept, connection_rule, meaning_zh,
    meaning_blocks: [{text, variant}], example_sentences: [{japanese, reading, chinese, highlights}]}
    """
    db.table("grammars").update({"jlpt_level": jlpt_level}).eq("id", grammar_id).execute()
    db.table("grammar_usages").delete().eq("grammar_id", grammar_id).execute()
    rows = []
    for i, u in enumerate(usages):
        rows.append(
            {
                "grammar_id": grammar_id,
                "sort_order": i,
                "semantic_concept": u["semantic_concept"],
                "connection_rule": u["connection_rule"],
                "meaning_zh": u["meaning_zh"],
                "meaning_en": None,
                "meaning_blocks": u.get("meaning_blocks", []),
                "example_sentences": u.get("example_sentences", []),
            }
        )
    if rows:
        db.table("grammar_usages").insert(rows).execute()
    print(f"wrote {grammar_id}: jlpt={jlpt_level}, usages={len(rows)}")
