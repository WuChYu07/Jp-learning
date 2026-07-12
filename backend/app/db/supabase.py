from functools import lru_cache

import httpx
from supabase import Client, ClientOptions, create_client

from app.core.config import settings
from app.core.http_client import create_sync_client


@lru_cache
def get_supabase_client() -> Client:
    """Service-role client for privileged backend operations."""
    httpx_client = create_sync_client()
    options = ClientOptions(httpx_client=httpx_client)
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
        options=options,
    )


def get_supabase_client_for_user(access_token: str) -> Client:
    """Anon client scoped to a user's JWT (respects RLS)."""
    httpx_client = create_sync_client()
    options = ClientOptions(httpx_client=httpx_client)
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY, options=options)
    client.postgrest.auth(access_token)
    return client
