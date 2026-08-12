"""Text-to-speech via Gemini's native audio output, cached in Supabase Storage
keyed by content hash so the same sentence is only ever synthesized once."""

from __future__ import annotations

import hashlib
import io
import logging
import wave

from fastapi import HTTPException, status
from google.genai import types

from app.core.config import settings
from app.db.supabase import get_supabase_client
from app.services.gemini_client import run_with_key_failover

logger = logging.getLogger(__name__)

_DEFAULT_SAMPLE_RATE = 24000
_bucket_ready = False

# Gemini's prebuilt TTS voices worth surfacing for audition (name, style hint).
# Full catalog has ~30 voices; this is a curated subset with well-documented styles.
AVAILABLE_VOICES: list[tuple[str, str]] = [
    ("Kore", "沉穩堅定"),
    ("Puck", "輕快活潑"),
    ("Zephyr", "明亮清爽"),
    ("Charon", "沉穩講解"),
    ("Fenrir", "激動有力"),
    ("Leda", "年輕活力"),
    ("Orus", "堅定有力"),
    ("Aoede", "輕鬆自然"),
    ("Callirrhoe", "從容悠閒"),
    ("Autonoe", "明亮開朗"),
    ("Achernar", "柔和輕聲"),
    ("Sulafat", "溫暖親切"),
]


def _cache_filename(text: str, voice: str) -> str:
    digest = hashlib.sha256(f"{voice}::{text}".encode("utf-8")).hexdigest()
    return f"{digest}.wav"


def _sample_rate_from_mime(mime_type: str) -> int:
    for part in mime_type.split(";"):
        part = part.strip()
        if part.startswith("rate="):
            try:
                return int(part.removeprefix("rate="))
            except ValueError:
                pass
    return _DEFAULT_SAMPLE_RATE


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    """Gemini TTS returns raw 16-bit PCM; wrap it in a WAV header for <audio> playback."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()


def _ensure_bucket(bucket: str) -> None:
    global _bucket_ready
    if _bucket_ready:
        return
    client = get_supabase_client()
    try:
        client.storage.get_bucket(bucket)
    except Exception:
        try:
            client.storage.create_bucket(bucket, options={"public": True})
        except Exception as exc:
            logger.warning("Could not auto-create TTS bucket '%s': %s", bucket, exc)
    _bucket_ready = True


def _existing_url(bucket: str, filename: str) -> str | None:
    client = get_supabase_client()
    try:
        entries = client.storage.from_(bucket).list(options={"search": filename, "limit": 1})
    except Exception as exc:
        logger.warning("TTS cache lookup failed for '%s': %s", filename, exc)
        return None
    if any(entry.get("name") == filename for entry in entries):
        return client.storage.from_(bucket).get_public_url(filename)
    return None


def _synthesize_wav(text: str, voice: str) -> bytes:
    # Short/ambiguous input (a single greeting, a bare word) can make the model
    # reply conversationally instead of just reading it aloud; an explicit
    # instruction forces literal TTS regardless of input length.
    prompt = f"Say clearly and naturally, without adding any extra words: {text}"

    def call(client):
        return client.models.generate_content(
            model=settings.GEMINI_TTS_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice,
                        )
                    )
                ),
            ),
        )

    response = run_with_key_failover(call)
    candidates = response.candidates or []
    parts = candidates[0].content.parts if candidates and candidates[0].content else None
    inline = parts[0].inline_data if parts else None
    if inline is None or not inline.data:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Gemini TTS returned no audio")

    sample_rate = _sample_rate_from_mime(inline.mime_type or "")
    return _pcm_to_wav(inline.data, sample_rate)


def get_or_create_speech_url(text: str, voice: str | None = None) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="text is required")
    voice = (voice or settings.GEMINI_TTS_VOICE).strip() or settings.GEMINI_TTS_VOICE

    bucket = settings.TTS_STORAGE_BUCKET
    _ensure_bucket(bucket)
    filename = _cache_filename(cleaned, voice)

    cached = _existing_url(bucket, filename)
    if cached:
        return cached

    wav_bytes = _synthesize_wav(cleaned, voice)

    client = get_supabase_client()
    try:
        client.storage.from_(bucket).upload(
            filename,
            wav_bytes,
            file_options={"content-type": "audio/wav", "upsert": "true"},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase Storage upload failed: {exc}. Ensure bucket '{bucket}' exists and is public.",
        ) from exc

    return client.storage.from_(bucket).get_public_url(filename)
