"""Song lyrics learning services (MARUMARU + AI enrichment)."""

from app.services.songs.enrichment_service import song_enrichment_service
from app.services.songs.song_service import song_service

__all__ = ["song_service", "song_enrichment_service"]
