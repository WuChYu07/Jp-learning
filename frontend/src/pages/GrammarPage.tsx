import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import EditModalShell from "../components/EditModalShell";
import GrammarForm from "../components/GrammarForm";
import GrammarRelationSection from "../components/GrammarRelationSection";
import SpeakButton from "../components/SpeakButton";
import SwipeNavigate from "../components/SwipeNavigate";
import {
  api,
  Grammar,
  GrammarSummary,
  GrammarUsage,
  GrammarWriteInput,
  ExampleSentence,
  MeaningBlock,
  SupplementaryBlock,
  formatUserFacingError,
} from "../lib/api";
import { useSlowLoadHint } from "../lib/backendStatus";
import { renderStrikethrough } from "../lib/textFormat";

const JLPT_FILTERS = ["", "N5", "N4", "N3", "N2", "N1", "unknown"] as const;
const JLPT_FILTER_LABELS: Partial<Record<(typeof JLPT_FILTERS)[number], string>> = {
  unknown: "Unknown（未分類）",
};

const SWIPE_NAV_PREF_KEY = "grammar-swipe-nav-enabled";

function toGrammarSummary(g: Grammar): GrammarSummary {
  return {
    id: g.id,
    grammar_point: g.grammar_point,
    jlpt_level: g.jlpt_level,
    usage_count: g.usages?.length ?? 0,
    image_count: g.image_urls?.length ?? 0,
    sync_status: g.sync_status,
    needs_enrichment: g.needs_enrichment,
    manual_edited: g.manual_edited,
  };
}

const MEANING_BLOCK_STYLES: Record<MeaningBlock["variant"], string> = {
  emphasis: "bg-orange-100 text-orange-950 ring-orange-200",
  note: "bg-sky-50 text-sky-950 ring-sky-200",
  caution: "bg-amber-50 text-amber-950 ring-amber-200",
  default: "bg-stone-50 text-stone-800 ring-stone-200",
};

const USAGE_ACCENTS = [
  {
    header: "bg-orange-100 text-orange-950 ring-orange-200",
    border: "border-l-orange-500",
    badge: "bg-orange-600 text-white",
    tab: "data-[active=true]:bg-orange-600 data-[active=true]:text-white ring-orange-200",
  },
  {
    header: "bg-sky-100 text-sky-950 ring-sky-200",
    border: "border-l-sky-500",
    badge: "bg-sky-600 text-white",
    tab: "data-[active=true]:bg-sky-600 data-[active=true]:text-white ring-sky-200",
  },
  {
    header: "bg-violet-100 text-violet-950 ring-violet-200",
    border: "border-l-violet-500",
    badge: "bg-violet-600 text-white",
    tab: "data-[active=true]:bg-violet-600 data-[active=true]:text-white ring-violet-200",
  },
] as const;

