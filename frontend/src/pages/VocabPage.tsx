import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import SpeakButton from "../components/SpeakButton";
import SwipeNavigate from "../components/SwipeNavigate";
import VocabEditModal from "../components/VocabEditModal";
import RelationHints from "../components/RelationHints";
import {
  api,
  Vocabulary,
  VocabDefinition,
  VocabularySummary,
  VocabularyWriteInput,
  formatUserFacingError,
} from "../lib/api";
import { useSlowLoadHint } from "../lib/backendStatus";
import { exampleMarks, renderHighlightedJapanese } from "../lib/highlightJapanese";
import { vocabDisplay } from "../lib/vocabDisplay";

const JLPT_FILTERS = ["", "N5", "N4", "N3", "N2", "N1", "unknown"] as const;
const JLPT_FILTER_LABELS: Partial<Record<(typeof JLPT_FILTERS)[number], string>> = {
  unknown: "Unknown（未分類）",
};
const PAGE_SIZE = 100;
const SWIPE_NAV_PREF_KEY = "vocab-swipe-nav-enabled";

const POS_LABELS: Record<string, string> = {
  noun: "名詞",
  verb: "動詞",
  i_adjective: "い形容詞",
  na_adjective: "な形容詞",
  adverb: "副詞",
  particle: "助詞",
  counter: "量詞",
  expression: "表現",
  other: "其他",
};

