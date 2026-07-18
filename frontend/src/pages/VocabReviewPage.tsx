import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import SpeakButton from "../components/SpeakButton";
import SwipeFlashcard from "../components/SwipeFlashcard";
import VocabRelationHints from "../components/VocabRelationHints";
import { api, Vocabulary } from "../lib/api";
import { vocabDisplay } from "../lib/vocabDisplay";

const BATCH_SIZE = 10;

type SessionStats = {
  reviewed: number;
  known: number;
  unknown: number;
  ratings: Record<"again" | "hard" | "good" | "easy", number>;
  scoreDelta: number;
  pointsDelta: number;
};

const EMPTY_STATS: SessionStats = {
  reviewed: 0,
  known: 0,
  unknown: 0,
  ratings: { again: 0, hard: 0, good: 0, easy: 0 },
  scoreDelta: 0,
  pointsDelta: 0,
};

/** Commute-friendly flashcard review mini-game. */
export default function VocabReviewPage() {
  const [cards, setCards] = useState<Vocabulary[]>([]);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [batchDone, setBatchDone] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [nextOffset, setNextOffset] = useState(0);
  const [totalVocab, setTotalVocab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<SessionStats>(EMPTY_STATS);
  const [lastDelta, setLastDelta] = useState<string | null>(null);

  const currentOffset = useRef(0);

  const loadBatch = useCallback((offset: number) => {
    setError("");
    setLoading(true);
    setBatchDone(false);
    currentOffset.current = offset;

    api
      .dueVocab(BATCH_SIZE, offset)
      .then((batch) => {
        setCards(batch.items);
        setIndex(0);
        setFlipped(false);
        setHasMore(batch.has_more);
        setNextOffset(batch.next_offset);
        setTotalVocab(batch.total);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadBatch(0);
  }, [loadBatch]);

  const current = cards[index];

  async function handleRating(rating: "again" | "hard" | "good" | "easy") {
    if (!current || submitting) return;
    setSubmitting(true);
    try {
      const result = await api.submitReview(current.id, rating);
      const sd = result.score_delta ?? 0;
      const pd = result.points_delta ?? 0;
      if (sd !== 0 || pd !== 0) {
        const scorePart = sd > 0 ? `熟練度 +${sd}` : sd < 0 ? `熟練度 ${sd}` : "";
        const pointPart = pd > 0 ? `總分 +${pd}` : pd < 0 ? `總分 ${pd}` : "";
        setLastDelta([scorePart, pointPart].filter(Boolean).join(" · "));
      } else {
        setLastDelta(null);
      }

      const isKnown = rating === "good" || rating === "easy";
      setStats((s) => ({
        reviewed: s.reviewed + 1,
        known: s.known + (isKnown ? 1 : 0),
        unknown: s.unknown + (isKnown ? 0 : 1),
        ratings: { ...s.ratings, [rating]: s.ratings[rating] + 1 },
        scoreDelta: s.scoreDelta + sd,
        pointsDelta: s.pointsDelta + pd,
      }));

      setFlipped(false);
      if (index + 1 < cards.length) {
        setIndex(index + 1);
      } else {
        setBatchDone(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失敗");
    } finally {
      setSubmitting(false);
    }
  }

  function handleContinue() {
    loadBatch(nextOffset);
  }

  function handleRestart() {
    setStats(EMPTY_STATS);
    loadBatch(0);
  }

  if (loading) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center ring-1 ring-orange-100">
        <p className="text-stone-500">載入中...</p>
      </div>
    );
  }

  if (!current && !batchDone) {
    return (
      <div className="space-y-4">
        <Link to="/vocab" className="text-sm font-medium text-stone-500 hover:text-stone-800">
          ← 回到單字庫
        </Link>
        <div className="rounded-2xl bg-white p-8 text-center ring-1 ring-orange-100">
          <p className="text-stone-600">目前沒有可複習的單字。</p>
          {error && <p className="mt-2 text-red-600">{error}</p>}
        </div>
      </div>
    );
  }

  if (batchDone) {
    const pct = stats.reviewed > 0 ? Math.round((stats.known / stats.reviewed) * 100) : 0;
    return (
      <div className="batch-complete-enter mx-auto max-w-md space-y-6">
        <Link to="/vocab" className="text-sm font-medium text-stone-500 hover:text-stone-800">
          ← 回到單字庫
        </Link>
        <div className="rounded-3xl bg-white p-8 text-center shadow-lg ring-1 ring-orange-100">
          <p className="text-4xl">🎉</p>
          <h2 className="mt-3 font-[family-name:var(--font-display)] text-2xl font-bold text-[var(--color-primary-dark)]">
            本輪完成！
          </h2>

          <div className="mt-6 grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-[var(--color-ink)]">{stats.reviewed}</p>
              <p className="text-xs text-stone-500">已複習</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-emerald-600">{stats.known}</p>
              <p className="text-xs text-stone-500">熟悉</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-red-500">{stats.unknown}</p>
              <p className="text-xs text-stone-500">不熟</p>
            </div>
          </div>

          <div className="mx-auto mt-4 h-2 w-full max-w-xs overflow-hidden rounded-full bg-stone-100">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="mt-1 text-sm text-stone-500">正確率 {pct}%</p>
          <div className="mt-4 grid grid-cols-4 gap-2 text-xs">
            <p className="rounded-lg bg-red-50 py-2 text-red-700">重來 {stats.ratings.again}</p>
            <p className="rounded-lg bg-amber-50 py-2 text-amber-700">困難 {stats.ratings.hard}</p>
            <p className="rounded-lg bg-emerald-50 py-2 text-emerald-700">良好 {stats.ratings.good}</p>
            <p className="rounded-lg bg-sky-50 py-2 text-sky-700">簡單 {stats.ratings.easy}</p>
          </div>
          <p className="mt-3 text-sm font-medium text-[var(--color-primary-dark)]">
            本輪熟練度 {stats.scoreDelta >= 0 ? "+" : ""}{stats.scoreDelta}
            {" · "}總分 {stats.pointsDelta >= 0 ? "+" : ""}{stats.pointsDelta}
          </p>
          <p className="mt-4 text-sm text-stone-400">資料庫共 {totalVocab} 個單字</p>
        </div>

        <div className="flex justify-center gap-3">
          {hasMore && (
            <button
              type="button"
              onClick={handleContinue}
              className="rounded-full bg-[var(--color-primary)] px-8 py-3 text-sm font-semibold text-white shadow-md transition hover:shadow-lg active:scale-95"
            >
              繼續下一組 →
            </button>
          )}
          <button
            type="button"
            onClick={handleRestart}
            className="rounded-full bg-stone-100 px-6 py-3 text-sm font-semibold text-stone-700 transition hover:bg-stone-200 active:scale-95"
          >
            從頭開始
          </button>
        </div>
      </div>
    );
  }

  const meaning = current!.definitions[0]?.meaning_zh ?? "";
  const pos = current!.definitions[0]?.part_of_speech;
  const example = current!.definitions[0]?.example_sentences[0];
  const { primary, secondary } = vocabDisplay(current!.word, current!.reading);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to="/vocab" className="text-sm font-medium text-stone-500 hover:text-stone-800">
            ← 回到單字庫
          </Link>
          <h1 className="mt-1 font-[family-name:var(--font-display)] text-2xl font-bold">
            單字卡
          </h1>
          <p className="text-xs text-stone-500">通勤複習小遊戲 · 左滑不熟、右滑熟悉</p>
        </div>
        <div className="text-right">
          <span className="text-sm text-stone-500">
            {index + 1} / {cards.length}
          </span>
          {stats.reviewed > 0 && (
            <p className="text-xs text-stone-400">本次已複習 {stats.reviewed}</p>
          )}
        </div>
      </div>
      {error && <p className="text-red-600">{error}</p>}
      {lastDelta && (
        <p className="text-center text-sm font-medium text-emerald-700">{lastDelta}</p>
      )}

      <SwipeFlashcard
        key={current!.id}
        flipped={flipped}
        disabled={submitting}
        onFlip={() => setFlipped((f) => !f)}
        onSwipeLeft={() => handleRating("again")}
        onSwipeRight={() => handleRating("good")}
        onRateHard={() => void handleRating("hard")}
        onRateEasy={() => void handleRating("easy")}
        front={
          <>
            <p className="kanji-display text-7xl text-[var(--color-ink)]">{primary}</p>
            {secondary && (
              <p className="mt-5 text-3xl text-stone-500">{secondary}</p>
            )}
            <SpeakButton
              className="mt-6"
              size="lg"
              text={current!.reading || current!.word}
              label={`播放「${current!.word}」的發音`}
              caption="點我發音"
            />
          </>
        }
        back={
          <>
            {pos && (
              <span className="mb-3 inline-block rounded-full bg-orange-50 px-3 py-0.5 text-sm text-orange-700">
                {pos}
              </span>
            )}
            <p className="text-4xl font-semibold text-[var(--color-primary-dark)]">{meaning}</p>
            {example && (
              <div className="mt-8 space-y-2 text-left text-base text-stone-600">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="min-w-0 flex-1 font-medium">{example.japanese}</p>
                  <SpeakButton
                    size="sm"
                    text={example.japanese}
                    label="播放例句發音"
                    caption="播例句"
                  />
                </div>
                {example.reading && (
                  <p className="text-sm text-stone-400">{example.reading}</p>
                )}
                {example.chinese && <p>{example.chinese}</p>}
              </div>
            )}
          </>
        }
      />

      {flipped && current && <VocabRelationHints vocabularyId={current.id} />}
    </div>
  );
}
