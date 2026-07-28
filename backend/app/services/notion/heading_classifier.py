"""AI-backed cache for classifying ambiguous grammar headings.

Decides whether a top-level Notion heading is a JLPT/category label (its
heading_2 children are each an independent grammar point, e.g. "N2文法") or a
grammar point itself (its children are usage variants of that one point,
e.g. "て形"). Classified once per notion_block_id via
`notion_heading_classifications`, so re-syncing an unchanged page never
re-asks Gemini — only genuinely new headings do.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from google.genai import types
from supabase import Client

from app.core.config import settings
from app.services.gemini_client import is_quota_error, run_with_key_failover
from app.services.notion.parser import HeadingCandidate

logger = logging.getLogger(__name__)

_PROMPT = """You are organizing a Traditional-Chinese speaker's Japanese grammar notes from Notion.
For each heading below, decide whether it is:
- "category": just a JLPT-level or topic LABEL. Every item listed under it is an INDEPENDENT grammar point that deserves its own separate entry (e.g. a heading "N2文法" listing several unrelated grammar patterns).
- "topic": the heading IS itself one specific grammar point/pattern. The items listed under it are different USAGES, explanations, or facets of that SAME point, not separate grammar points (e.g. a heading "て形" whose items are usage variants of て形).

Headings (id: heading text — children):
{items}

Return ONLY valid JSON mapping each id to "category" or "topic", nothing else:
{{"id1": "category", "id2": "topic"}}
"""


@dataclass
class HeadingClassificationResult:
    category_block_ids: set[str] = field(default_factory=set)
    # Headings that couldn't be classified this run (AI unavailable / bad
    # response) — surfaced to the user rather than silently guessed.
    failed: list[dict] = field(default_factory=list)


def classify_headings(
    candidates: list[HeadingCandidate], db: Client
) -> HeadingClassificationResult:
    if not candidates:
        return HeadingClassificationResult()

    by_id = {c.block_id: c for c in candidates}
    block_ids = list(by_id.keys())

    cached_category: set[str] = set()
    cached_ids: set[str] = set()
    for batch_start in range(0, len(block_ids), 200):
        batch = block_ids[batch_start : batch_start + 200]
        try:
            result = (
                db.table("notion_heading_classifications")
                .select("notion_block_id, is_category")
                .in_("notion_block_id", batch)
                .execute()
            )
        except Exception:
            logger.warning(
                "notion_heading_classifications lookup failed; treating this batch as "
                "uncached (migration 021 may not be applied yet)"
            )
            continue
        for row in result.data or []:
            cached_ids.add(row["notion_block_id"])
            if row.get("is_category"):
                cached_category.add(row["notion_block_id"])

    uncached = [c for c in candidates if c.block_id not in cached_ids]
    if not uncached:
        return HeadingClassificationResult(category_block_ids=cached_category)

    decisions, failed_ids = _classify_via_gemini(uncached)

    new_category: set[str] = set()
    rows_to_upsert = []
    for candidate in uncached:
        decision = decisions.get(candidate.block_id)
        if decision is None:
            continue
        is_category = decision == "category"
        if is_category:
            new_category.add(candidate.block_id)
        rows_to_upsert.append(
            {
                "notion_block_id": candidate.block_id,
                "heading_text": candidate.heading_text,
                "is_category": is_category,
            }
        )

    if rows_to_upsert:
        try:
            db.table("notion_heading_classifications").upsert(
                rows_to_upsert, on_conflict="notion_block_id"
            ).execute()
        except Exception:
            logger.warning(
                "failed to persist heading classification cache; these headings will "
                "be re-classified next sync"
            )

    failed = [
        {"notion_block_id": by_id[bid].block_id, "heading_text": by_id[bid].heading_text}
        for bid in failed_ids
    ]

    return HeadingClassificationResult(
        category_block_ids=cached_category | new_category, failed=failed
    )


def _classify_via_gemini(
    candidates: list[HeadingCandidate],
) -> tuple[dict[str, str], list[str]]:
    """Returns (decisions_by_block_id, failed_block_ids)."""
    items_text = "\n".join(
        f"{c.block_id}: {c.heading_text} — {', '.join(c.children[:15])}" for c in candidates
    )
    prompt = _PROMPT.format(items=items_text)

    try:
        response = run_with_key_failover(
            lambda client: client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=4096,
                    # This is a plain classification task with no need for extended
                    # reasoning — on thinking-capable models (e.g. gemini-2.5-flash)
                    # thinking tokens otherwise eat max_output_tokens first and can
                    # truncate the JSON before it's complete.
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
        )
    except Exception as exc:
        if is_quota_error(exc):
            logger.warning("heading classification skipped: Gemini quota exhausted")
        else:
            logger.exception("heading classification Gemini call failed")
        return {}, [c.block_id for c in candidates]

    try:
        raw = response.text or ""
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("not an object")
    except (json.JSONDecodeError, ValueError):
        logger.warning("heading classification returned invalid JSON; treating as failed")
        return {}, [c.block_id for c in candidates]

    decisions: dict[str, str] = {}
    for c in candidates:
        value = parsed.get(c.block_id)
        if value in {"category", "topic"}:
            decisions[c.block_id] = value

    failed_ids = [c.block_id for c in candidates if c.block_id not in decisions]
    return decisions, failed_ids
