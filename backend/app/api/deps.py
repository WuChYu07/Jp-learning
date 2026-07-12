from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.security import verify_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_effective_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str | None:
    """Return user id from JWT, or None when auth is disabled (single-user mode)."""
    if not settings.AUTH_ENABLED:
        return settings.DEV_USER_ID or None

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    payload = verify_access_token(credentials.credentials)
    return str(payload["sub"])


async def get_current_user_id(
    user_id: Annotated[str | None, Depends(get_effective_user_id)],
) -> str:
    """Require a user id — used when multi-user auth is enabled."""
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user_id


async def get_optional_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str | None:
    if not settings.AUTH_ENABLED:
        return settings.DEV_USER_ID or None
    if credentials is None:
        return None
    try:
        payload = verify_access_token(credentials.credentials)
        return str(payload["sub"])
    except HTTPException:
        return None
