from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve backend/.env regardless of the shell's current working directory.
# On Railway/Render there is usually no .env file — env vars come from the platform.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE if ENV_FILE.is_file() else None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_NAME: str = "Komorebi Japanese API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Supabase
    SUPABASE_URL: str
    # Publishable key (sb_publishable_...) — replaces legacy anon key
    SUPABASE_ANON_KEY: str

    # Secret key (sb_secret_...) — replaces legacy service_role key; backend only
    SUPABASE_SERVICE_ROLE_KEY: str

    # Gemini
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIM: int = 768
    # Grammar-note embeddings cluster tightly; keep threshold high.
    EMBEDDING_SIMILARITY_THRESHOLD: float = 0.90
    EMBEDDING_MATCH_TOP_K: int = 5
    # Only keep neighbors within this gap of the best match (filters soft clusters).
    EMBEDDING_MAX_SCORE_GAP: float = 0.025

    # Rate limiting
    DAILY_AI_REQUEST_LIMIT: int = 50

    # SRS
    SRS_DEFAULT_EASINESS_FACTOR: float = 2.5
    SRS_DEFAULT_INTERVAL_DAYS: int = 1

    # Auth — set false for single-user / local dev (no JWT required)
    AUTH_ENABLED: bool = False
    # Optional override; when empty and AUTH_ENABLED=false, uses SINGLETON_OWNER_ID
    DEV_USER_ID: str = ""
    # Fixed solo-owner UUID (created by migration 012 / ensure_owner_user)
    SINGLETON_OWNER_ID: str = "a0000000-0000-4000-8000-000000000001"

    # TLS — set false only for local dev if Windows SSL chain fails
    SSL_VERIFY: bool = True

    # Notion (optional — used by sync / probe scripts)
    NOTION_TOKEN: str = ""
    # Legacy fallback if only one page is configured
    NOTION_PAGE_ID: str = ""
    NOTION_VOCAB_PAGE_ID: str = ""
    NOTION_GRAMMAR_PAGE_ID: str = ""
    NOTION_AUTO_APPROVE: bool = False
    NOTION_STORAGE_BUCKET: str = "notion-images"

    @field_validator("SUPABASE_URL")
    @classmethod
    def normalize_supabase_url(cls, value: str) -> str:
        return value.rstrip("/").removesuffix("/rest/v1")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
