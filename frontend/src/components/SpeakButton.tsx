import { useEffect, useRef, useState, type MouseEvent, type PointerEvent } from "react";
import { api } from "../lib/api";
import { BROWSER_VOICE_OPTION, getPreferredVoice } from "../lib/ttsPrefs";

type SpeakButtonProps = {
  text: string;
  label?: string;
  className?: string;
  /** Larger control for flashcard fronts. */
  size?: "sm" | "md" | "lg";
  /** Shown next to the icon (default 發音 / 播例句). */
  caption?: string;
  /** Force a specific Gemini voice, ignoring the saved preference (voice audition UI). */
  voiceOverride?: string;
};

function normalizeJapanese(text: string): string {
  return text.replace(/[〜～~]/g, "").replace(/[（）()]/g, " ").trim();
}

/** Browsers often list a robotic local voice before better cloud/neural ones
 * (e.g. Chrome's "Google 日本語", Edge's "Microsoft ... Online (Natural)").
 * Prefer those explicitly instead of just taking the first ja-* match.
 * Used only as a fallback when the Gemini-voiced backend clip fails to load. */
function pickBestJapaneseVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | undefined {
  const jaVoices = voices.filter((voice) => voice.lang.toLowerCase().startsWith("ja"));
  const byPreference = [
    (v: SpeechSynthesisVoice) => /google/i.test(v.name),
    (v: SpeechSynthesisVoice) => /natural|neural|online/i.test(v.name),
    (v: SpeechSynthesisVoice) => !v.localService,
  ];
  for (const prefers of byPreference) {
    const match = jaVoices.find(prefers);
    if (match) return match;
  }
  return jaVoices[0];
}

/** Session-local cache of "voice::text" → Gemini audio URL, so repeat clicks in
 * the same visit skip the network round trip (the backend already caches by
 * content hash, this just avoids re-asking it). */
const speechUrlCache = new Map<string, string>();

/** Ensures only one SpeakButton is ever audible at a time, app-wide. */
let stopCurrent: (() => void) | null = null;

const SIZE_CLASS = {
  sm: "px-2.5 py-1.5 text-xs",
  md: "px-3 py-2 text-sm",
  lg: "px-5 py-3 text-base shadow-sm",
} as const;

type PlayState = "idle" | "loading" | "playing";

export default function SpeakButton({
  text,
  label = "播放發音",
  className = "",
  size = "md",
  caption,
  voiceOverride,
}: SpeakButtonProps) {
  const [state, setState] = useState<PlayState>("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      audioRef.current?.pause();
      window.speechSynthesis?.cancel();
      if (stopCurrent === stop) stopCurrent = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function stop() {
    abortRef.current?.abort();
    audioRef.current?.pause();
    window.speechSynthesis?.cancel();
    setState("idle");
  }

  function speakWithBrowserTts(normalized: string) {
    if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
      setState("idle");
      return;
    }
    const utterance = new SpeechSynthesisUtterance(normalized);
    utterance.lang = "ja-JP";
    utterance.rate = 0.85;
    const japaneseVoice = pickBestJapaneseVoice(window.speechSynthesis.getVoices());
    if (japaneseVoice) utterance.voice = japaneseVoice;
    utterance.onend = () => setState("idle");
    utterance.onerror = () => setState("idle");
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    setState("playing");
  }

  async function handleSpeak(event: MouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    const normalized = normalizeJapanese(text);
    if (!normalized) return;

    if (state !== "idle") {
      stop();
      return;
    }

    stopCurrent?.();
    stopCurrent = stop;

    const voice = voiceOverride ?? getPreferredVoice();
    if (voice === BROWSER_VOICE_OPTION) {
      speakWithBrowserTts(normalized);
      return;
    }

    setState("loading");
    const cacheKey = `${voice ?? "default"}::${normalized}`;
    const cached = speechUrlCache.get(cacheKey);
    if (cached) {
      playUrl(cached);
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const { url } = await api.getSpeechUrl(normalized, voice);
      if (controller.signal.aborted) return;
      speechUrlCache.set(cacheKey, url);
      playUrl(url);
    } catch {
      if (controller.signal.aborted) return;
      speakWithBrowserTts(normalized);
    }
  }

  function playUrl(url: string) {
    const audio = new Audio(url);
    audioRef.current = audio;
    audio.onended = () => setState("idle");
    audio.onerror = () => speakWithBrowserTts(normalizeJapanese(text));
    audio.play().catch(() => speakWithBrowserTts(normalizeJapanese(text)));
    setState("playing");
  }

  const displayCaption =
    caption ?? (state === "loading" ? "生成中" : state === "playing" ? "停止" : "發音");

  return (
    <button
      type="button"
      disabled={!normalizeJapanese(text)}
      onPointerDown={(event: PointerEvent<HTMLButtonElement>) => event.stopPropagation()}
      onClick={handleSpeak}
      aria-label={state === "playing" ? "停止發音" : label}
      title={label}
      className={`inline-flex items-center justify-center rounded-full bg-sky-50 font-semibold text-sky-800 ring-1 ring-sky-200 transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-40 ${SIZE_CLASS[size]} ${className}`}
    >
      <span aria-hidden className={size === "lg" ? "text-lg" : ""}>
        {state === "loading" ? "…" : state === "playing" ? "■" : "🔊"}
      </span>
      <span className="ml-1.5">{displayCaption}</span>
    </button>
  );
}
