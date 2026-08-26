import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import SpeakButton from "../components/SpeakButton";
import {
  api,
  PracticeDialogue,
  PracticeGradeResult,
  PracticeHint,
  PracticePrompt,
  formatUserFacingError,
} from "../lib/api";

type PracticeMode = "speak" | "hint_translate";
type PracticeTopic = "daily" | "academic" | "travel" | "work" | "random";

type PracticeNavState = {
  mode?: PracticeMode;
  grammarId?: string;
  grammarPoint?: string;
  vocabId?: string;
  vocabWord?: string;
};

const TOPICS: { id: PracticeTopic; label: string }[] = [
  { id: "random", label: "隨機" },
  { id: "daily", label: "日常" },
  { id: "travel", label: "旅行" },
  { id: "work", label: "工作" },
  { id: "academic", label: "學術" },
];

export default function PracticePage() {
  const location = useLocation();
  const navState = location.state as PracticeNavState | null;
  const [mode, setMode] = useState<PracticeMode>(navState?.mode ?? "speak");
  const [topic, setTopic] = useState<PracticeTopic>("random");
  const [forcedGrammarId, setForcedGrammarId] = useState<string | undefined>(
    navState?.grammarId,
  );
  const [forcedGrammarPoint, setForcedGrammarPoint] = useState<string | undefined>(
    navState?.grammarPoint,
  );
  const [forcedVocabId, setForcedVocabId] = useState<string | undefined>(
    navState?.vocabId,
  );
  const [forcedVocabWord, setForcedVocabWord] = useState<string | undefined>(
    navState?.vocabWord,
  );
  const [prompt, setPrompt] = useState<PracticePrompt | null>(null);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [grading, setGrading] = useState(false);
  const [result, setResult] = useState<PracticeGradeResult | null>(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<PracticeDialogue[]>([]);
  const [addingExample, setAddingExample] = useState(false);
  const [exampleAdded, setExampleAdded] = useState(false);
  const [addExampleError, setAddExampleError] = useState("");

  const loadHistory = useCallback(() => {
    api
      .practiceHistory(15)
      .then(setHistory)
      .catch(() => setHistory([]));
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Deep-linked from a grammar's detail page: jump straight into an exercise.
  // Guarded with a ref (not just `loading`) so React StrictMode's dev-only
  // double-invoke of mount effects can't fire this twice and burn extra quota.
  const autoStartedRef = useRef(false);
  useEffect(() => {
    if ((navState?.grammarId || navState?.vocabId) && !autoStartedRef.current) {
      autoStartedRef.current = true;
      void startSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function startSession() {
    if (loading) return;
    setLoading(true);
    setError("");
    setResult(null);
    setAnswer("");
    setPrompt(null);
    setExampleAdded(false);
    setAddExampleError("");
    try {
      const p = await api.practiceSession(mode, topic, forcedGrammarId, forcedVocabId);
      setPrompt(p);
    } catch (e) {
      setError(formatUserFacingError(e));
    } finally {
      setLoading(false);
    }
  }

  function clearForcedTarget() {
    setForcedGrammarId(undefined);
    setForcedGrammarPoint(undefined);
    setForcedVocabId(undefined);
    setForcedVocabWord(undefined);
  }

  async function addExampleToLibrary() {
    if (!result?.model_answer || addingExample) return;
    setAddingExample(true);
    setAddExampleError("");
    try {
      if (forcedGrammarId) {
        await api.addGrammarExampleFromPractice(
          forcedGrammarId,
          result.model_answer,
          prompt?.prompt_zh,
        );
      } else if (forcedVocabId) {
        await api.addVocabExampleFromPractice(
          forcedVocabId,
          result.model_answer,
          prompt?.prompt_zh,
        );
      } else {
        return;
      }
      setExampleAdded(true);
    } catch (e) {
      setAddExampleError(formatUserFacingError(e));
    } finally {
      setAddingExample(false);
    }
  }

  async function submitGrade() {
    if (!prompt || !answer.trim() || grading) return;
    setGrading(true);
    setError("");
    try {
      const res = await api.practiceGrade({
        mode: prompt.mode,
        topic: prompt.topic,
        prompt_zh: prompt.prompt_zh,
        prompt_ja: prompt.prompt_ja,
        user_answer: answer.trim(),
        hints: prompt.hints,
      });
      setResult(res);
      loadHistory();
    } catch (e) {
      setError(formatUserFacingError(e));
    } finally {
      setGrading(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold">
          AI 練習
        </h1>
        <p className="mt-1 text-sm text-stone-600">
          日文問答評分，或中文翻譯（附文法／單字提示）。會消耗 Gemini 額度。
        </p>
      </div>

      <div className="flex flex-wrap rounded-full bg-stone-100 p-1">
        <ModeTab active={mode === "speak"} onClick={() => setMode("speak")}>
          日文問答
        </ModeTab>
        <ModeTab
          active={mode === "hint_translate"}
          onClick={() => setMode("hint_translate")}
        >
          帶提示翻譯
        </ModeTab>
      </div>

      {(forcedGrammarId || forcedVocabId) && (
        <div className="flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-800 ring-1 ring-emerald-200">
          <span>
            已指定{forcedGrammarId ? "文法" : "單字"}：
            {forcedGrammarId
              ? (forcedGrammarPoint ?? forcedGrammarId)
              : (forcedVocabWord ?? forcedVocabId)}
          </span>
          <button
            type="button"
            onClick={clearForcedTarget}
            aria-label="取消指定"
            className="text-emerald-600 hover:text-emerald-900"
          >
            ✕
          </button>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {TOPICS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTopic(t.id)}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
              topic === t.id
                ? "bg-[var(--color-primary)] text-white"
                : "bg-white text-stone-600 ring-1 ring-stone-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {!prompt && (
        <button
          type="button"
          onClick={() => void startSession()}
          disabled={loading}
          className="w-full rounded-full bg-[var(--color-primary)] py-3 text-sm font-semibold text-white shadow-md disabled:opacity-50"
        >
          {loading ? "出題中…" : "開始一題"}
        </button>
      )}

      {error && (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      )}

      {(prompt?.daily_ai_limit_reached || result?.daily_ai_limit_reached) && (
        <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
          今日 AI 練習次數已偏高，額度明天會重置，目前仍可繼續使用。
        </p>
      )}

      {prompt && (
        <div className="space-y-4 rounded-3xl bg-white p-6 shadow-lg ring-1 ring-orange-100">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="rounded-full bg-violet-50 px-3 py-0.5 text-xs font-semibold text-violet-700">
              {prompt.mode === "speak" ? "日文問答" : "帶提示翻譯"} · {prompt.topic}
            </span>
            {prompt.prompt_ja && (
              <SpeakButton size="sm" text={prompt.prompt_ja} label="播放問題" caption="發音" />
            )}
          </div>

          {prompt.mode === "speak" ? (
            <>
              <p className="text-xl font-medium text-[var(--color-ink)]">
                {prompt.prompt_ja}
              </p>
              {prompt.prompt_zh && (
                <p className="text-sm text-stone-500">{prompt.prompt_zh}</p>
              )}
              <p className="text-xs text-stone-400">請用日文回答</p>
            </>
          ) : (
            <>
              <p className="text-lg font-medium text-[var(--color-ink)]">
                {prompt.prompt_zh}
              </p>
              <p className="text-xs text-stone-400">請譯成日文（可參考下方提示）</p>
              {prompt.hints.length > 0 && (
                <ul className="space-y-2">
                  {prompt.hints.map((h, i) => (
                    <HintChip key={`${h.label}-${i}`} hint={h} />
                  ))}
                </ul>
              )}
            </>
          )}

          {!result && (
            <>
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                rows={4}
                placeholder="在這裡輸入日文答案…"
                className="w-full rounded-2xl border-2 border-stone-200 bg-stone-50 p-4 text-sm outline-none focus:border-[var(--color-primary)]"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => void submitGrade()}
                  disabled={grading || !answer.trim()}
                  className="flex-1 rounded-full bg-emerald-600 py-3 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {grading ? "評分中…" : "送出評分"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setPrompt(null);
                    setAnswer("");
                    setResult(null);
                  }}
                  className="rounded-full bg-stone-100 px-5 py-3 text-sm font-semibold text-stone-700"
                >
                  取消
                </button>
              </div>
            </>
          )}

          {result && (
            <div className="space-y-3 rounded-2xl bg-emerald-50 p-4 ring-1 ring-emerald-100">
              <p className="text-2xl font-bold text-emerald-800">{result.score} / 5</p>
              <p className="text-sm text-emerald-900">{result.feedback_zh}</p>
              {result.model_answer && (
                <div>
                  <p className="text-xs font-semibold text-emerald-700">參考答案</p>
                  <div className="mt-1 flex flex-wrap items-start gap-2">
                    <p className="flex-1 text-sm text-stone-800">{result.model_answer}</p>
                    <SpeakButton
                      size="sm"
                      text={result.model_answer}
                      label="播放參考答案"
                      caption="發音"
                    />
                  </div>
                </div>
              )}
              {(forcedGrammarId || forcedVocabId) && result.model_answer && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void addExampleToLibrary()}
                    disabled={addingExample || exampleAdded}
                    className="rounded-full bg-teal-600 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
                  >
                    {exampleAdded
                      ? "已加入例句 ✓"
                      : addingExample
                        ? "加入中…"
                        : `加入「${forcedGrammarId ? (forcedGrammarPoint ?? "此文法") : (forcedVocabWord ?? "此單字")}」例句`}
                  </button>
                  {addExampleError && (
                    <span className="text-xs text-red-600">{addExampleError}</span>
                  )}
                </div>
              )}
              <button
                type="button"
                onClick={() => void startSession()}
                disabled={loading}
                className="w-full rounded-full bg-[var(--color-primary)] py-2.5 text-sm font-semibold text-white"
              >
                再來一題
              </button>
            </div>
          )}
        </div>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-stone-700">最近紀錄</h2>
        {history.length === 0 ? (
          <p className="text-sm text-stone-400">尚無紀錄。完成一題後會顯示在這裡。</p>
        ) : (
          <ul className="space-y-2">
            {history.map((row) => (
              <li
                key={row.id}
                className="rounded-2xl bg-white px-4 py-3 text-sm ring-1 ring-stone-100"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-stone-500">
                    {row.mode === "speak" ? "問答" : "翻譯"}
                    {row.topic ? ` · ${row.topic}` : ""}
                  </span>
                  {row.score != null && (
                    <span className="text-xs font-bold text-emerald-700">
                      {row.score}/5
                    </span>
                  )}
                </div>
                <p className="mt-1 text-stone-800">
                  {row.prompt_zh || row.prompt_ja || "—"}
                </p>
                <p className="mt-1 text-stone-600">你：{row.user_answer}</p>
                {row.feedback_zh && (
                  <p className="mt-1 text-xs text-stone-500">{row.feedback_zh}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function ModeTab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 rounded-full px-4 py-2 text-sm font-semibold transition ${
        active
          ? "bg-white text-[var(--color-primary)] shadow-sm"
          : "text-stone-500 hover:text-stone-800"
      }`}
    >
      {children}
    </button>
  );
}

function HintChip({ hint }: { hint: PracticeHint }) {
  return (
    <li className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-950 ring-1 ring-amber-100">
      <span className="font-semibold">
        {hint.kind === "grammar" ? "文法" : "單字"}：{hint.label}
      </span>
      {hint.detail && <span className="mt-0.5 block text-amber-800">{hint.detail}</span>}
    </li>
  );
}
