"""Single shared-credential gate for the whole API — independent of AUTH_ENABLED
/ Supabase Auth (see app/api/deps.py). This isn't per-user identity, just a lock
on the front door so a stranger who finds the URL can't read or write data."""

from __future__ import annotations

import time

import bcrypt
import jwt

from app.core.config import settings

TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days


def verify_password(password: str) -> bool:
    if not settings.ADMIN_PASSWORD_HASH:
        # Fail closed: an unconfigured gate rejects everyone rather than admitting everyone.
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), settings.ADMIN_PASSWORD_HASH.encode("utf-8"))
    except ValueError:
        # Malformed hash in the env var — treat as misconfigured, not a crash.
        return False


def issue_token() -> str:
    now = int(time.time())
    payload = {"site": "komorebi", "iat": now, "exp": now + TOKEN_TTL_SECONDS}
    return jwt.encode(payload, settings.SITE_AUTH_SECRET, algorithm="HS256")


def verify_token(token: str) -> bool:
    if not settings.SITE_AUTH_SECRET:
        return False
    try:
        jwt.decode(token, settings.SITE_AUTH_SECRET, algorithms=["HS256"])
        return True
    except jwt.PyJWTError:
        return False
