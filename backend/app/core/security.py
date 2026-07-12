from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.http_client import create_sync_client


def verify_access_token(token: str) -> dict[str, Any]:
    """Validate a Supabase user access token via the Auth API.

    Works with the new publishable/secret API keys — no local JWT secret needed.
  See: https://supabase.com/docs/guides/auth/jwts
    """
    url = f"{settings.SUPABASE_URL}/auth/v1/user"
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {token}",
    }

    try:
        with create_sync_client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase Auth service unavailable",
        ) from exc

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = response.json()
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user id",
        )

    return {"sub": user_id, "email": user.get("email"), "user": user}