export default function GrammarPage() {
  const location = useLocation();
  const [items, setItems] = useState<GrammarSummary[]>([]);
  const [selected, setSelected] = useState<Grammar | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [error, setError] = useState("");
  const loadHint = useSlowLoadHint(listLoading);
  const [query, setQuery] = useState("");
  const [jlpt, setJlpt] = useState("");
  const [nextLoading, setNextLoading] = useState(false);
  const [swipeNavEnabled, setSwipeNavEnabled] = useState(
    () => localStorage.getItem(SWIPE_NAV_PREF_KEY) !== "off",
  );
  const [enriching, setEnriching] = useState(false);
  const [explaining, setExplaining] = useState(false);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  const [activeUsageIdx, setActiveUsageIdx] = useState(0);
  const [editorMode, setEditorMode] = useState<"view" | "create" | "edit">("view");
  const [editDraft, setEditDraft] = useState<Grammar | null>(null);
  const [editSource, setEditSource] = useState<"manual" | "ai">("manual");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [imagesOpen, setImagesOpen] = useState(false);

  useEffect(() => {
    setActiveUsageIdx(0);
    setEditorMode("view");
    setEditDraft(null);
    setImagesOpen(false);
  }, [selected?.id]);

  useEffect(() => {
    if (!selected || selected.usages.length <= 1) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const best = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!best?.target.id) return;

        const idx = selected.usages.findIndex((usage) => `usage-${usage.id}` === best.target.id);
        if (idx >= 0) setActiveUsageIdx(idx);
      },
      { rootMargin: "-15% 0px -55% 0px", threshold: [0.15, 0.4, 0.7] },
    );

    for (const usage of selected.usages) {
      const element = document.getElementById(`usage-${usage.id}`);
      if (element) observer.observe(element);
    }

    return () => observer.disconnect();
  }, [selected]);

  // List reloads when JLPT / search changes (debounced).
  useEffect(() => {
    const navId = (location.state as { grammarId?: string } | null)?.grammarId;
    const timer = window.setTimeout(() => {
      setListLoading(true);
      api
        .listGrammar({
          limit: 100,
          jlpt: jlpt || undefined,
          q: query.trim() || undefined,
        })
        .then((res) => {
          setItems(res.items);
          if (navId) setSelectedId(navId);
        })
        .catch((err: unknown) => setError(formatUserFacingError(err)))
        .finally(() => setListLoading(false));
    }, query.trim() ? 280 : 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jlpt, query]);

  // Deep-link / in-page navigation via location.state.
  useEffect(() => {
    const navId = (location.state as { grammarId?: string } | null)?.grammarId;
    if (navId) setSelectedId(navId);
  }, [location.state]);

  // Fetch full detail when selection changes.
  useEffect(() => {
    if (!selectedId) {
      setSelected(null);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    api
      .getGrammar(selectedId)
      .then((g) => {
        if (cancelled) return;
        setSelected(g);
        setItems((prev) => {
          const summary = toGrammarSummary(g);
          if (prev.some((x) => x.id === g.id)) {
            return prev.map((x) => (x.id === g.id ? { ...x, ...summary } : x));
          }
          return [...prev, summary].sort((a, b) =>
            a.grammar_point.localeCompare(b.grammar_point, "ja"),
          );
        });
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  function toggleSwipeNav() {
    setSwipeNavEnabled((prev) => {
      const next = !prev;
      localStorage.setItem(SWIPE_NAV_PREF_KEY, next ? "on" : "off");
      return next;
    });
  }

  async function goNextRandom() {
    if (nextLoading || editorMode !== "view") return;
    setNextLoading(true);
    setError("");
    try {
      const next = await api.randomGrammar({
        exclude_id: selectedId || undefined,
        jlpt: jlpt || undefined,
      });
      window.scrollTo({ top: 0, behavior: "smooth" });
      closeEditor();
      setSelectedId(next.id);
      setSelected(next);
      setItems((prev) => {
        const summary = toGrammarSummary(next);
        if (prev.some((x) => x.id === next.id)) {
          return prev.map((x) => (x.id === next.id ? { ...x, ...summary } : x));
        }
        return [...prev, summary].sort((a, b) =>
          a.grammar_point.localeCompare(b.grammar_point, "ja"),
        );
      });
    } catch (err) {
      setError(formatUserFacingError(err));
    } finally {
      setNextLoading(false);
    }
  }

  useEffect(() => {
    if (!lightboxUrl) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setLightboxUrl(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [lightboxUrl]);

  function applyDetail(g: Grammar) {
    setSelected(g);
    setSelectedId(g.id);
    setItems((prev) => {
      const summary = toGrammarSummary(g);
      if (prev.some((x) => x.id === g.id)) {
        return prev
          .map((x) => (x.id === g.id ? { ...x, ...summary } : x))
          .sort((a, b) => a.grammar_point.localeCompare(b.grammar_point, "ja"));
      }
      return [...prev, summary].sort((a, b) =>
        a.grammar_point.localeCompare(b.grammar_point, "ja"),
      );
    });
  }

  async function handleEnrichSelected() {
    if (!selected || enriching || explaining) return;
    setEnriching(true);
    setError("");
    try {
      const draft = await api.enrichGrammar(selected.id, true);
      setEditDraft(draft);
      setEditSource("ai");
      setEditorMode("edit");
    } catch (err) {
      setError(err instanceof Error ? err.message : "圖片補全失敗");
    } finally {
      setEnriching(false);
    }
  }

  async function handleAiExplain() {
    if (!selected || explaining || enriching) return;
    setExplaining(true);
    setError("");
    try {
      const draft = await api.aiExplainGrammar(selected.id, true);
      setEditDraft(draft);
      setEditSource("ai");
      setEditorMode("edit");
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 解釋補全失敗");
    } finally {
      setExplaining(false);
    }
  }

  function openManualEdit() {
    if (!selected) return;
    setEditDraft(selected);
    setEditSource("manual");
    setEditorMode("edit");
  }

  function openCreate() {
    setEditDraft(null);
    setEditSource("manual");
    setEditorMode("create");
    setError("");
  }

  function closeEditor() {
    setEditorMode("view");
    setEditDraft(null);
    setEditSource("manual");
  }

  async function handleSave(payload: GrammarWriteInput) {
    setSaving(true);
    setError("");
    try {
      if (editorMode === "create") {
        const created = await api.createGrammar(payload);
        applyDetail(created);
        closeEditor();
        return;
      }
      if (!selected) return;
      const updated = await api.updateGrammar(selected.id, payload);
      applyDetail(updated);
      closeEditor();
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selected || deleting) return;
    const ok = window.confirm(
      `確定刪除「${selected.grammar_point}」？\n\n將從列表移除；若來自 Notion，下次同步不會再自動加回。`,
    );
    if (!ok) return;
    setDeleting(true);
    setError("");
    try {
      await api.deleteGrammar(selected.id);
      const next = items.filter((item) => item.id !== selected.id);
      setItems(next);
      setSelectedId(next[0]?.id ?? null);
      setSelected(null);
      closeEditor();
    } catch (err) {
      setError(err instanceof Error ? err.message : "刪除失敗");
    } finally {
      setDeleting(false);
    }
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (item) =>
        item.grammar_point.toLowerCase().includes(q) ||
        item.jlpt_level.toLowerCase().includes(q),
    );
  }, [items, query]);

  return (
    <div className="space-y-6">
      <div className={`flex flex-wrap items-center justify-between gap-3 ${selectedId ? "hidden md:flex" : ""}`}>
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold">文法中心</h1>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/grammar/review"
            className="rounded-full bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white"
          >
            開始文法卡 →
          </Link>
          <button
            type="button"
            onClick={openCreate}
            className="rounded-full bg-stone-100 px-4 py-2 text-sm font-semibold text-stone-700"
          >
            ＋ 新增文法
          </button>
        </div>
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
          placeholder="搜尋文法（如 てしまう、つもり）…"
          className="min-w-[180px] flex-1 rounded-full bg-white px-4 py-2 text-sm ring-1 ring-orange-100"
        />
        <p className="text-xs text-stone-400">
          {filtered.length}
          {query ? ` / ${items.length}` : ""} 筆
        </p>
      </div>

      {error && <p className="text-red-600">{error}</p>}
      {listLoading && (
        <div className="rounded-2xl bg-amber-50 px-4 py-6 text-center ring-1 ring-amber-200">
          <p className="text-sm font-medium text-amber-950">{loadHint}</p>
          <p className="mt-2 text-xs text-amber-800">
            第一次打開或久未使用時，Render 會休眠；醒來後列表就會出現。
          </p>
        </div>
      )}

      {!listLoading && (
      <div className="grid gap-6 md:grid-cols-[260px_1fr]">
        <div
          className={`max-h-[75vh] space-y-2 overflow-y-auto pr-1 ${
            selectedId ? "hidden md:block" : "block"
          }`}
        >
          {filtered.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                setSelectedId(item.id);
                closeEditor();
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
              className={`w-full rounded-xl px-4 py-3 text-left text-sm transition ${
                selectedId === item.id
                  ? "bg-[var(--color-primary)] text-white"
                  : "bg-white ring-1 ring-orange-100 hover:bg-orange-50"
              }`}
            >
              <p className="font-medium">{item.grammar_point}</p>
              <p className="text-xs opacity-80">
                {item.jlpt_level}
                {item.manual_edited ? " · 已手動編輯" : ""}
                {(item.image_count ?? 0) > 0 ? " · 有圖片" : ""}
                {(item.usage_count ?? 0) > 1 ? ` · ${item.usage_count} 用法` : ""}
              </p>
            </button>
          ))}
          {filtered.length === 0 && !error && (
            <p className="py-8 text-center text-sm text-stone-400">
              {query.trim() ? "沒有符合的文法" : "目前沒有文法資料"}
            </p>
          )}
        </div>

        <div className={selectedId ? "block" : "hidden md:block"}>
          {selectedId && (
            <button
              type="button"
              onClick={() => {
                setSelectedId(null);
                setSelected(null);
                closeEditor();
              }}
              className="mb-3 inline-flex items-center gap-1 rounded-full bg-white px-3 py-1.5 text-sm font-medium text-stone-700 ring-1 ring-orange-100 md:hidden"
            >
              ← 返回列表
            </button>
          )}

          {detailLoading && !selected && (
            <p className="py-12 text-center text-sm text-stone-400">載入詳情...</p>
          )}

          {!selected && !detailLoading && (
            <p className="py-12 text-center text-sm text-stone-400">
              {items.length === 0
                ? "尚無文法，可按右上角「新增文法」開始。"
                : "選擇左側文法查看詳情"}
            </p>
          )}

          {selected && (
          <SwipeNavigate
            onSwipeRight={() => void goNextRandom()}
            disabled={!swipeNavEnabled || nextLoading || editorMode !== "view"}
            hint={
              swipeNavEnabled
                ? "右滑或按上方按鈕 → 下一個文法（低分優先）"
                : "右滑已關閉；可按上方按鈕前往下一個文法"
            }
          >
          <div className="space-y-5">
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
              <button
                type="button"
                disabled={nextLoading || editorMode !== "view"}
                onClick={() => void goNextRandom()}
                className="rounded-full bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {nextLoading ? "載入中…" : "下一個（低分優先）→"}
              </button>
            </div>
            <div className="rounded-2xl bg-white p-5 ring-1 ring-orange-100 sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <JlptBadge level={selected.jlpt_level} />
                  {selected.manual_edited && (
                    <span className="ml-2 inline-flex rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-800 ring-1 ring-emerald-200">
                      已手動編輯
                    </span>
                  )}
                  <div className="mt-2 flex flex-wrap items-center gap-3">
                    <h2 className="kanji-display text-3xl font-bold">{selected.grammar_point}</h2>
                    <SpeakButton
                      text={selected.grammar_point}
                      label={`播放「${selected.grammar_point}」的發音`}
                    />
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void handleAiExplain()}
                    disabled={explaining || enriching}
                    className="rounded-full bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                  >
                    {explaining ? "產生中..." : "AI 解釋補全"}
                  </button>
                  <button
                    type="button"
                    onClick={openManualEdit}
                    className="rounded-full bg-stone-100 px-4 py-2 text-sm font-semibold text-stone-700"
                  >
                    編輯
                  </button>
                  <button
                    type="button"
                    onClick={handleDelete}
                    disabled={deleting}
                    className="rounded-full bg-red-50 px-4 py-2 text-sm font-semibold text-red-700 disabled:opacity-50"
                  >
                    {deleting ? "刪除中..." : "刪除"}
                  </button>
                </div>
              </div>

              {(selected.image_urls?.length ?? 0) > 0 && (
                <div className="mt-4 overflow-hidden rounded-xl ring-1 ring-stone-200">
                  <button
                    type="button"
                    onClick={() => setImagesOpen((open) => !open)}
                    className="flex w-full items-center justify-between gap-3 bg-stone-50 px-4 py-3 text-left transition hover:bg-stone-100"
                    aria-expanded={imagesOpen ? "true" : "false"}
                  >
                    <span className="text-sm font-semibold text-stone-700">
                      筆記圖片（{selected.image_urls!.length}）
                    </span>
                    <span className="text-xs font-semibold text-stone-500">
                      {imagesOpen ? "收合 ▲" : "展開 ▼"}
                    </span>
                  </button>

                  {imagesOpen && (
                    <div className="space-y-3 border-t border-stone-200 bg-white p-4">
                      <div className="flex flex-wrap items-center gap-3">
                        <p className="text-sm text-stone-500">
                          點擊縮圖可放大；也可從圖片補全或更新內容。
                        </p>
                        <button
                          type="button"
                          onClick={handleEnrichSelected}
                          disabled={enriching || explaining}
                          className="rounded-full bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                        >
                          {enriching ? "補全中..." : "從圖片補全"}
                        </button>
                      </div>
                      <ImageGallery urls={selected.image_urls!} onOpen={setLightboxUrl} />
                    </div>
                  )}
                </div>
              )}
            </div>

            <GrammarRelationSection
              grammar={selected}
              grammarList={items}
              onNavigateGrammar={(grammarId) => {
                setSelectedId(grammarId);
                closeEditor();
              }}
            />

            {selected.usages.length === 0 && (
              <p className="text-sm text-stone-400">尚無用法資料</p>
            )}

            {selected.usages.length > 1 && (
              <UsageNavigator
                usages={selected.usages}
                activeIndex={activeUsageIdx}
                onSelect={(index) => {
                  setActiveUsageIdx(index);
                  const usage = selected.usages[index];
                  document.getElementById(`usage-${usage.id}`)?.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                  });
                }}
              />
            )}

            {selected.usages.map((usage, idx) => (
              <UsageCard
                key={usage.id}
                usage={usage}
                grammarPoint={selected.grammar_point}
                index={idx}
                total={selected.usages.length}
                isActive={selected.usages.length > 1 && activeUsageIdx === idx}
                nextUsageLabel={
                  idx < selected.usages.length - 1
                    ? usageNavLabel(selected.usages[idx + 1], idx + 1)
                    : undefined
                }
              />
            ))}

            {(selected.supplementary_blocks?.length ?? 0) > 0 &&
              selected.supplementary_blocks!.map((block, idx) => (
                <SupplementaryCard
                  key={`${block.title}-${idx}`}
                  block={block}
                  grammarPoint={selected.grammar_point}
                />
              ))}
          </div>
          </SwipeNavigate>
          )}
        </div>
      </div>
      )}

      {(editorMode === "create" || editorMode === "edit") && (
        <EditModalShell
          title={
            editorMode === "create"
              ? "新增文法"
              : editSource === "ai"
                ? "確認 AI 結果"
                : "編輯文法"
          }
          subtitle={
            editSource === "ai"
              ? "可再修改內容，確定後才會寫入筆記"
              : "直接修改後確定套用"
          }
          onClose={closeEditor}
        >
          <GrammarForm
            key={
              editorMode === "create"
                ? "create"
                : `${editSource}-${editDraft?.id}-${editDraft?.usages?.length ?? 0}`
            }
            mode={editorMode === "create" ? "create" : "edit"}
            initial={editorMode === "edit" ? editDraft : null}
            saving={saving}
            embedded
            submitLabel="確定套用"
            onCancel={closeEditor}
            onSubmit={handleSave}
          />
        </EditModalShell>
      )}

      {lightboxUrl && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
          onClick={() => setLightboxUrl(null)}
          role="dialog"
          aria-modal="true"
          aria-label="放大圖片"
        >
          <button
            type="button"
            className="absolute right-4 top-4 rounded-full bg-white/90 px-3 py-1 text-sm font-medium text-stone-800"
            onClick={() => setLightboxUrl(null)}
          >
            關閉
          </button>
          <img
            src={lightboxUrl}
            alt=""
            className="max-h-[90vh] max-w-[95vw] rounded-lg object-contain shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}

function JlptBadge({ level }: { level: string }) {
  if (!level || level === "unknown") {
    return <p className="text-sm text-stone-400">JLPT 待分類</p>;
  }
  return (
    <span className="inline-flex rounded-full bg-violet-50 px-3 py-1 text-xs font-bold text-violet-800 ring-1 ring-violet-200">
      JLPT {level}
    </span>
  );
}

function UsageNavigator({
  usages,
  activeIndex,
  onSelect,
}: {
  usages: GrammarUsage[];
  activeIndex: number;
  onSelect: (index: number) => void;
}) {
  const [open, setOpen] = useState(true);

  // New grammar selection: expand again so tags are easy to reach.
  useEffect(() => {
    setOpen(true);
  }, [usages.map((u) => u.id).join("|")]);

  return (
    <div className="sticky top-2 z-10 rounded-2xl bg-white/95 shadow-sm ring-1 ring-orange-200 backdrop-blur">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-orange-50/60"
      >
        <p className="text-sm font-bold text-[var(--color-primary-dark)]">
          此文法有 {usages.length} 個用法
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
            {usages.map((usage, index) => {
              const accent = USAGE_ACCENTS[index % USAGE_ACCENTS.length];
              const label = usageNavLabel(usage, index);
              return (
                <button
                  key={usage.id}
                  type="button"
                  data-active={activeIndex === index}
                  onClick={() => onSelect(index)}
                  className={`inline-flex max-w-full items-center gap-2 rounded-full px-3 py-1.5 text-left text-sm font-semibold ring-1 transition bg-stone-50 text-stone-700 hover:bg-orange-50 ${accent.tab}`}
                >
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                      activeIndex === index ? "bg-white/25 text-white" : accent.badge
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

function usageNavLabel(usage: GrammarUsage, index: number): string {
  const title = resolveChineseTitle(usage);
  if (!title) return `用法 ${index + 1}`;
  return title.length > 16 ? `${title.slice(0, 16)}…` : title;
}

function ImageGallery({
  urls,
  onOpen,
}: {
  urls: string[];
  onOpen: (url: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {urls.slice(0, 8).map((url) => (
        <button
          key={url}
          type="button"
          onClick={() => onOpen(url)}
          className="group overflow-hidden rounded-lg ring-1 ring-stone-200 transition hover:ring-orange-300"
          title="點擊放大"
        >
          <img
            src={url}
            alt=""
            className="h-24 w-24 object-cover transition group-hover:scale-105"
          />
        </button>
      ))}
    </div>
  );
}

function UsageCard({
  usage,
  grammarPoint,
  index,
  total,
  isActive = false,
  nextUsageLabel,
}: {
  usage: GrammarUsage;
  grammarPoint: string;
  index: number;
  total: number;
  isActive?: boolean;
  nextUsageLabel?: string;
}) {
  const title = resolveChineseTitle(usage);
  const blocks = resolveDetailBlocks(usage, title);
  const accent = USAGE_ACCENTS[index % USAGE_ACCENTS.length];
  const multi = total > 1;

  return (
    <div
      id={`usage-${usage.id}`}
      className={`scroll-mt-28 overflow-hidden rounded-2xl bg-white ring-1 transition ${
        multi
          ? `border-l-4 ${accent.border} ${isActive ? "ring-2 ring-orange-300 shadow-md" : "ring-orange-100"}`
          : "ring-orange-100"
      }`}
    >
      {multi && (
        <div className={`flex items-start gap-3 px-5 py-4 ring-1 ring-inset ${accent.header}`}>
          <span
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold ${accent.badge}`}
          >
            {index + 1}
          </span>
          <div className="min-w-0">
            <p className="text-xs font-bold tracking-wide opacity-80">
              用法 {index + 1}／{total}
            </p>
            {title && <p className="mt-0.5 text-lg font-bold leading-snug">{title}</p>}
          </div>
        </div>
      )}

      <div className={`space-y-3 ${multi ? "p-5 pt-4" : "p-5"}`}>
        {!multi && title && (
          <p className="text-lg font-bold text-[var(--color-primary-dark)]">{title}</p>
        )}

        {blocks.length > 0 && (
          <div className="space-y-2">
            {blocks.map((block, i) => (
              <div
                key={i}
                className={`rounded-xl p-4 text-sm font-bold leading-relaxed ring-1 ${MEANING_BLOCK_STYLES[block.variant]}`}
              >
                {block.text}
              </div>
            ))}
          </div>
        )}

        <div className="rounded-xl bg-orange-50 p-4">
          <p className="text-xs font-semibold text-stone-500">接續規則</p>
          <ConnectionRules rule={usage.connection_rule} />
        </div>

        {usage.example_sentences.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs font-semibold text-stone-500">
              例句（{usage.example_sentences.length}）
            </p>
            {usage.example_sentences.map((ex, i) => (
              <ExampleBlock key={i} example={ex} grammarPoint={grammarPoint} />
            ))}
          </div>
        )}
      </div>

      {multi && index < total - 1 && nextUsageLabel && (
        <div className="flex items-center justify-center gap-2 border-t border-dashed border-orange-100 bg-orange-50/50 px-4 py-2 text-xs font-semibold text-orange-700">
          <span>↓</span>
          <span>下一個用法：{nextUsageLabel}</span>
        </div>
      )}
    </div>
  );
}

function SupplementaryCard({
  block,
  grammarPoint,
}: {
  block: SupplementaryBlock;
  grammarPoint: string;
}) {
  return (
    <div className="rounded-2xl bg-white p-5 ring-1 ring-violet-100">
      <span className="mb-2 inline-block rounded-full bg-violet-50 px-2.5 py-0.5 text-xs font-semibold text-violet-700">
        {block.title || "補充說明"}
      </span>
      <div className="rounded-xl bg-violet-50 p-4 text-sm font-bold leading-relaxed text-violet-950 ring-1 ring-violet-100">
        {block.summary_zh}
      </div>
      {block.example_sentences.length > 0 && (
        <div className="mt-3 space-y-3">
          <p className="text-xs font-semibold text-stone-500">補充例句</p>
          {block.example_sentences.map((ex, i) => (
            <ExampleBlock key={i} example={ex} grammarPoint={grammarPoint} />
          ))}
        </div>
      )}
    </div>
  );
}

function ConnectionRules({ rule }: { rule: string }) {
  const lines = splitConnectionRules(rule);

  if (lines.length <= 1) {
    return (
      <p className="mt-1 text-sm font-semibold leading-relaxed">
        {renderStrikethrough(rule)}
      </p>
    );
  }

  return (
    <ul className="mt-2 space-y-1.5">
      {lines.map((line, index) => (
        <li key={index} className="flex gap-2 text-sm font-semibold leading-relaxed">
          <span className="shrink-0 text-orange-600">*</span>
          <span>{renderStrikethrough(line)}</span>
        </li>
      ))}
    </ul>
  );
}

/** 將接續規則拆成多行（支援換行、* 條列、或 V/イA/ナA/N 連寫的舊資料）。 */
function splitConnectionRules(rule: string): string[] {
  const trimmed = rule.trim();
  if (!trimmed) return [];

  if (trimmed.includes("\n")) {
    return trimmed
      .split(/\n+/)
      .map((line) => line.replace(/^[*•·\-]\s*/, "").trim())
      .filter(Boolean);
  }

  if (trimmed.includes("*")) {
    return trimmed
      .split(/\s*\*\s+/)
      .map((line) => line.trim())
      .filter(Boolean);
  }

  const parts = trimmed.split(
    /\s+(?=(?:V(?:\s*[\(（])|イA|ナA|N\s*[+＋の]|動詞|名詞|形容詞|數量詞|数量詞|副詞))/u,
  );

  if (parts.length > 1) {
    return parts.map((part) => part.trim()).filter(Boolean);
  }

  return [trimmed];
}

function hasChineseOrJapanese(text: string): boolean {
  return /[\u3040-\u30ff\u4e00-\u9fff]/.test(text);
}

/** 主標題一律顯示中文說明，略過舊資料的英文 semantic_concept。 */
function resolveChineseTitle(usage: GrammarUsage): string {
  const blocks = usage.meaning_blocks ?? [];
  const emphasis = blocks.find((block) => block.variant === "emphasis");
  if (emphasis?.text.trim()) return emphasis.text.trim();

  if (usage.meaning_zh?.trim() && !hasChineseOrJapanese(usage.semantic_concept)) {
    return usage.meaning_zh.trim();
  }

  if (hasChineseOrJapanese(usage.semantic_concept)) {
    return usage.semantic_concept.trim();
  }

  if (usage.meaning_zh?.trim()) return usage.meaning_zh.trim();

  return usage.semantic_concept.trim();
}

function resolveDetailBlocks(usage: GrammarUsage, title: string): MeaningBlock[] {
  const blocks = usage.meaning_blocks ?? [];
  if (blocks.length > 0) {
    return blocks.filter((block) => block.text.trim() !== title);
  }

  if (usage.meaning_zh?.trim() === title) return [];

  if (usage.meaning_zh?.trim() && usage.meaning_zh.trim() !== title) {
    return [{ text: usage.meaning_zh.trim(), variant: "default" }];
  }

  return [];
}

function ExampleBlock({
  example,
  grammarPoint,
}: {
  example: ExampleSentence;
  grammarPoint: string;
}) {
  return (
    <div className="rounded-xl bg-green-50 p-4">
      <p className="kanji-display text-base leading-relaxed">
        {renderHighlightedJapanese(example.japanese, example.highlight, grammarPoint)}
      </p>
      {example.reading && (
        <p className="mt-0.5 text-xs text-stone-400">{example.reading}</p>
      )}
      {example.chinese && (
        <p className="mt-1 text-sm text-stone-600">{example.chinese}</p>
      )}
    </div>
  );
}

/** Build candidate substrings from grammar_point like 「〜おきに」「〜つもりだ」. */
function grammarHighlightCandidates(grammarPoint: string): string[] {
  const raw = grammarPoint.trim();
  if (!raw) return [];

  const stripped = raw
    .replace(/^[〜～~]+/, "")
    .replace(/[（(].*?[）)]/g, "")
    .replace(/[／/].*$/, "")
    .trim();

  const candidates = [raw, stripped].filter(Boolean);

  // Longer first so 「つもりだった」-style matches prefer fuller forms when provided via highlight.
  const unique = [...new Set(candidates)].sort((a, b) => b.length - a.length);
  return unique.filter((c) => c.length >= 1);
}

function findHighlightRange(
  japanese: string,
  explicit: string | undefined,
  grammarPoint: string,
): { start: number; end: number } | null {
  if (explicit?.trim()) {
    const needle = explicit.trim();
    const idx = japanese.indexOf(needle);
    if (idx >= 0) return { start: idx, end: idx + needle.length };
  }

  for (const candidate of grammarHighlightCandidates(grammarPoint)) {
    const idx = japanese.indexOf(candidate);
    if (idx >= 0) return { start: idx, end: idx + candidate.length };
  }

  // Soft match: ignore 〜 and try core token again inside conjugated forms
  // e.g. grammar 「つもりだ」 in sentence 「つもりだった」 → highlight 「つもりだ」
  const core = grammarPoint
    .replace(/^[〜～~]+/, "")
    .replace(/[（(].*?[）)]/g, "")
    .replace(/[／/].*$/, "")
    .trim();
  if (core.length >= 2) {
    const idx = japanese.indexOf(core);
    if (idx >= 0) return { start: idx, end: idx + core.length };
  }

  return null;
}

function renderHighlightedJapanese(
  japanese: string,
  explicitHighlight: string | undefined,
  grammarPoint: string,
) {
  const range = findHighlightRange(japanese, explicitHighlight, grammarPoint);
  if (!range) return japanese;

  const before = japanese.slice(0, range.start);
  const mid = japanese.slice(range.start, range.end);
  const after = japanese.slice(range.end);

  return (
    <>
      {before}
      <mark className="rounded px-0.5 bg-orange-200/90 font-bold text-[var(--color-primary-dark)] not-italic">
        {mid}
      </mark>
      {after}
    </>
  );
}
