import { useCallback, useEffect, useState } from "react";
import SpeakButton from "../components/SpeakButton";
import {
  api,
  ClozeQuestion,
  FourChoiceQuestion,
  TranslationGradeResult,
  TranslationPrompt,
} from "../lib/api";

type QuizMode = "4choice" | "grammar" | "cloze" | "translation";

export default function QuizPage() {
  const [mode, setMode] = useState<QuizMode>("4choice");
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold">
          測驗
        </h1>
        <div className="flex flex-wrap rounded-full bg-stone-100 p-1">
          <TabButton
            active={mode === "4choice"}
            onClick={() => setMode("4choice")}
          >
            單字四選一
          </TabButton>
          <TabButton
            active={mode === "grammar"}
            onClick={() => setMode("grammar")}
          >
            文法四選一
          </TabButton>
          <TabButton active={mode === "cloze"} onClick={() => setMode("cloze")}>
            例句挖空
          </TabButton>
          <TabButton
            active={mode === "translation"}
            onClick={() => setMode("translation")}
          >
            翻譯
          </TabButton>
        </div>
      </div>

      {mode === "4choice" && <FourChoiceQuiz />}
      {mode === "grammar" && <GrammarFourChoiceQuiz />}
      {mode === "cloze" && <ClozeQuiz />}
      {mode === "translation" && <TranslationQuiz />}
    </div>
  );
}

