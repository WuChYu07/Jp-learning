import { useEffect, useState } from "react";
import SpeakButton from "../components/SpeakButton";
import { api, formatUserFacingError } from "../lib/api";
import { getPreferredVoice, setPreferredVoice } from "../lib/ttsPrefs";

const SAMPLE_TEXT = "週末は友達と映画を見に行くつもりです。";
const DEFAULT_VOICE = "Kore";

export default function SettingsPage() {
  const [voices, setVoices] = useState<{ name: string; style: string }[]>([]);
  const [selected, setSelected] = useState(() => getPreferredVoice() ?? DEFAULT_VOICE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listVoices()
      .then((res) => setVoices(res.voices))
      .catch((err: unknown) => setError(formatUserFacingError(err)))
      .finally(() => setLoading(false));
  }, []);

  function choose(name: string) {
    setPreferredVoice(name);
    setSelected(name);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold">設定</h1>
        <p className="mt-1 text-sm text-stone-500">個人化你的學習體驗</p>
      </div>

      <section className="space-y-3 rounded-2xl bg-white p-5 ring-1 ring-orange-100">
        <div>
          <h2 className="text-lg font-bold text-[var(--color-primary-dark)]">發音語音</h2>
          <p className="mt-1 text-sm text-stone-500">
            試聽下面幾種 Gemini 語音，選一個你喜歡的——全站的發音按鈕都會改用這個聲音。
          </p>
        </div>

        {loading && <p className="text-sm text-stone-400">載入中...</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}

        {!loading && !error && (
          <ul className="divide-y divide-stone-100">
            {voices.map((voice) => {
              const isSelected = voice.name === selected;
              return (
                <li
                  key={voice.name}
                  className={`flex flex-wrap items-center justify-between gap-3 py-3 ${
                    isSelected ? "rounded-xl bg-orange-50 px-3" : "px-3"
                  }`}
                >
                  <div className="min-w-0">
                    <p className="font-semibold text-stone-800">
                      {voice.name}
                      {isSelected && (
                        <span className="ml-2 rounded-full bg-[var(--color-primary)] px-2 py-0.5 text-xs font-semibold text-white">
                          使用中
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-stone-500">{voice.style}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <SpeakButton
                      text={SAMPLE_TEXT}
                      voiceOverride={voice.name}
                      size="sm"
                      caption="試聽"
                      label={`試聽 ${voice.name} 語音`}
                    />
                    <button
                      type="button"
                      disabled={isSelected}
                      onClick={() => choose(voice.name)}
                      className="rounded-full bg-[var(--color-primary)] px-3 py-1.5 text-xs font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {isSelected ? "已選用" : "選用"}
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
