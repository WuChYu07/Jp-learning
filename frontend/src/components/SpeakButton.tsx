import { useEffect, useState, type MouseEvent, type PointerEvent } from "react";

type SpeakButtonProps = {
  text: string;
  label?: string;
  className?: string;
};

function normalizeJapanese(text: string): string {
  return text.replace(/[〜～~]/g, "").replace(/[（）()]/g, " ").trim();
}

export default function SpeakButton({
  text,
  label = "播放發音",
  className = "",
}: SpeakButtonProps) {
  const [supported, setSupported] = useState(false);
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => {
    setSupported("speechSynthesis" in window && "SpeechSynthesisUtterance" in window);
    return () => {
      window.speechSynthesis?.cancel();
    };
  }, []);

  function stopPointer(event: PointerEvent<HTMLButtonElement>) {
    event.stopPropagation();
  }

  function handleSpeak(event: MouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    if (!supported) return;

    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(normalizeJapanese(text));
    utterance.lang = "ja-JP";
    utterance.rate = 0.85;
    const japaneseVoice = window.speechSynthesis
      .getVoices()
      .find((voice) => voice.lang.toLowerCase().startsWith("ja"));
    if (japaneseVoice) utterance.voice = japaneseVoice;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    window.speechSynthesis.cancel();
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }

  return (
    <button
      type="button"
      disabled={!supported || !normalizeJapanese(text)}
      onPointerDown={stopPointer}
      onClick={handleSpeak}
      aria-label={speaking ? "停止發音" : label}
      title={supported ? (speaking ? "停止發音" : label) : "此瀏覽器不支援語音朗讀"}
      className={`inline-flex items-center justify-center rounded-full bg-sky-50 px-3 py-2 text-sm font-semibold text-sky-700 ring-1 ring-sky-200 transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-40 ${className}`}
    >
      <span aria-hidden>{speaking ? "■" : "🔊"}</span>
      <span className="ml-1.5">{speaking ? "停止" : "發音"}</span>
    </button>
  );
}