function TabButton({
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
      className={`rounded-full px-6 py-2 text-sm font-semibold transition ${
        active
          ? "bg-white text-[var(--color-primary)] shadow-sm"
          : "text-stone-500 hover:text-stone-800"
      }`}
    >
      {children}
    </button>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 4-Choice Quiz
// ═══════════════════════════════════════════════════════════════════════════

function FourChoiceQuiz() {
  return (
    <GenericFourChoiceQuiz
      title="單字四選一"
      subject="vocab"
      loadQuestions={() => api.quiz4Choice(10).then((r) => r.questions)}
      emptyText="資料庫單字不足，無法出題"
    />
  );
}

function GrammarFourChoiceQuiz() {
  return (
    <GenericFourChoiceQuiz
      title="文法四選一"
      subject="grammar"
      loadQuestions={() => api.quizGrammar4Choice(10).then((r) => r.questions)}
      emptyText="資料庫文法不足，無法出題"
    />
  );
}

function GenericFourChoiceQuiz({
  title,
  subject,
  loadQuestions,
  emptyText,
}: {
  title: string;
  subject: "vocab" | "grammar";
  loadQuestions: () => Promise<FourChoiceQuestion[]>;
  emptyText: string;
}) {
  const [questions, setQuestions] = useState<FourChoiceQuestion[]>([]);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [wrongIds, setWrongIds] = useState<string[]>([]);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    setIndex(0);
    setScore(0);
    setFinished(false);
    setSelected(null);
    setRevealed(false);
    setSaved(false);
    setWrongIds([]);
    loadQuestions()
      .then(setQuestions)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [loadQuestions]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!finished || saved || questions.length === 0) return;
    setSaved(true);
    void api
      .submitQuizResult({
        subject,
        mode: "4choice",
        correct_count: score,
        total_count: questions.length,
        detail: { wrong_ids: wrongIds },
      })
      .catch(() => {
        /* non-blocking */
      });
  }, [finished, saved, score, questions.length, subject, wrongIds]);

  if (loading) return <LoadingCard />;
  if (error) return <ErrorCard message={error} />;
  if (questions.length === 0) return <EmptyCard text={emptyText} />;

  if (finished) {
    const pct = Math.round((score / questions.length) * 100);
    return (
      <div className="batch-complete-enter mx-auto max-w-lg space-y-6">
        <div className="rounded-3xl bg-white p-8 text-center shadow-lg ring-1 ring-orange-100">
          <p className="text-4xl">{pct >= 80 ? "🎉" : pct >= 50 ? "💪" : "📖"}</p>
          <h2 className="mt-3 font-[family-name:var(--font-display)] text-2xl font-bold text-[var(--color-primary-dark)]">
            {title}完成！
          </h2>
          <div className="mt-6 grid grid-cols-2 gap-4">
            <div>
              <p className="text-3xl font-bold text-emerald-600">{score}</p>
              <p className="text-xs text-stone-500">答對</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-red-500">
                {questions.length - score}
              </p>
              <p className="text-xs text-stone-500">答錯</p>
            </div>
          </div>
          <div className="mx-auto mt-4 h-2 w-full max-w-xs overflow-hidden rounded-full bg-stone-100">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="mt-1 text-sm text-stone-500">正確率 {pct}%</p>
          {wrongIds.length > 0 && (
            <p className="mt-3 text-sm text-orange-700">
              {wrongIds.length} 題錯題已加入複習佇列
            </p>
          )}
        </div>
        <div className="flex justify-center">
          <button
            type="button"
            onClick={load}
            className="rounded-full bg-[var(--color-primary)] px-8 py-3 text-sm font-semibold text-white shadow-md transition hover:shadow-lg active:scale-95"
          >
            再測一次
          </button>
        </div>
      </div>
    );
  }

  const q = questions[index];
  const progress = ((index + 1) / questions.length) * 100;

  function handleSelect(optionId: string) {
    if (revealed) return;
    setSelected(optionId);
    setRevealed(true);
    if (optionId === q.correct_option_id) {
      setScore((s) => s + 1);
    } else {
      setWrongIds((ids) => (ids.includes(q.question_id) ? ids : [...ids, q.question_id]));
    }
  }

  function handleNext() {
    setSelected(null);
    setRevealed(false);
    if (index + 1 < questions.length) {
      setIndex(index + 1);
    } else {
      setFinished(true);
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      {/* Progress */}
      <div className="space-y-1">
        <div className="flex justify-between px-1 text-xs text-stone-500">
          <span>第 {index + 1} / {questions.length} 題</span>
          <span>{Math.round(progress)}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-stone-100">
          <div
            className="h-full rounded-full bg-gradient-to-r from-orange-300 to-[var(--color-primary)] transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Question card */}
      <div className="rounded-3xl bg-white p-8 text-center shadow-lg ring-1 ring-orange-100">
        <span className="inline-block rounded-full bg-orange-50 px-3 py-0.5 text-xs font-semibold text-orange-700">
          {q.mode === "reading"
            ? "讀音"
            : q.mode === "point"
              ? "文法"
              : "意思"}
        </span>
        <p className="kanji-display mt-6 text-6xl text-[var(--color-ink)]">
          {q.word}
        </p>
        <p className="mt-4 text-base text-stone-500">{q.prompt}</p>
      </div>

      {/* Options */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {q.options.map((opt) => {
          let ring = "ring-1 ring-orange-100 hover:ring-[var(--color-primary)]";
          if (revealed) {
            if (opt.id === q.correct_option_id) {
              ring = "ring-2 ring-emerald-500 bg-emerald-50";
            } else if (opt.id === selected) {
              ring = "ring-2 ring-red-400 bg-red-50";
            } else {
              ring = "ring-1 ring-stone-200 opacity-50";
            }
          }
          return (
            <button
              key={opt.id}
              type="button"
              onClick={() => handleSelect(opt.id)}
              disabled={revealed}
              className={`rounded-2xl bg-white p-5 text-center text-lg font-medium transition active:scale-[0.97] ${ring}`}
            >
              {opt.text}
            </button>
          );
        })}
      </div>

      {/* Revealed feedback + next */}
      {revealed && (
        <div className="flex flex-col items-center gap-3">
          <p
            className={`text-sm font-semibold ${
              selected === q.correct_option_id
                ? "text-emerald-600"
                : "text-red-500"
            }`}
          >
            {selected === q.correct_option_id ? "正確！" : "答錯了"}
          </p>
          <button
            type="button"
            onClick={handleNext}
            className="rounded-full bg-[var(--color-primary)] px-8 py-2.5 text-sm font-semibold text-white transition hover:shadow-md active:scale-95"
          >
            {index + 1 < questions.length ? "下一題" : "查看結果"}
          </button>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Cloze Quiz (blank target word/grammar in example sentences)
// ═══════════════════════════════════════════════════════════════════════════

function ClozeQuiz() {
  const [questions, setQuestions] = useState<ClozeQuestion[]>([]);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [wrongVocab, setWrongVocab] = useState<string[]>([]);
  const [wrongGrammar, setWrongGrammar] = useState<string[]>([]);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    setIndex(0);
    setScore(0);
    setFinished(false);
    setSelected(null);
    setRevealed(false);
    setSaved(false);
    setWrongVocab([]);
    setWrongGrammar([]);
    api
      .quizCloze(10, "both")
      .then((r) => setQuestions(r.questions))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!finished || saved || questions.length === 0) return;
    setSaved(true);
    const jobs: Promise<unknown>[] = [];
    if (wrongVocab.length > 0 || questions.some((q) => q.subject === "vocab")) {
      const vocabTotal = questions.filter((q) => q.subject === "vocab").length;
      const vocabCorrect = vocabTotal - wrongVocab.length;
      if (vocabTotal > 0) {
        jobs.push(
          api.submitQuizResult({
            subject: "vocab",
            mode: "cloze",
            correct_count: Math.max(0, vocabCorrect),
            total_count: vocabTotal,
            detail: { wrong_ids: wrongVocab },
          }),
        );
      }
    }
    if (
      wrongGrammar.length > 0 ||
      questions.some((q) => q.subject === "grammar")
    ) {
      const grammarTotal = questions.filter((q) => q.subject === "grammar").length;
      const grammarCorrect = grammarTotal - wrongGrammar.length;
      if (grammarTotal > 0) {
        jobs.push(
          api.submitQuizResult({
            subject: "grammar",
            mode: "cloze",
            correct_count: Math.max(0, grammarCorrect),
            total_count: grammarTotal,
            detail: { wrong_ids: wrongGrammar },
          }),
        );
      }
    }
    void Promise.all(jobs).catch(() => {
      /* non-blocking */
    });
  }, [finished, saved, questions, wrongVocab, wrongGrammar]);

  if (loading) return <LoadingCard />;
  if (error) return <ErrorCard message={error} />;
  if (questions.length === 0) {
    return <EmptyCard text="資料庫中沒有足夠帶例句的單字／文法可出挖空題" />;
  }

  if (finished) {
    const pct = Math.round((score / questions.length) * 100);
    const wrongCount = wrongVocab.length + wrongGrammar.length;
    return (
      <div className="batch-complete-enter mx-auto max-w-lg space-y-6">
        <div className="rounded-3xl bg-white p-8 text-center shadow-lg ring-1 ring-orange-100">
          <p className="text-4xl">{pct >= 80 ? "🎉" : pct >= 50 ? "💪" : "📖"}</p>
          <h2 className="mt-3 font-[family-name:var(--font-display)] text-2xl font-bold text-[var(--color-primary-dark)]">
            例句挖空完成！
          </h2>
          <div className="mt-6 grid grid-cols-2 gap-4">
            <div>
              <p className="text-3xl font-bold text-emerald-600">{score}</p>
              <p className="text-xs text-stone-500">答對</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-red-500">
                {questions.length - score}
              </p>
              <p className="text-xs text-stone-500">答錯</p>
            </div>
          </div>
          <p className="mt-3 text-sm text-stone-500">正確率 {pct}%</p>
          {wrongCount > 0 && (
            <p className="mt-3 text-sm text-orange-700">
              {wrongCount} 題錯題已加入複習佇列
            </p>
          )}
        </div>
        <div className="flex justify-center">
          <button
            type="button"
            onClick={load}
            className="rounded-full bg-[var(--color-primary)] px-8 py-3 text-sm font-semibold text-white shadow-md"
          >
            再測一次
          </button>
        </div>
      </div>
    );
  }

  const q = questions[index];
  const progress = ((index + 1) / questions.length) * 100;

  function handleSelect(optionId: string) {
    if (revealed) return;
    setSelected(optionId);
    setRevealed(true);
    if (optionId === q.correct_option_id) {
      setScore((s) => s + 1);
    } else if (q.subject === "grammar") {
      setWrongGrammar((ids) =>
        ids.includes(q.entity_id) ? ids : [...ids, q.entity_id],
      );
    } else {
      setWrongVocab((ids) =>
        ids.includes(q.entity_id) ? ids : [...ids, q.entity_id],
      );
    }
  }

  function handleNext() {
    setSelected(null);
    setRevealed(false);
    if (index + 1 < questions.length) setIndex(index + 1);
    else setFinished(true);
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div className="space-y-1">
        <div className="flex justify-between px-1 text-xs text-stone-500">
          <span>
            第 {index + 1} / {questions.length} 題
          </span>
          <span>{Math.round(progress)}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-stone-100">
          <div
            className="h-full rounded-full bg-gradient-to-r from-orange-300 to-[var(--color-primary)] transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="rounded-3xl bg-white p-8 shadow-lg ring-1 ring-orange-100">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="inline-block rounded-full bg-violet-50 px-3 py-0.5 text-xs font-semibold text-violet-700">
            {q.subject === "grammar" ? "文法挖空" : "單字挖空"}
          </span>
          <SpeakButton
            size="sm"
            text={revealed ? q.sentence_full : q.sentence_blanked.replace(/____/g, "なに")}
            label="播放句子"
            caption="發音"
          />
        </div>
        <p className="mt-6 text-center text-2xl font-medium leading-relaxed text-[var(--color-ink)]">
          {q.sentence_blanked}
        </p>
        {q.sentence_zh && (
          <p className="mt-3 text-center text-sm text-stone-500">{q.sentence_zh}</p>
        )}
        <p className="mt-4 text-center text-sm text-stone-500">{q.prompt}</p>
        {revealed && (
          <p className="mt-4 text-center text-sm text-emerald-700">
            完整句子：{q.sentence_full}
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {q.options.map((opt) => {
          let ring = "ring-1 ring-orange-100 hover:ring-[var(--color-primary)]";
          if (revealed) {
            if (opt.id === q.correct_option_id) {
              ring = "ring-2 ring-emerald-500 bg-emerald-50";
            } else if (opt.id === selected) {
              ring = "ring-2 ring-red-400 bg-red-50";
            } else {
              ring = "ring-1 ring-stone-200 opacity-50";
            }
          }
          return (
            <button
              key={opt.id}
              type="button"
              onClick={() => handleSelect(opt.id)}
              disabled={revealed}
              className={`rounded-2xl bg-white p-5 text-center text-lg font-medium transition active:scale-[0.97] ${ring}`}
            >
              {opt.text}
            </button>
          );
        })}
      </div>

      {revealed && (
        <div className="flex flex-col items-center gap-3">
          <p
            className={`text-sm font-semibold ${
              selected === q.correct_option_id ? "text-emerald-600" : "text-red-500"
            }`}
          >
            {selected === q.correct_option_id ? "正確！" : "答錯了"}
          </p>
          <button
            type="button"
            onClick={handleNext}
            className="rounded-full bg-[var(--color-primary)] px-8 py-2.5 text-sm font-semibold text-white"
          >
            {index + 1 < questions.length ? "下一題" : "查看結果"}
          </button>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Translation Quiz
// ═══════════════════════════════════════════════════════════════════════════

function TranslationQuiz() {
  const [prompts, setPrompts] = useState<TranslationPrompt[]>([]);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [grading, setGrading] = useState(false);
  const [result, setResult] = useState<TranslationGradeResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scores, setScores] = useState<number[]>([]);
  const [finished, setFinished] = useState(false);
  const [saved, setSaved] = useState(false);
  const [wrongIds, setWrongIds] = useState<string[]>([]);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    setIndex(0);
    setAnswer("");
    setResult(null);
    setScores([]);
    setFinished(false);
    setSaved(false);
    setWrongIds([]);
    api
      .translationPrompts(5)
      .then((res) => setPrompts(res.prompts))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!finished || saved || scores.length === 0) return;
    setSaved(true);
    const correct = scores.filter((s) => s >= 3).length;
    void api
      .submitQuizResult({
        subject: "vocab",
        mode: "translation",
        correct_count: correct,
        total_count: scores.length,
        detail: { scores, wrong_ids: wrongIds },
      })
      .catch(() => {
        /* non-blocking */
      });
  }, [finished, saved, scores, wrongIds]);

  if (loading) return <LoadingCard />;
  if (error) return <ErrorCard message={error} />;
  if (prompts.length === 0)
    return <EmptyCard text="資料庫中沒有足夠的例句來出翻譯題" />;

  if (finished) {
    const avg =
      scores.length > 0
        ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1)
        : "0";
    return (
      <div className="batch-complete-enter mx-auto max-w-lg space-y-6">
        <div className="rounded-3xl bg-white p-8 text-center shadow-lg ring-1 ring-orange-100">
          <p className="text-4xl">✍️</p>
          <h2 className="mt-3 font-[family-name:var(--font-display)] text-2xl font-bold text-[var(--color-primary-dark)]">
            翻譯測驗完成！
          </h2>
          <p className="mt-4 text-3xl font-bold text-[var(--color-primary)]">
            {avg}
            <span className="text-lg text-stone-400"> / 5</span>
          </p>
          <p className="text-sm text-stone-500">平均分數</p>
          {wrongIds.length > 0 && (
            <p className="mt-3 text-sm text-orange-700">
              {wrongIds.length} 題需加強，已加入單字複習
            </p>
          )}
        </div>
        <div className="flex justify-center">
          <button
            type="button"
            onClick={load}
            className="rounded-full bg-[var(--color-primary)] px-8 py-3 text-sm font-semibold text-white shadow-md transition hover:shadow-lg active:scale-95"
          >
            再測一次
          </button>
        </div>
      </div>
    );
  }

  const prompt = prompts[index];
  const progress = ((index + 1) / prompts.length) * 100;

  async function handleSubmit() {
    if (!answer.trim() || grading) return;
    setGrading(true);
    setError("");
    try {
      const res = await api.gradeTranslation(
        prompt.source_zh,
        answer,
        prompt.hint_word || undefined,
      );
      setResult(res);
      setScores((s) => [...s, res.score]);
      if (res.score < 3) {
        setWrongIds((ids) =>
          ids.includes(prompt.question_id) ? ids : [...ids, prompt.question_id],
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "批改失敗");
    } finally {
      setGrading(false);
    }
  }

  function handleNext() {
    setAnswer("");
    setResult(null);
    if (index + 1 < prompts.length) {
      setIndex(index + 1);
    } else {
      setFinished(true);
    }
  }

  const scoreColor = (s: number) =>
    s >= 4
      ? "text-emerald-600 bg-emerald-50 ring-emerald-200"
      : s >= 3
        ? "text-orange-600 bg-orange-50 ring-orange-200"
        : "text-red-600 bg-red-50 ring-red-200";

  return (
    <div className="mx-auto max-w-lg space-y-6">
      {/* Progress */}
      <div className="space-y-1">
        <div className="flex justify-between px-1 text-xs text-stone-500">
          <span>第 {index + 1} / {prompts.length} 題</span>
          <span>{Math.round(progress)}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-stone-100">
          <div
            className="h-full rounded-full bg-gradient-to-r from-sky-300 to-sky-500 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Prompt card */}
      <div className="rounded-3xl bg-white p-8 shadow-lg ring-1 ring-orange-100">
        <span className="inline-block rounded-full bg-sky-50 px-3 py-0.5 text-xs font-semibold text-sky-700">
          翻譯
        </span>
        <p className="mt-4 text-sm text-stone-500">請將以下句子翻譯成日文：</p>
        <p className="mt-3 text-2xl font-semibold text-[var(--color-ink)]">
          {prompt.source_zh}
        </p>
        {prompt.source_en && (
          <p className="mt-1 text-sm italic text-stone-400">
            {prompt.source_en}
          </p>
        )}
        {prompt.hint_word && (
          <p className="mt-4 text-xs text-stone-400">
            提示：{prompt.hint_word}
            {prompt.hint_reading && `（${prompt.hint_reading}）`}
          </p>
        )}
      </div>

      {/* Input */}
      {!result && (
        <div className="space-y-3">
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="日本語で入力してください..."
            rows={3}
            className="w-full rounded-2xl border-2 border-stone-200 bg-white p-4 text-lg outline-none transition focus:border-[var(--color-primary)] focus:ring-0"
          />
          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleSubmit}
              disabled={grading || !answer.trim()}
              className="rounded-full bg-[var(--color-primary)] px-8 py-3 text-sm font-semibold text-white shadow-md transition hover:shadow-lg active:scale-95 disabled:opacity-50"
            >
              {grading ? "AI 批改中..." : "提交"}
            </button>
          </div>
        </div>
      )}

      {/* Grading result */}
      {result && (
        <div className="space-y-4 animate-in">
          <div
            className={`rounded-2xl p-6 ring-1 ${scoreColor(result.score)}`}
          >
            <div className="flex items-center gap-3">
              <span className="text-3xl font-bold">{result.score}</span>
              <span className="text-sm opacity-70">/ 5</span>
            </div>
            <p className="mt-3 text-base leading-relaxed">{result.feedback}</p>
          </div>

          {result.correction && (
            <div className="rounded-2xl bg-white p-5 ring-1 ring-orange-100">
              <p className="text-xs font-semibold text-stone-500">正確翻譯</p>
              <p className="mt-2 text-lg font-medium text-[var(--color-ink)]">
                {result.correction}
              </p>
            </div>
          )}

          {result.grammar_notes && (
            <div className="rounded-2xl bg-orange-50 p-5 ring-1 ring-orange-100">
              <p className="text-xs font-semibold text-orange-700">文法筆記</p>
              <p className="mt-2 text-sm text-stone-700">
                {result.grammar_notes}
              </p>
            </div>
          )}

          <div className="flex justify-center">
            <button
              type="button"
              onClick={handleNext}
              className="rounded-full bg-[var(--color-primary)] px-8 py-2.5 text-sm font-semibold text-white transition hover:shadow-md active:scale-95"
            >
              {index + 1 < prompts.length ? "下一題" : "查看結果"}
            </button>
          </div>
        </div>
      )}

      {error && <p className="text-center text-red-600">{error}</p>}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Shared small components
// ═══════════════════════════════════════════════════════════════════════════

function LoadingCard() {
  return (
    <div className="rounded-2xl bg-white p-8 text-center ring-1 ring-orange-100">
      <p className="text-stone-500">載入中...</p>
    </div>
  );
}

function ErrorCard({ message }: { message: string }) {
  return (
    <div className="rounded-2xl bg-white p-8 text-center ring-1 ring-orange-100">
      <p className="text-red-600">{message}</p>
    </div>
  );
}

function EmptyCard({ text }: { text: string }) {
  return (
    <div className="rounded-2xl bg-white p-8 text-center ring-1 ring-orange-100">
      <p className="text-stone-600">{text}</p>
    </div>
  );
}
