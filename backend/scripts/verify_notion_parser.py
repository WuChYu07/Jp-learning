"""Verify grammar block parser against cached grammar_structure.json.

Usage (from backend/):
    python scripts/verify_notion_parser.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.notion.client import FlatBlock
from app.services.notion.parser import parse_blocks

STRUCTURE_PATH = BACKEND_ROOT.parent / "data" / "reports" / "notion_probe" / "grammar_structure.json"
OUTPUT_PATH = BACKEND_ROOT.parent / "data" / "reports" / "notion_probe" / "parser_verify.json"


def _structure_to_blocks(rows: list[dict]) -> list[FlatBlock]:
    blocks: list[FlatBlock] = []
    for idx, row in enumerate(rows):
        block_type = row["type"]
        image_url = "https://example.com/img.png" if row.get("has_image") else None
        blocks.append(
            FlatBlock(
                id=f"block-{idx}",
                type=block_type,
                depth=int(row.get("depth", 0)),
                parent_id=None,
                text=row.get("text") or "",
                image_url=image_url,
            )
        )
    return blocks


def main() -> None:
    if not STRUCTURE_PATH.exists():
        raise SystemExit(f"Missing {STRUCTURE_PATH}")

    rows = json.loads(STRUCTURE_PATH.read_text(encoding="utf-8"))
    blocks = _structure_to_blocks(rows)
    result = parse_blocks(blocks, focus="grammar")

    false_positives = [
        g.grammar_point
        for g in result.grammars
        if g.grammar_point.startswith("例：") or g.grammar_point.startswith("例:")
    ]

    n3_topics = [
        g.grammar_point
        for g in result.grammars
        if any(k in g.grammar_point for k in ("間", "合う", "いくら", "一方"))
    ]

    ni_shimasu = next(
        (g for g in result.grammars if "にします" in g.grammar_point or "いAく" in g.grammar_point),
        None,
    )

    summary = {
        "grammar_count": len(result.grammars),
        "total_images": sum(len(g.image_urls) for g in result.grammars),
        "total_usages": sum(len(g.usages) for g in result.grammars),
        "multi_usage_grammars": sum(1 for g in result.grammars if len(g.usages) > 1),
        "false_positive_example_headings": false_positives,
        "n3_sample_topics": n3_topics[:12],
        "aidani_usages": next(
            (
                {
                    "grammar_point": g.grammar_point,
                    "usage_count": len(g.usages),
                    "usage_titles": [u.semantic_concept for u in g.usages],
                }
                for g in result.grammars
                if "間（あいだ）" in g.grammar_point
            ),
            None,
        ),
        "ippou_usages": next(
            (
                {
                    "grammar_point": g.grammar_point,
                    "usage_count": len(g.usages),
                    "usage_titles": [u.semantic_concept for u in g.usages],
                }
                for g in result.grammars
                if "一方" in g.grammar_point
            ),
            None,
        ),
        "ga_usages": next(
            (
                {
                    "grammar_point": g.grammar_point,
                    "usage_count": len(g.usages),
                    "usage_titles": [u.semantic_concept[:40] for u in g.usages[:8]],
                }
                for g in result.grammars
                if g.grammar_point == "がの使い方"
            ),
            None,
        ),
        "ni_shimasu": {
            "grammar_point": ni_shimasu.grammar_point if ni_shimasu else None,
            "image_count": len(ni_shimasu.image_urls) if ni_shimasu else 0,
            "usage_count": len(ni_shimasu.usages) if ni_shimasu else 0,
        },
        "first_20_titles": [g.grammar_point for g in result.grammars[:20]],
        "bracket_topics": [g.grammar_point for g in result.grammars if g.grammar_point in {"のは", "のが", "のを"}],
    }

    OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({summary['grammar_count']} grammar points)")


if __name__ == "__main__":
    main()
