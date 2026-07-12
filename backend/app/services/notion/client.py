"""Notion API client — recursive block fetch with pagination and rate limiting."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.http_client import create_sync_client

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
RATE_LIMIT_DELAY_SEC = 0.35


class NotionClientError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class FlatBlock:
    id: str
    type: str
    depth: int
    parent_id: str | None
    text: str = ""
    image_url: str | None = None
    table_rows: list[list[str]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def normalize_page_id(page_id: str) -> str:
    """Accept dashed or compact 32-char hex page IDs."""
    cleaned = page_id.strip().replace("-", "").lower()
    if len(cleaned) != 32:
        raise ValueError(
            f"Invalid Notion page ID: {page_id!r}. "
            "Expected 32 hex characters (from your Notion page URL)."
        )
    if cleaned == "x" * 32 or cleaned.count("x") >= 28:
        raise ValueError(
            "NOTION_PAGE_ID is still a placeholder (xxxxxxxx...). "
            "Copy the real ID from your Notion page URL — see backend/.env.example."
        )
    if not all(c in "0123456789abcdef" for c in cleaned):
        raise ValueError(
            f"Invalid Notion page ID: {page_id!r}. "
            "Page ID must contain only hex digits (0-9, a-f)."
        )
    if cleaned == "x" * 32 or cleaned.count("x") >= 28:
        raise ValueError(
            "NOTION_PAGE_ID is still a placeholder (xxxxxxxx...). "
            "Copy the real ID from your Notion page URL — see backend/.env.example."
        )
    return f"{cleaned[:8]}-{cleaned[8:12]}-{cleaned[12:16]}-{cleaned[16:20]}-{cleaned[20:]}"


def extract_page_id_from_url(url: str) -> str:
    """Extract page ID from a Notion page URL."""
    slug = url.rstrip("/").split("/")[-1]
    token = slug.split("-")[-1] if "-" in slug else slug
    token = token.split("?")[0]
    return normalize_page_id(token)


class NotionClient:
    def __init__(self, token: str) -> None:
        if not token.strip():
            raise NotionClientError("NOTION_TOKEN is empty")
        self._token = token.strip()
        self._client = create_sync_client(
            base_url=NOTION_API_BASE,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
        # S3 / external image URLs must NOT receive Notion auth headers.
        self._download_client = create_sync_client(timeout=120.0)
        self._last_request_at = 0.0

    def close(self) -> None:
        self._client.close()
        self._download_client.close()

    def __enter__(self) -> NotionClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < RATE_LIMIT_DELAY_SEC:
            time.sleep(RATE_LIMIT_DELAY_SEC - elapsed)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        self._throttle()
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise NotionClientError(f"Notion HTTP error: {exc}") from exc
        finally:
            self._last_request_at = time.monotonic()

        if response.status_code >= 400:
            detail = response.text[:500]
            hint = _status_hint(response.status_code)
            raise NotionClientError(
                f"Notion API {response.status_code}: {detail}. {hint}".strip(),
                status_code=response.status_code,
            )
        return response.json()

    def get_page(self, page_id: str) -> dict[str, Any]:
        normalized = normalize_page_id(page_id)
        return self._request("GET", f"/pages/{normalized}")

    def get_block(self, block_id: str) -> dict[str, Any]:
        return self._request("GET", f"/blocks/{block_id}")

    def refresh_image_url(self, block_id: str) -> str | None:
        """Re-fetch an image block to obtain a fresh temporary download URL."""
        raw = self.get_block(block_id)
        if raw.get("type") != "image":
            return None
        return _image_url_from_raw(raw)

    def fetch_all_blocks(self, block_id: str, *, depth: int = 0, parent_id: str | None = None) -> list[FlatBlock]:
        normalized = normalize_page_id(block_id) if depth == 0 and _looks_like_page_id(block_id) else block_id
        return self._fetch_children_recursive(normalized, depth=depth, parent_id=parent_id)

    def _fetch_children_recursive(
        self,
        block_id: str,
        *,
        depth: int,
        parent_id: str | None,
    ) -> list[FlatBlock]:
        blocks: list[FlatBlock] = []
        start_cursor: str | None = None

        while True:
            params: dict[str, str] = {"page_size": "100"}
            if start_cursor:
                params["start_cursor"] = start_cursor

            payload = self._request("GET", f"/blocks/{block_id}/children", params=params)
            for raw in payload.get("results", []):
                flat = _flatten_block(raw, depth=depth, parent_id=parent_id)
                blocks.append(flat)
                if raw.get("has_children"):
                    blocks.extend(
                        self._fetch_children_recursive(
                            raw["id"],
                            depth=depth + 1,
                            parent_id=raw["id"],
                        )
                    )

            if not payload.get("has_more"):
                break
            start_cursor = payload.get("next_cursor")

        return blocks

    def download_image(self, url: str) -> tuple[bytes, str | None]:
        """Download image bytes from Notion temporary S3 URL (no Notion auth headers)."""
        self._throttle()
        try:
            response = self._download_client.get(url, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise NotionClientError(f"Image download failed: {exc}") from exc
        finally:
            self._last_request_at = time.monotonic()

        if response.status_code >= 400:
            raise NotionClientError(
                f"Image download HTTP {response.status_code}",
                status_code=response.status_code,
            )

        content_type = response.headers.get("content-type")
        return response.content, content_type


def _looks_like_page_id(value: str) -> bool:
    cleaned = value.replace("-", "")
    return len(cleaned) == 32 and all(c in "0123456789abcdef" for c in cleaned.lower())


def _status_hint(status_code: int) -> str:
    if status_code == 401:
        return "Check NOTION_TOKEN is valid."
    if status_code == 403:
        return "Share the page with your integration (Connections menu)."
    if status_code == 404:
        return "Page or block not found — verify NOTION_PAGE_ID."
    if status_code == 400:
        return (
            "Page ID may be invalid or still a placeholder. "
            "Use the 32-char hex from your Notion page URL."
        )
    return ""


def extract_page_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            return _rich_text_to_plain(prop.get("title", []))
    return "Untitled"


def _rich_text_to_plain(rich_text: list[dict[str, Any]]) -> str:
    return "".join(part.get("plain_text", "") for part in rich_text).strip()


def _flatten_block(raw: dict[str, Any], *, depth: int, parent_id: str | None) -> FlatBlock:
    block_type = raw.get("type", "unsupported")
    payload = raw.get(block_type, {}) if block_type in raw else {}
    text = ""
    image_url: str | None = None
    table_rows: list[list[str]] = []

    if block_type in {"heading_1", "heading_2", "heading_3", "paragraph", "bulleted_list_item", "numbered_list_item"}:
        text = _rich_text_to_plain(payload.get("rich_text", []))
    elif block_type == "to_do":
        prefix = "[x] " if payload.get("checked") else "[ ] "
        text = prefix + _rich_text_to_plain(payload.get("rich_text", []))
    elif block_type == "quote":
        text = _rich_text_to_plain(payload.get("rich_text", []))
    elif block_type == "callout":
        text = _rich_text_to_plain(payload.get("rich_text", []))
    elif block_type == "toggle":
        text = _rich_text_to_plain(payload.get("rich_text", []))
    elif block_type == "code":
        text = _rich_text_to_plain(payload.get("rich_text", []))
    elif block_type == "image":
        image_url = _image_url_from_raw(raw)
        caption = _rich_text_to_plain(payload.get("caption", []))
        text = caption
    elif block_type == "table_row":
        table_rows = [
            _rich_text_to_plain(cell) for cell in payload.get("cells", [])
        ]

    return FlatBlock(
        id=raw["id"],
        type=block_type,
        depth=depth,
        parent_id=parent_id,
        text=text,
        image_url=image_url,
        table_rows=table_rows,
        raw=raw,
    )


def _image_url_from_raw(raw: dict[str, Any]) -> str | None:
    payload = raw.get("image", {}) if raw.get("type") == "image" else {}
    file_obj = payload.get("file") or payload.get("external") or {}
    return file_obj.get("url")
