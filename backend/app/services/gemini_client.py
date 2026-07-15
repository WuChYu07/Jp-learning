"""Shared Gemini client with multi-key failover on free-tier quota errors."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TypeVar

from google import genai
from google.genai import types

from app.core.config import settings
from app.core.http_client import create_sync_client

logger = logging.getLogger(__name__)

T = TypeVar("T")

_lock = threading.Lock()
_preferred_index = 0
_exhausted: set[str] = set()
_clients: dict[str, genai.Client] = {}


def is_quota_error(exc: BaseException) -> bool:
    message = str(exc).upper()
    return (
        "429" in message
        or "RESOURCE_EXHAUSTED" in message
        or "QUOTA" in message
        or "RATE LIMIT" in message
        or "RATE_LIMIT" in message
    )


def gemini_keys() -> list[str]:
    return settings.gemini_api_key_list


def _client_for(api_key: str) -> genai.Client:
    client = _clients.get(api_key)
    if client is None:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(httpx_client=create_sync_client()),
        )
        _clients[api_key] = client
    return client


def mark_exhausted(api_key: str) -> None:
    with _lock:
        _exhausted.add(api_key)
        logger.warning(
            "Gemini key exhausted (suffix …%s); remaining usable=%s",
            api_key[-4:] if len(api_key) >= 4 else "????",
            sum(1 for k in gemini_keys() if k not in _exhausted),
        )


def reset_exhausted() -> None:
    """Clear in-memory exhausted markers (e.g. after midnight / process restart)."""
    with _lock:
        _exhausted.clear()
        global _preferred_index
        _preferred_index = 0


def _ordered_keys() -> list[str]:
    keys = gemini_keys()
    if not keys:
        raise RuntimeError("No GEMINI_API_KEY configured")
    with _lock:
        start = _preferred_index % len(keys)
        preferred = keys[start:] + keys[:start]
        live = [k for k in preferred if k not in _exhausted]
        # If every key is marked exhausted, try all again (quota may have reset)
        return live or preferred


def _promote(api_key: str) -> None:
    keys = gemini_keys()
    try:
        idx = keys.index(api_key)
    except ValueError:
        return
    with _lock:
        global _preferred_index
        _preferred_index = idx


def run_with_key_failover(operation: Callable[[genai.Client], T]) -> T:
    """Run ``operation(client)``, switching keys on free-tier quota errors."""
    last_quota: BaseException | None = None
    tried: set[str] = set()

    for api_key in _ordered_keys():
        if api_key in tried:
            continue
        tried.add(api_key)
        client = _client_for(api_key)
        try:
            result = operation(client)
            _promote(api_key)
            return result
        except Exception as exc:
            if is_quota_error(exc):
                mark_exhausted(api_key)
                last_quota = exc
                logger.info(
                    "Gemini quota error on …%s; trying next key",
                    api_key[-4:] if len(api_key) >= 4 else "????",
                )
                continue
            raise

    if last_quota is not None:
        raise last_quota
    raise RuntimeError("No Gemini API keys available")


def get_client() -> genai.Client:
    """Return current preferred Gemini client (no failover by itself)."""
    keys = _ordered_keys()
    return _client_for(keys[0])
