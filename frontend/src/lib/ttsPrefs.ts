const TTS_VOICE_PREF_KEY = "komorebi-tts-voice";

/** Sentinel meaning "skip Gemini, use the browser/OS's built-in speechSynthesis voice". */
export const BROWSER_VOICE_OPTION = "__browser__";

export function getPreferredVoice(): string | undefined {
  return localStorage.getItem(TTS_VOICE_PREF_KEY) || undefined;
}

export function setPreferredVoice(voice: string): void {
  localStorage.setItem(TTS_VOICE_PREF_KEY, voice);
}
