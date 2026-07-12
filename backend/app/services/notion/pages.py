"""Resolve Notion page IDs by content type (vocabulary / grammar)."""

from __future__ import annotations

from typing import Literal

from app.core.config import settings
from app.services.notion.client import normalize_page_id

NotionFocus = Literal["vocabulary", "grammar", "both"]


class NotionPageConfigError(ValueError):
    pass


def resolve_page_targets(
    focus: NotionFocus,
    *,
    page_id: str | None = None,
    vocab_page_id: str | None = None,
    grammar_page_id: str | None = None,
) -> list[tuple[NotionFocus, str]]:
    """Return (focus, normalized_page_id) pairs to fetch."""
    if page_id:
        normalized = normalize_page_id(page_id)
        if focus == "both":
            raise NotionPageConfigError(
                "Cannot use a single page_id with focus='both'. "
                "Set NOTION_VOCAB_PAGE_ID and NOTION_GRAMMAR_PAGE_ID, or sync each page separately."
            )
        return [(focus, normalized)]

    vocab_id = (vocab_page_id or settings.NOTION_VOCAB_PAGE_ID or settings.NOTION_PAGE_ID).strip()
    grammar_id = (grammar_page_id or settings.NOTION_GRAMMAR_PAGE_ID or settings.NOTION_PAGE_ID).strip()

    if focus == "vocabulary":
        if not vocab_id:
            raise NotionPageConfigError(
                "NOTION_VOCAB_PAGE_ID is required for vocabulary sync."
            )
        return [("vocabulary", normalize_page_id(vocab_id))]

    if focus == "grammar":
        if not grammar_id:
            raise NotionPageConfigError(
                "NOTION_GRAMMAR_PAGE_ID is required for grammar sync."
            )
        return [("grammar", normalize_page_id(grammar_id))]

    if not vocab_id or not grammar_id:
        raise NotionPageConfigError(
            "Both NOTION_VOCAB_PAGE_ID and NOTION_GRAMMAR_PAGE_ID are required for focus='both'."
        )
    if normalize_page_id(vocab_id) == normalize_page_id(grammar_id):
        raise NotionPageConfigError(
            "NOTION_VOCAB_PAGE_ID and NOTION_GRAMMAR_PAGE_ID must be different pages."
        )
    return [
        ("vocabulary", normalize_page_id(vocab_id)),
        ("grammar", normalize_page_id(grammar_id)),
    ]
