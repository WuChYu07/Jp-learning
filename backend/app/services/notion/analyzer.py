"""Analyze Notion flat blocks into sections and validation metrics."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.services.notion.client import FlatBlock

HEADING_TYPES = {"heading_1", "heading_2", "heading_3"}
TEXT_TYPES = {
    "paragraph",
    "bulleted_list_item",
    "numbered_list_item",
    "to_do",
    "quote",
    "callout",
    "toggle",
    "code",
}


@dataclass
class SectionPreview:
    heading: str | None
    heading_level: int | None
    text_lines: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    table_rows: list[list[str]] = field(default_factory=list)
    block_ids: list[str] = field(default_factory=list)


@dataclass
class NotionAnalysisResult:
    total_blocks: int
    type_counts: dict[str, int]
    sections: list[SectionPreview]
    orphan_images: list[str]
    has_tables: bool
    table_row_count: int
    image_count: int
    heading_count: int
    text_block_count: int


def analyze_blocks(blocks: list[FlatBlock]) -> NotionAnalysisResult:
    sections = build_sections(blocks)
    type_counts = dict(Counter(block.type for block in blocks))
    orphan_images = _collect_orphan_images(sections)
    image_count = sum(1 for block in blocks if block.type == "image")
    table_row_count = sum(1 for block in blocks if block.type == "table_row")
    heading_count = sum(1 for block in blocks if block.type in HEADING_TYPES)
    text_block_count = sum(1 for block in blocks if block.type in TEXT_TYPES)

    return NotionAnalysisResult(
        total_blocks=len(blocks),
        type_counts=type_counts,
        sections=sections,
        orphan_images=orphan_images,
        has_tables=type_counts.get("table", 0) > 0,
        table_row_count=table_row_count,
        image_count=image_count,
        heading_count=heading_count,
        text_block_count=text_block_count,
    )


def build_sections(blocks: list[FlatBlock]) -> list[SectionPreview]:
    sections: list[SectionPreview] = []
    current: SectionPreview | None = None

    for block in blocks:
        if block.type in HEADING_TYPES:
            if current is not None:
                sections.append(current)
            level = int(block.type.split("_")[1])
            current = SectionPreview(
                heading=block.text or None,
                heading_level=level,
                block_ids=[block.id],
            )
            continue

        if current is None:
            current = SectionPreview(heading=None, heading_level=None)

        current.block_ids.append(block.id)

        if block.type in TEXT_TYPES and block.text.strip():
            prefix = "• " if block.type == "bulleted_list_item" else ""
            if block.type == "numbered_list_item":
                prefix = "1. "
            current.text_lines.append(prefix + block.text.strip())
        elif block.type == "image" and block.image_url:
            current.image_urls.append(block.image_url)
        elif block.type == "table_row" and block.table_rows:
            current.table_rows.append(block.table_rows)

    if current is not None:
        sections.append(current)

    return sections


def attach_images_to_sections(sections: list[SectionPreview]) -> list[SectionPreview]:
    """No-op helper — images are attached during build_sections; kept for Phase 1 reuse."""
    return sections


def _collect_orphan_images(sections: list[SectionPreview]) -> list[str]:
    orphans: list[str] = []
    for section in sections:
        if section.heading is None and section.image_urls:
            orphans.extend(section.image_urls)
    return orphans


def sections_to_json(sections: list[SectionPreview], *, limit: int = 20) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for section in sections[:limit]:
        preview.append(
            {
                "heading": section.heading,
                "heading_level": section.heading_level,
                "text_preview": section.text_lines[:5],
                "text_line_count": len(section.text_lines),
                "image_count": len(section.image_urls),
                "image_urls": section.image_urls[:3],
                "table_row_count": len(section.table_rows),
            }
        )
    return preview


def build_validation_checklist(
    *,
    page: dict[str, Any] | None,
    analysis: NotionAnalysisResult,
    image_download_ok: bool | None,
    api_error: str | None,
    image_download_successes: int = 0,
    image_download_attempts: int = 0,
) -> dict[str, Any]:
    has_images_in_note = analysis.image_count > 0
    has_tables_in_note = analysis.has_tables

    if has_images_in_note and image_download_attempts > 0:
        downloadable = image_download_successes > 0
    else:
        downloadable = (not has_images_in_note) or image_download_ok is True

    checks = {
        "page_metadata_readable": page is not None and bool(page.get("id")),
        "recursive_fetch_complete": api_error is None,
        "heading_content_structure": analysis.heading_count > 0 and analysis.text_block_count > 0,
        "image_blocks_present": (not has_images_in_note) or analysis.image_count >= 1,
        "image_urls_downloadable": downloadable,
        "images_linked_to_sections": (not has_images_in_note)
        or (analysis.image_count > 0 and len(analysis.orphan_images) < analysis.image_count),
        "table_blocks_parseable": (not has_tables_in_note) or analysis.table_row_count > 0,
        "no_auth_errors": api_error is None,
    }

    checks["all_passed"] = all(checks.values())
    checks["orphan_image_count"] = len(analysis.orphan_images)
    checks["image_download_successes"] = image_download_successes
    checks["image_download_attempts"] = image_download_attempts
    checks["notes"] = []
    if analysis.orphan_images:
        checks["notes"].append(
            f"{len(analysis.orphan_images)} image(s) appear before any heading (orphan_images)."
        )
    if has_images_in_note and image_download_attempts > 0 and image_download_successes == 0:
        checks["notes"].append(
            "Sample image downloads all failed — check network or Notion file permissions."
        )
    elif has_images_in_note and image_download_attempts > 0 and image_download_successes < image_download_attempts:
        checks["notes"].append(
            f"Downloaded {image_download_successes}/{image_download_attempts} sample images "
            "(some URLs may have expired during long page fetches)."
        )

    return checks
