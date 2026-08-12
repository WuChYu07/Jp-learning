const TTS_VOICE_PREF_KEY = "komorebi-tts-voice";

export function getPreferredVoice(): string | undefined {
  return localStorage.getItem(TTS_VOICE_PREF_KEY) || undefined;
}

export function setPreferredVoice(voice: string): void {
  localStorage.setItem(TTS_VOICE_PREF_KEY, voice);
}