/** Vocabulary library: browse all words, then jump to flashcard review. */
export default function VocabPage() {
  const location = useLocation();
  const [items, setItems] = useState<VocabularySummary[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<Vocabulary | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [jlpt, setJlpt] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [nextLoading, setNextLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [swipeNavEnabled, setSwipeNavEnabled] = useState(
    () => localStorage.getItem(SWIPE_NAV_PREF_KEY) !== "off",
  );
  const [editing, setEditing] = useState(false);
  const detailReqId = useRef(0);
  const viewedIds = useRef<Set<string>>(new Set());
  const loadHint = useSlowLoadHint(loading);

  const loadList = async (offset = 0, append = false) => {
    if (append) setLoadingMore(true);
    else setLoading(true);
    setError("");
    try {
      const res = await api.listVocab({
        jlpt: jlpt || undefined,
        q: query.trim() || undefined,
        limit: PAGE_SIZE,
        offset,
      });
      setTotal(res.total);
      setItems((prev) => (append ? [...prev, ...res.items] : res.items));
      if (!append) {
        const navId = (location.state as { vocabularyId?: string } | null)?.vocabularyId;
        setSelectedId(navId || null);
      }
    } catch (err) {
      setError(formatUserFacingError(err));
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  // Reload when JLPT or search query changes (debounced for typing).
  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadList(0, false);
    }, query.trim() ? 280 : 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jlpt, query]);

  // Relation chip / deep-link: update selection without refetching the list.
  useEffect(() => {
    const navId = (location.state as { vocabularyId?: string } | null)?.vocabularyId;
    if (navId) setSelectedId(navId);
  }, [location.state]);

  useEffect(() => {
    setEditing(false);
  }, [selectedId]);

  // Fetch full detail when selection changes; record daily view bonus once per id session.
  useEffect(() => {
    if (!selectedId) {
      setSelected(null);
      return;
    }
    const req = ++detailReqId.current;
    setDetailLoading(true);
    setError("");
    api
      .getVocab(selectedId)
      .then(async (vocab) => {
        if (req !== detailReqId.current) return;
        setSelected(vocab);
        if (!viewedIds.current.has(selectedId)) {
          viewedIds.current.add(selectedId);
          try {
            const score = await api.recordVocabView(selectedId);
            if (req !== detailReqId.current) return;
            setSelected((prev) =>
              prev && prev.id === selectedId
                ? { ...prev, review_score: score.review_score }
                : prev,
            );
          } catch {
            // Viewing still works if score write fails (e.g. migration not applied).
          }
        }
      })
      .catch((err: Error) => {
        if (req !== detailReqId.current) return;
        setError(err.message);
        setSelected(null);
      })
      .finally(() => {
        if (req === detailReqId.current) setDetailLoading(false);
      });
  }, [selectedId]);

  function toggleSwipeNav() {
    setSwipeNavEnabled((prev) => {
      const next = !prev;
      localStorage.setItem(SWIPE_NAV_PREF_KEY, next ? "on" : "off");
      return next;
    });
  }

  async function goNextRandom() {
    if (nextLoading || editing) return;
    setNextLoading(true);
    setError("");
    try {
      const next = await api.randomVocab({
        exclude_id: selectedId || undefined,
        jlpt: jlpt || undefined,
      });
      window.scrollTo({ top: 0, behavior: "smooth" });
      setSelectedId(next.id);
      setSelected(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "無法載入下一個單字");
    } finally {
      setNextLoading(false);
    }
  }

  async function handleDelete() {
    if (!selected || deleting) return;
    const { primary } = vocabDisplay(selected.word, selected.reading);
    const ok = window.confirm(
      `確定刪除「${primary}」？\n\n將從列表移除；若來自 Notion，下次同步不會再自動加回。`,
    );
    if (!ok) return;
    setDeleting(true);
    setError("");
    try {
      await api.deleteVocab(selected.id);
      const next = items.filter((item) => item.id !== selected.id);
      setItems(next);
      setSelectedId(next[0]?.id ?? null);
      setSelected(null);
    } catch (err) {
      setError(formatUserFacingError(err));
    } finally {
      setDeleting(false);
    }
  }

  const filtered = useMemo(() => {
    // Server already filters by q; keep a light client pass for meaning_zh edge cases.
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((v) => {
      const { primary } = vocabDisplay(v.word, v.reading);
      const meaning = v.meaning_zh || "";
      return (
        v.word.toLowerCase().includes(q) ||
        (v.reading || "").toLowerCase().includes(q) ||
        primary.toLowerCase().includes(q) ||
        meaning.toLowerCase().includes(q)
      );
    });
  }, [items, query]);

  const hasMore = items.length < total;

  return (
    <div className="space-y-6">
      <div className={`flex flex-wrap items-start justify-between gap-4 ${selectedId ? "hidden md:flex" : ""}`}>
        <div>
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold text-[var(--color-primary-dark)]">
            單字庫
          </h1>
          <p className="mt-1 text-sm text-stone-600">
            瀏覽全部單字與詳情；通勤時可開單字卡小遊戲複習
          </p>
        </div>
        <Link
          to="/vocab/review"
          className="w-full rounded-full bg-[var(--color-primary)] px-5 py-2.5 text-center text-sm font-semibold text-white shadow-sm transition hover:opacity-90 sm:w-auto"
        >
          開始單字卡 →
        </Link>
      </div>

      <div className={`flex flex-wrap items-center gap-2 ${selectedId ? "hidden md:flex" : ""}`}>
        <select
          value={jlpt}
          onChange={(e) => setJlpt(e.target.value)}
          className="rounded-full bg-white px-4 py-2 text-sm ring-1 ring-orange-100"
        >
          <option value="">全部 JLPT</option>
          {JLPT_FILTERS.filter(Boolean).map((level) => (
            <option key={level} value={level}>
              {JLPT_FILTER_LABELS[level] ?? level}
            </option>
          ))}
        </select>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜尋單字、讀音、意思…"
          className="min-w-[180px] flex-1 rounded-full bg-white px-4 py-2 text-sm ring-1 ring-orange-100"
        />
        <p className="text-xs text-stone-400">
          {filtered.length}
          {query ? ` / ${items.length}` : ""} 筆
          {!query && total > items.length ? `（已載入，共 ${total}）` : ""}
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {loading && (
        <div className="rounded-2xl bg-amber-50 px-4 py-6 text-center ring-1 ring-amber-200">
          <p className="text-sm font-medium text-amber-950">{loadHint}</p>
          <p className="mt-2 text-xs text-amber-800">
            第一次打開或久未使用時，Render 會休眠；醒來後列表就會出現。
          </p>
        </div>
      )}

      {!loading && (
        <div className="grid gap-6 md:grid-cols-[260px_1fr]">
          <div
            className={`max-h-[70vh] space-y-2 overflow-y-auto pr-1 ${
              selectedId ? "hidden md:block" : "block"
            }`}
          >
            {filtered.map((item) => {
              const { primary, secondary } = vocabDisplay(item.word, item.reading);
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setSelectedId(item.id);
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                  className={`w-full rounded-xl px-4 py-3 text-left text-sm transition ${
                    selectedId === item.id
                      ? "bg-[var(--color-primary)] text-white"
                      : "bg-white ring-1 ring-orange-100 hover:bg-orange-50"
                  }`}
                >
                  <p className="font-medium">{primary}</p>
                  <p className="text-xs opacity-80">
                    {secondary || "—"} · {item.jlpt_level}
                    {item.meaning_zh ? ` · ${item.meaning_zh}` : ""}
                  </p>
                </button>
              );
            })}
            {filtered.length === 0 && (
              <p className="py-8 text-center text-sm text-stone-400">沒有符合的單字</p>
            )}
            {hasMore && !query && (
              <button
                type="button"
                disabled={loadingMore}
                onClick={() => void loadList(items.length, true)}
                className="w-full rounded-xl bg-stone-100 py-2 text-sm font-semibold text-stone-700 disabled:opacity-50"
              >
                {loadingMore ? "載入中..." : "載入更多"}
              </button>
            )}
          </div>

          <div className={selectedId ? "block" : "hidden md:block"}>
            {selectedId && (
              <button
                type="button"
                onClick={() => {
                  setSelectedId(null);
                  setSelected(null);
                }}
                className="mb-3 inline-flex items-center gap-1 rounded-full bg-white px-3 py-1.5 text-sm font-medium text-stone-700 ring-1 ring-orange-100 md:hidden"
              >
                ← 返回列表
              </button>
            )}
            {detailLoading && !selected ? (
              <p className="py-12 text-center text-sm text-stone-400">載入詳情...</p>
            ) : selected ? (
              <SwipeNavigate
                onSwipeRight={() => void goNextRandom()}
                disabled={!swipeNavEnabled || nextLoading || editing}
                hint={
                  swipeNavEnabled
                    ? "右滑或按下方按鈕 → 下一個（低分優先）"
                    : "右滑已關閉；可按下方按鈕前往下一個"
                }
              >
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <p className="text-xs text-stone-500">
                        {swipeNavEnabled ? "瀏覽詳情時可右滑切換下一筆" : "右滑切換已關閉"}
                      </p>
                      <button
                        type="button"
                        role="switch"
                        aria-checked={swipeNavEnabled}
                        onClick={toggleSwipeNav}
                        title={swipeNavEnabled ? "關閉右滑切換下一筆" : "開啟右滑切換下一筆"}
                        className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
                          swipeNavEnabled ? "bg-[var(--color-primary)]" : "bg-stone-300"
                        }`}
                      >
                        <span
                          className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                            swipeNavEnabled ? "translate-x-[18px]" : "translate-x-1"
                          }`}
                        />
                      </button>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs text-stone-500">
                      熟練度{" "}
                      <span className="font-semibold text-[var(--color-primary)]">
                        {Math.round(selected.review_score ?? 0)}
                      </span>
                    </p>
                    <button
                      type="button"
                      disabled={nextLoading || editing}
                      onClick={() => void goNextRandom()}
                      className="rounded-full bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                    >
                      {nextLoading ? "載入中…" : "下一個（低分優先）→"}
                    </button>
                  </div>
                  <VocabDetail
                    vocab={selected}
                    onDelete={() => void handleDelete()}
                    deleting={deleting}
                    onEditingChange={setEditing}
                    onSaved={(updated) => {
                      setSelected(updated);
                      setItems((prev) =>
                        prev.map((item) =>
                          item.id === updated.id
                            ? {
                                ...item,
                                word: updated.word,
                                reading: updated.reading,
                                jlpt_level: updated.jlpt_level,
                                meaning_zh: updated.definitions[0]?.meaning_zh ?? item.meaning_zh,
                              }
                            : item,
                        ),
                      );
                    }}
                    onError={setError}
                  />
                </div>
              </SwipeNavigate>
            ) : (
              <p className="py-12 text-center text-sm text-stone-400">選擇左側單字查看詳情</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function VocabDetail({
  vocab,
  onSaved,
  onError,
  onDelete,
  deleting,
  onEditingChange,
}: {
  vocab: Vocabulary;
  onSaved: (updated: Vocabulary) => void;
  onError: (message: string) => void;
  onDelete: () => void;
  deleting: boolean;
  onEditingChange: (editing: boolean) => void;
}) {
  const navigate = useNavigate();
  const [enriching, setEnriching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [modal, setModal] = useState<{
    source: "manual" | "ai";
    draft: Vocabulary;
  } | null>(null);
  const [activeDefIdx, setActiveDefIdx] = useState(0);
  const { primary, secondary } = vocabDisplay(vocab.word, vocab.reading);
  const primaryDef = vocab.definitions[0];
  const hasExamples = (primaryDef?.example_sentences?.length ?? 0) > 0;
  const hasNotes = Boolean(primaryDef?.notes_zh?.trim());
  const needsEnrich = !hasExamples || !hasNotes;
  const highlightCandidates = useMemo(
    () => vocabHighlightCandidates(vocab.word, vocab.reading),
    [vocab.word, vocab.reading],
  );

  useEffect(() => {
    setActiveDefIdx(0);
  }, [vocab.id]);

  useEffect(() => {
    onEditingChange(modal !== null);
  }, [modal, onEditingChange]);

  useEffect(() => {
    if (vocab.definitions.length <= 1) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const best = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!best?.target.id) return;

        const idx = vocab.definitions.findIndex((def) => `def-${def.id}` === best.target.id);
        if (idx >= 0) setActiveDefIdx(idx);
      },
      { rootMargin: "-15% 0px -55% 0px", threshold: [0.15, 0.4, 0.7] },
    );

    for (const def of vocab.definitions) {
      const element = document.getElementById(`def-${def.id}`);
      if (element) observer.observe(element);
    }

    return () => observer.disconnect();
  }, [vocab.definitions]);

  async function handleAiEnrich() {
    if (enriching) return;
    setEnriching(true);
    onError("");
    try {
      const draft = await api.aiEnrichVocab(vocab.id);
      setModal({ source: "ai", draft });
    } catch (err) {
      onError(err instanceof Error ? err.message : "AI 補充失敗");
    } finally {
      setEnriching(false);
    }
  }

  async function handleConfirm(payload: VocabularyWriteInput) {
    setSaving(true);
    onError("");
    try {
      const updated = await api.updateVocab(vocab.id, payload);
      onSaved(updated);
      setModal(null);
    } catch (err) {
      throw err;
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="rounded-2xl bg-white p-6 ring-1 ring-orange-100">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <JlptBadge level={vocab.jlpt_level} />
            {vocab.review_score != null && (
              <span className="ml-2 inline-flex rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-800 ring-1 ring-emerald-200">
                熟練度 {Math.round(vocab.review_score)}
              </span>
            )}
            <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-stone-400">
              單字
            </p>
            <h2 className="kanji-display mt-1 text-4xl font-bold text-[var(--color-ink)]">
              {primary}
            </h2>
            <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-stone-400">
              發音
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-3">
              <p className="text-xl text-stone-600">{secondary || vocab.reading || "—"}</p>
              <SpeakButton text={vocab.reading || vocab.word} label={`播放「${vocab.word}」的發音`} />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setModal({ source: "manual", draft: vocab })}
              className="rounded-full bg-stone-100 px-4 py-2 text-sm font-semibold text-stone-700"
            >
              編輯
            </button>
            <button
              type="button"
              onClick={() =>
                navigate("/practice", {
                  state: {
                    mode: "hint_translate",
                    vocabId: vocab.id,
                    vocabWord: vocab.word,
                  },
                })
              }
              className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-semibold text-white"
            >
              AI 練習
            </button>
            <button
              type="button"
              onClick={() => void handleAiEnrich()}
              disabled={enriching}
              className={`rounded-full px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 ${
                needsEnrich
                  ? "bg-violet-600 hover:bg-violet-700"
                  : "bg-stone-400 hover:bg-stone-500"
              }`}
              title={
                needsEnrich
                  ? "產生補充草稿，確認後才寫入"
                  : "例句與補充已齊；仍可產生草稿再確認"
              }
            >
              {enriching ? "產生中..." : "AI 補充"}
            </button>
            <button
              type="button"
              onClick={onDelete}
              disabled={deleting}
              className="rounded-full bg-red-50 px-4 py-2 text-sm font-semibold text-red-700 disabled:opacity-50"
            >
              {deleting ? "刪除中..." : "刪除"}
            </button>
          </div>
        </div>
      </div>

      {vocab.definitions.length === 0 && (
        <p className="text-sm text-stone-400">尚無釋義</p>
      )}

      {vocab.definitions.length > 1 && (
        <DefinitionNavigator
          definitions={vocab.definitions}
          activeIndex={activeDefIdx}
          onSelect={(index) => {
            setActiveDefIdx(index);
            const def = vocab.definitions[index];
            document.getElementById(`def-${def.id}`)?.scrollIntoView({
              behavior: "smooth",
              block: "start",
            });
          }}
        />
      )}

      {vocab.definitions.map((def, index) => {
        const multi = vocab.definitions.length > 1;
        return (
          <div
            key={def.id}
            id={`def-${def.id}`}
            className={`scroll-mt-28 space-y-4 rounded-2xl border-l-4 border-l-orange-500 bg-white p-5 ring-1 transition ${
              multi && activeDefIdx === index
                ? "ring-2 ring-orange-300 shadow-md"
                : "ring-orange-100"
            }`}
          >
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                {multi && (
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-orange-600 text-xs font-bold text-white">
                    {index + 1}
                  </span>
                )}
                <p className="text-xs font-semibold uppercase tracking-wide text-stone-400">
                  中文
                </p>
                {def.part_of_speech && def.part_of_speech !== "other" && (
                  <span className="rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-semibold text-orange-900">
                    {POS_LABELS[def.part_of_speech] || def.part_of_speech}
                  </span>
                )}
              </div>
              <p className="whitespace-pre-wrap text-lg font-semibold text-[var(--color-primary-dark)]">
                {def.meaning_zh}
              </p>
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-400">
                例句
              </p>
              {def.example_sentences?.length > 0 ? (
                <ul className="space-y-3">
                  {def.example_sentences.map((ex, i) => (
                    <li
                      key={`${ex.japanese}-${i}`}
                      className="rounded-xl bg-stone-50 px-4 py-3 text-sm text-stone-700"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="kanji-display min-w-0 flex-1 whitespace-pre-wrap font-medium">
                          {renderHighlightedJapanese(
                            ex.japanese,
                            exampleMarks(ex),
                            highlightCandidates,
                          )}
                        </p>
                        <SpeakButton size="sm" text={ex.japanese} label="播放例句發音" caption="播例句" />
                      </div>
                      {ex.reading && (
                        <p className="mt-0.5 whitespace-pre-wrap text-xs text-stone-400">{ex.reading}</p>
                      )}
                      {ex.chinese && (
                        <p className="mt-1 whitespace-pre-wrap text-stone-600">{ex.chinese}</p>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-stone-400">尚無例句 — 可按「AI 補充」或「編輯」</p>
              )}
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-400">
                補充
              </p>
              {def.notes_zh?.trim() ? (
                <p className="whitespace-pre-wrap rounded-xl bg-amber-50/80 px-4 py-3 text-sm leading-relaxed text-stone-700 ring-1 ring-amber-100">
                  {def.notes_zh}
                </p>
              ) : (
                <p className="text-sm text-stone-400">尚無補充 — 可按「AI 補充」或「編輯」</p>
              )}
            </div>
          </div>
        );
      })}

      <RelationHints entityId={vocab.id} entityType="vocabulary" />

      {modal && (
        <VocabEditModal
          key={`${modal.source}-${modal.draft.id}-${modal.draft.definitions[0]?.notes_zh || ""}-${modal.draft.definitions[0]?.example_sentences?.length || 0}`}
          initial={modal.draft}
          source={modal.source}
          saving={saving}
          onClose={() => setModal(null)}
          onConfirm={handleConfirm}
        />
      )}
    </div>
  );
}

function JlptBadge({ level }: { level: string }) {
  if (!level || level === "unknown") {
    return <p className="text-sm text-stone-400">JLPT 待分類</p>;
  }
  return (
    <span className="inline-flex rounded-full bg-orange-50 px-2.5 py-0.5 text-xs font-semibold text-orange-800 ring-1 ring-orange-200">
      JLPT {level}
    </span>
  );
}

/** Candidate substrings to highlight within example sentences: prefer the
 * headword (usually kanji, more specific), fall back to the reading. Some
 * entries pack multiple near-synonyms into one word field (e.g. 「1.務める
 * 2.勤める 3.努める」) — split those out too so each still matches its own
 * example sentence. */
function vocabHighlightCandidates(word: string, reading?: string): string[] {
  const parts = word
    .split(/\s+/)
    .map((p) => p.replace(/^\d+[.．、]\s*/, "").trim())
    .filter(Boolean);
  const candidates = [word.trim(), ...parts, reading?.trim()].filter((c): c is string =>
    Boolean(c),
  );
  return [...new Set(candidates)].sort((a, b) => b.length - a.length);
}

function DefinitionNavigator({
  definitions,
  activeIndex,
  onSelect,
}: {
  definitions: VocabDefinition[];
  activeIndex: number;
  onSelect: (index: number) => void;
}) {
  const [open, setOpen] = useState(true);

  // New word selection: expand again so tags are easy to reach.
  useEffect(() => {
    setOpen(true);
  }, [definitions.map((d) => d.id).join("|")]);

  return (
    <div className="sticky top-2 z-10 rounded-2xl bg-white/95 shadow-sm ring-1 ring-orange-200 backdrop-blur">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-orange-50/60"
      >
        <p className="text-sm font-bold text-[var(--color-primary-dark)]">
          此單字有 {definitions.length} 個釋義
        </p>
        <span className="flex items-center gap-2 text-xs text-stone-500">
          <span className="hidden sm:inline">{open ? "點選標籤可跳轉" : "點此展開"}</span>
          <span
            aria-hidden
            className={`inline-block text-stone-400 transition-transform ${open ? "rotate-180" : ""}`}
          >
            ▾
          </span>
        </span>
      </button>
      {open && (
        <div className="border-t border-orange-100 px-4 pb-4 pt-3">
          <div className="flex flex-wrap gap-2">
            {definitions.map((def, index) => {
              const label = defNavLabel(def, index);
              return (
                <button
                  key={def.id}
                  type="button"
                  data-active={activeIndex === index}
                  onClick={() => onSelect(index)}
                  className="inline-flex max-w-full items-center gap-2 rounded-full bg-stone-50 px-3 py-1.5 text-left text-sm font-semibold text-stone-700 ring-1 ring-orange-100 transition hover:bg-orange-50 data-[active=true]:bg-orange-600 data-[active=true]:text-white data-[active=true]:ring-orange-200"
                >
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                      activeIndex === index ? "bg-white/25 text-white" : "bg-orange-600 text-white"
                    }`}
                  >
                    {index + 1}
                  </span>
                  <span className="truncate">{label}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function defNavLabel(def: VocabDefinition, index: number): string {
  const meaning = def.meaning_zh?.trim();
  if (!meaning) return `釋義 ${index + 1}`;
  return meaning.length > 16 ? `${meaning.slice(0, 16)}…` : meaning;
}
