import certifi
import httpx

from app.core.config import settings


def ssl_verify_setting() -> bool | str:
    """Return httpx/google-genai verify value. certifi path or False in broken local SSL."""
    if not settings.SSL_VERIFY and settings.APP_ENV == "development":
        return False
    return certifi.where()


def create_sync_client(**kwargs: object) -> httpx.Client:
    kwargs.setdefault("verify", ssl_verify_setting())
    return httpx.Client(**kwargs)
