"""Text-to-speech: synthesize (or reuse cached) audio for Japanese text."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.tts_service import AVAILABLE_VOICES, get_or_create_speech_url

router = APIRouter()


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    voice: str | None = None


class SpeechResponse(BaseModel):
    url: str


class VoiceOption(BaseModel):
    name: str
    style: str


class VoicesResponse(BaseModel):
    voices: list[VoiceOption]


@router.post("", response_model=SpeechResponse)
def synthesize_speech(body: SpeechRequest) -> SpeechResponse:
    return SpeechResponse(url=get_or_create_speech_url(body.text, body.voice))


@router.get("/voices", response_model=VoicesResponse)
def list_voices() -> VoicesResponse:
    return VoicesResponse(voices=[VoiceOption(name=name, style=style) for name, style in AVAILABLE_VOICES])
