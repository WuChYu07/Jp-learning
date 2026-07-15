import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import SwipeFlashcard from "../components/SwipeFlashcard";
import { api, Grammar } from "../lib/api";

const BATCH_SIZE = 10;

type SessionStats = {
  reviewed: number;
  known: number;
  unknown: number;
};

export default function GrammarReviewPage() {
  const [cards, setCards] = useState<Grammar[]>([]);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [batchDone, setBatchDone] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [nextOffset, setNextOffset] = useState(0);
  const [totalGrammar, setTotalGrammar] = useState(0);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<SessionStats>({ reviewed: 0, known: 0, unknown: 0 });
  const [lastDelta, setLastDelta] = useState<string | null>(null);

  const loadBatch = useCallback((offset: number) => {
    setError("");
    setLoading(true);
    setBatchDone(false);
    api
      .dueGrammar(BATCH_SIZE, offset)
      .then((batch) => {
        setCards(batch.items);
        setIndex(0);
        setFlipped(false);
        setHasMore(batch.has_more);
        setNextOffset(batch.next_offset);
        setTotalGrammar(batch.total);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadBatch(0);
  }, [loadBatch]);

  const current = cards[index];

  async function handleRating(rating: string) {
    if (!current || submitting) return;
    setSubmitting(true);
    try {
      const result = await api.submitGrammarReview(current.id, rating);
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
        <Link to="/grammar" className="text-sm font-medium text-stone-500 hover:text-stone-800">
          ← 回到文法中心
        </Link>
        <div className="rounded-2xl bg-white p-8 text-center ring-1 ring-orange-100">
          <p className="text-stone-600">目前沒有可複習的文法。</p>
          {error && <p className="mt-2 text-red-600">{error}</p>}
        </div>
      </div>
    );
  }

  if (batchDone) {
    const pct = stats.reviewed > 0 ? Math.round((stats.known / stats.reviewed) * 100) : 0;
    return (
      <div className="batch-complete-enter mx-auto max-w-md space-y-6">
        <Link to="/grammar" className="text-sm font-medium text-stone-500 hover:text-stone-800">
          ← 回到文法中心
        </Link>
        <div className="rounded-3xl bg-white p-8 text-center shadow-lg ring-1 ring-orange-100">
          <p className="text-4xl">🎉</p>
          <h2 className="mt-3 font-[family-name:var(--font-display)] text-2xl font-bold text-[var(--color-primary-dark)]">
            本輪完成！
          </h2>
          <div className="mt-6 grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold">{stats.reviewed}</p>
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
          <p className="mt-4 text-sm text-stone-500">熟悉率 {pct}%</p>
          <p className="mt-1 text-sm text-stone-400">資料庫共 {totalGrammar} 個文法</p>
        </div>
        <div className="flex justify-center gap-3">
          {hasMore && (
            <button
              type="button"
              onClick={() => loadBatch(nextOffset)}
              className="rounded-full bg-[var(--color-primary)] px-8 py-3 text-sm font-semibold text-white"
            >
              繼續下一組 →
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              setStats({ reviewed: 0, known: 0, unknown: 0 });
              loadBatch(0);
            }}
            className="rounded-full bg-stone-100 px-6 py-3 text-sm font-semibold text-stone-700"
          >
            從頭開始
          </button>
        </div>
      </div>
    );
  }

  const usage = current!.usages[0];
  const meaning =
    usage?.meaning_zh ||
    usage?.meaning_blocks?.[0]?.text ||
    usage?.semantic_concept ||
    "—";
  const example = usage?.example_sentences?.[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to="/grammar" className="text-sm font-medium text-stone-500 hover:text-stone-800">
            ← 回到文法中心
          </Link>
          <h1 className="mt-1 font-[family-name:var(--font-display)] text-2xl font-bold">
            文法卡
          </h1>
          <p className="text-xs text-stone-500">左滑不熟、右滑熟悉</p>
        </div>
        <div className="text-right">
          <span className="text-sm text-stone-500">
            {index + 1} / {cards.length}
          </span>
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
        onSwipeLeft={() => void handleRating("again")}
        onSwipeRight={() => void handleRating("good")}
        front={
          <>
            <span className="mb-3 inline-block rounded-full bg-orange-50 px-3 py-0.5 text-sm text-orange-700">
              {current!.jlpt_level}
            </span>
            <p className="kanji-display text-5xl text-[var(--color-ink)]">
              {current!.grammar_point}
            </p>
            {usage?.semantic_concept && (
              <p className="mt-4 text-base text-stone-500">{usage.semantic_concept}</p>
            )}
          </>
        }
        back={
          <>
            <p className="text-2xl font-semibold text-[var(--color-primary-dark)]">{meaning}</p>
            {usage?.connection_rule && (
              <p className="mt-4 text-left text-sm text-stone-600">
                <span className="font-semibold">接續：</span>
                {usage.connection_rule}
              </p>
            )}
            {example && (
              <div className="mt-6 space-y-2 text-left text-base text-stone-600">
                <p className="font-medium">{example.japanese}</p>
                {example.reading && (
                  <p className="text-sm text-stone-400">{example.reading}</p>
                )}
                {example.chinese && <p>{example.chinese}</p>}
              </div>
            )}
          </>
        }
      />
    </div>
  );
}
