"""One-off: dump full structural outline of a Notion page for parser design.

Usage (from backend/):
    python scripts/dump_notion_outline.py --focus grammar
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.services.notion.analyzer import build_sections
from app.services.notion.client import NotionClient
from app.services.notion.pages import resolve_page_targets


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump Notion page outline")
    parser.add_argument("--focus", choices=["vocabulary", "grammar"], default="grammar")
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND_ROOT.parent / "data" / "reports" / "notion_probe",
    )
    args = parser.parse_args()

    (page_focus, page_id) = resolve_page_targets(args.focus)[0]
    out_dir = args.output.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    with NotionClient(settings.NOTION_TOKEN) as client:
        blocks = client.fetch_all_blocks(page_id)

    # 1. Flat outline: indentation by depth, type tag, text preview
    outline_lines: list[str] = []
    for b in blocks:
        indent = "  " * b.depth
        text = (b.text or "").replace("\n", " ")[:90]
        marker = ""
        if b.type == "image":
            marker = " [IMG]"
        elif b.type == "table_row":
            marker = " [ROW: " + " | ".join(b.table_rows) + "]"
        outline_lines.append(f"{indent}<{b.type}>{marker} {text}")
    (out_dir / f"{page_focus}_outline.txt").write_text("\n".join(outline_lines), encoding="utf-8")

    # 2. Full sections (no truncation)
    sections = build_sections(blocks)
    full = []
    for s in sections:
        full.append(
            {
                "heading": s.heading,
                "heading_level": s.heading_level,
                "text_lines": s.text_lines,
                "image_count": len(s.image_urls),
                "table_rows": s.table_rows,
            }
        )
    (out_dir / f"{page_focus}_full_sections.json").write_text(
        json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"blocks: {len(blocks)} | sections: {len(sections)}")
    print(f"outline -> {out_dir / f'{page_focus}_outline.txt'}")
    print(f"sections -> {out_dir / f'{page_focus}_full_sections.json'}")


if __name__ == "__main__":
    main()
