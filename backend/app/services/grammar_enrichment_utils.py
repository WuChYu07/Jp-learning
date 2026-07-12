"""Detect when a grammar item should be enriched from images."""


def needs_image_enrichment(*, image_urls: list[str]) -> bool:
    """Any grammar with stored Notion images can be enriched (or re-enriched)."""
    return bool(image_urls)
