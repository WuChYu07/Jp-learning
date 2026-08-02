import { useEffect, useRef, useState } from "react";
import {
  api,
  IngestionResponse,
  JlptSuggestion,
  NotionScheduledCheck,
  NotionSyncPreview,
  SyncReport,
  TextParsePreview,
} from "../lib/api";

type UploadTab = "csv" | "text" | "pdf" | "notion" | "jlpt";
type FocusType = "vocabulary" | "grammar" | "both";
type JlptEntityFilter = "vocab" | "grammar" | "both";

export default function UploadPage() {
  const [tab, setTab] = useState<UploadTab>("csv");

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div className="flex items-start justify-between gap-3">
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold">
          匯入學習資料
        </h1>
        <a
          href={api.exportBackupUrl()}
          className="shrink-0 rounded-full bg-stone-100 px-4 py-2 text-sm font-semibold text-stone-700 transition hover:bg-stone-200"
          title="下載所有單字、文法、複習紀錄與語意關聯的 JSON 備份"
        >
          備份資料 ↓
        </a>
      </div>

      {/* Tab bar */}
      <div className="flex flex-wrap rounded-2xl bg-stone-100 p-1">
        {([
          { id: "csv" as const, label: "CSV" },
          { id: "text" as const, label: "文字" },
          { id: "pdf" as const, label: "PDF" },
          { id: "notion" as const, label: "Notion" },
          { id: "jlpt" as const, label: "JLPT" },
        ]).map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`flex-1 rounded-full px-3 py-2 text-sm font-semibold transition ${
              tab === t.id
                ? "bg-white text-[var(--color-primary)] shadow-sm"
                : "text-stone-500 hover:text-stone-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "csv" && <CsvUpload />}
      {tab === "text" && <TextPaste />}
      {tab === "pdf" && <PdfUpload />}
      {tab === "notion" && <NotionSync />}
      {tab === "jlpt" && <JlptBatchFill />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// JLPT batch fill (preview → confirm → apply)
// ═══════════════════════════════════════════════════════════════════════════

function JlptBatchFill() {
  const [entity, setEntity] = useState<JlptEntityFilter>("both");
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [items, setItems] = useState<JlptSuggestion[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [remaining, setRemaining] = useState<number | null>(null);
  const [updated, setUpdated] = useState<number | null>(null);
  const [error, setError] = useState("");

  const keyOf = (item: JlptSuggestion) => `${item.entity}:${item.id}`;

  async function handlePreview() {
    if (loading) return;
    setLoading(true);
    setError("");
    setUpdated(null);
    try {
      const res = await api.jlptPreview(entity, 20);
      setItems(res.items);
      setRemaining(res.remaining_unknown);
      setSelected(new Set(res.items.map(keyOf)));
      if (res.items.length === 0) {
        setError("目前沒有 unknown 項目可建議（或 AI 無法判斷）。");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "JLPT 預覽失敗");
      setItems([]);
      setSelected(new Set());
    } finally {
      setLoading(false);
    }
  }

  async function handleApply() {
    if (applying || selected.size === 0) return;
    setApplying(true);
    setError("");
    try {
      const payload = items
        .filter((item) => selected.has(keyOf(item)))
        .map((item) => ({
          entity: item.entity,
          id: item.id,
          jlpt_level: item.suggested_jlpt,
        }));
      const res = await api.jlptApply(payload);
      setUpdated(res.updated);
      setItems((prev) => prev.filter((item) => !selected.has(keyOf(item))));
      setSelected(new Set());
      if (remaining != null) {
        setRemaining(Math.max(0, remaining - res.updated));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "套用失敗");
    } finally {
      setApplying(false);
    }
  }

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function toggleAll(on: boolean) {
    setSelected(on ? new Set(items.map(keyOf)) : new Set());
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-stone-600">
        針對 <code className="text-xs">jlpt_level = unknown</code>{" "}
        的單字／文法批次產生建議，勾選後才寫入（不會覆寫已有等級）。
      </p>

      <div className="flex flex-wrap gap-2">
        {(
          [
            { id: "both" as const, label: "兩者" },
            { id: "vocab" as const, label: "單字" },
            { id: "grammar" as const, label: "文法" },
          ] as const
        ).map((opt) => (
          <button
            key={opt.id}
            type="button"
            onClick={() => setEntity(opt.id)}
            className={`rounded-full px-4 py-1.5 text-sm font-semibold transition ${
              entity === opt.id
                ? "bg-[var(--color-primary)] text-white"
                : "bg-stone-100 text-stone-600 hover:bg-stone-200"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={() => void handlePreview()}
        disabled={loading}
        className="w-full rounded-full bg-[var(--color-primary)] px-6 py-3 text-sm font-semibold text-white shadow-md transition hover:shadow-lg disabled:opacity-60"
      >
        {loading ? "產生建議中…" : "產生 JLPT 建議（最多 20）"}
      </button>

      {remaining != null && (
        <p className="text-xs text-stone-500">
          目前尚有約 {remaining} 筆 unknown（可連續跑多輪）。
        </p>
      )}

      {error && (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      )}

      {updated != null && (
        <p className="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          已寫入 {updated} 筆等級。
        </p>
      )}

      {items.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="font-semibold text-stone-700">
              建議 {items.length} 筆（已選 {selected.size}）
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => toggleAll(true)}
                className="text-[var(--color-primary)]"
              >
                全選
              </button>
              <button
                type="button"
                onClick={() => toggleAll(false)}
                className="text-stone-500"
              >
                清除
              </button>
            </div>
          </div>

          <ul className="max-h-96 space-y-2 overflow-y-auto">
            {items.map((item) => {
              const key = keyOf(item);
              const checked = selected.has(key);
              return (
                <li key={key}>
                  <label className="flex cursor-pointer items-start gap-3 rounded-2xl bg-white px-4 py-3 shadow-sm ring-1 ring-stone-100">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(key)}
                      className="mt-1 accent-[var(--color-primary)]"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-stone-800">
                          {item.label}
                        </span>
                        <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-stone-500">
                          {item.entity === "vocab" ? "單字" : "文法"}
                        </span>
                        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-700">
                          {item.suggested_jlpt}
                        </span>
                      </span>
                      {item.detail && (
                        <span className="mt-0.5 block truncate text-xs text-stone-500">
                          {item.detail}
                        </span>
                      )}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>

          <button
            type="button"
            onClick={() => void handleApply()}
            disabled={applying || selected.size === 0}
            className="w-full rounded-full bg-emerald-600 px-6 py-3 text-sm font-semibold text-white shadow-md transition hover:bg-emerald-700 disabled:opacity-60"
          >
            {applying ? "寫入中…" : `套用已選 ${selected.size} 筆`}
          </button>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Notion Sync (preview → confirm)
// ═══════════════════════════════════════════════════════════════════════════

function formatCheckTime(iso: string): string {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(
    d.getMinutes(),
  ).padStart(2, "0")}`;
}

function NotionSync() {
  const [focus, setFocus] = useState<FocusType>("both");
  const [pageId, setPageId] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [preview, setPreview] = useState<NotionSyncPreview | null>(null);
  const [selectedGrammar, setSelectedGrammar] = useState<Set<number>>(new Set());
  const [selectedVocab, setSelectedVocab] = useState<Set<number>>(new Set());
  const [forceOverwriteGrammar, setForceOverwriteGrammar] = useState<Set<string>>(new Set());
  const [selectedArchive, setSelectedArchive] = useState<Set<string>>(new Set());
  const [selectedArchiveVocab, setSelectedArchiveVocab] = useState<Set<string>>(new Set());
  const [expandedVocabDiff, setExpandedVocabDiff] = useState<Set<number>>(new Set());
  const [vocabFieldOverwrites, setVocabFieldOverwrites] = useState<Record<string, Set<string>>>({});
  const [forceConfirm, setForceConfirm] = useState(false);
  const [forceRefresh, setForceRefresh] = useState(false);
  const [result, setResult] = useState<IngestionResponse | null>(null);
  const [error, setError] = useState("");
  const [scheduledCheck, setScheduledCheck] = useState<NotionScheduledCheck | null>(null);

  useEffect(() => {
    api
      .notionStatus()
      .then((s) => setScheduledCheck(s.scheduled_check ?? null))
      .catch(() => setScheduledCheck(null));
  }, []);

  async function handleSync() {
    if (syncing) return;
    setSyncing(true);
    setError("");
    setPreview(null);
    setResult(null);
    setForceOverwriteGrammar(new Set());
    setSelectedArchive(new Set());
    setSelectedArchiveVocab(new Set());
    setExpandedVocabDiff(new Set());
    setVocabFieldOverwrites({});
    setForceConfirm(false);
    try {
      const res = await api.notionSync(focus, pageId.trim() || undefined, true, forceRefresh);
      if ("ingestion_id" in res) {
        setResult(res);
        return;
      }
      setPreview(res);
      setSelectedGrammar(new Set(res.parsed.grammars.map((_, i) => i)));
      setSelectedVocab(new Set(res.parsed.vocabularies.map((_, i) => i)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Notion 同步失敗");
    } finally {
      setSyncing(false);
    }
  }

  async function handleConfirm() {
    if (!preview || confirming) return;
    setConfirming(true);
    setError("");
    try {
      const filtered = {
        grammars: preview.parsed.grammars
          .filter((_, i) => selectedGrammar.has(i))
          .map((item) => ({
            ...item,
            force_overwrite: item.notion_block_id
              ? forceOverwriteGrammar.has(item.notion_block_id)
              : false,
          })),
        vocabularies: preview.parsed.vocabularies.filter((_, i) => selectedVocab.has(i)),
      };
      const res = await api.notionConfirm(
        filtered,
        preview.content_hash,
        preview.page_id,
        preview.page_title,
        preview.focus,
        {
          force: forceConfirm,
          force_overwrite_grammar_block_ids: [...forceOverwriteGrammar],
          archive_grammar_ids: [...selectedArchive],
          archive_vocab_ids: [...selectedArchiveVocab],
          vocab_field_overwrites: Object.fromEntries(
            Object.entries(vocabFieldOverwrites)
              .filter(([, fields]) => fields.size > 0)
              .map(([vocabId, fields]) => [vocabId, [...fields]]),
          ),
        },
      );
      setResult(res);
      setPreview(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "匯入失敗");
    } finally {
      setConfirming(false);
    }
  }

  function toggleSet(setter: React.Dispatch<React.SetStateAction<Set<number>>>, index: number) {
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  function toggleBlockId(
    setter: React.Dispatch<React.SetStateAction<Set<string>>>,
    id: string,
  ) {
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleVocabDiffExpanded(index: number) {
    toggleSet(setExpandedVocabDiff, index);
  }

  function toggleVocabFieldOverwrite(vocabId: string, field: string) {
    setVocabFieldOverwrites((prev) => {
      const current = new Set(prev[vocabId] ?? []);
      if (current.has(field)) current.delete(field);
      else current.add(field);
      return { ...prev, [vocabId]: current };
    });
  }

  function formatExamples(examples?: { japanese: string; chinese?: string }[]): string {
    if (!examples || examples.length === 0) return "（無）";
    return examples.map((ex) => ex.japanese + (ex.chinese ? ` → ${ex.chinese}` : "")).join("；");
  }

  const hasPreviewItems =
    preview &&
    (preview.parsed.grammars.length > 0 ||
      preview.parsed.vocabularies.length > 0 ||
      preview.orphaned_grammars.length > 0 ||
      preview.orphaned_vocabularies.length > 0);

  return (
    <div className="space-y-4">
      <p className="text-sm text-stone-600">
        從 Notion 筆記同步。在 backend/.env 分別設定 NOTION_VOCAB_PAGE_ID 與 NOTION_GRAMMAR_PAGE_ID。
      </p>

      {!preview && !result && scheduledCheck && (
        <div
          className={`rounded-xl p-3 text-xs ring-1 ${
            scheduledCheck.error
              ? "bg-red-50 text-red-800 ring-red-200"
              : scheduledCheck.has_changes
                ? "bg-amber-50 text-amber-900 ring-amber-200"
                : "bg-stone-50 text-stone-500 ring-stone-200"
          }`}
        >
          {scheduledCheck.error ? (
            <>自動排程檢查失敗：{scheduledCheck.error}</>
          ) : scheduledCheck.has_changes ? (
            <>
              自動排程於 {formatCheckTime(scheduledCheck.checked_at)} 發現待確認的變更：
              {[
                scheduledCheck.grammar_new_count > 0 && `文法新增 ${scheduledCheck.grammar_new_count}`,
                scheduledCheck.grammar_updated_count > 0 && `文法更新 ${scheduledCheck.grammar_updated_count}`,
                scheduledCheck.vocab_new_count > 0 && `單字新增 ${scheduledCheck.vocab_new_count}`,
                scheduledCheck.vocab_updated_count > 0 && `單字更新 ${scheduledCheck.vocab_updated_count}`,
                scheduledCheck.orphaned_grammar_count > 0 && `文法孤兒 ${scheduledCheck.orphaned_grammar_count}`,
                scheduledCheck.orphaned_vocab_count > 0 && `單字孤兒 ${scheduledCheck.orphaned_vocab_count}`,
                scheduledCheck.unclassified_count > 0 && `未分類標題 ${scheduledCheck.unclassified_count}`,
              ]
                .filter(Boolean)
                .join("、")}
              ，請按下方「開始同步」查看並確認。
            </>
          ) : (
            <>自動排程於 {formatCheckTime(scheduledCheck.checked_at)} 檢查過，沒有發現變更。</>
          )}
        </div>
      )}

      <div className="rounded-xl bg-emerald-50 p-3 text-xs text-emerald-800 ring-1 ring-emerald-200">
        不消耗 AI Token · 流程：同步預覽 → 勾選新增／更新 → 確認匯入
        <br />
        <span className="text-emerald-700">
          綠色＝全新 · 橘色＝有變更（預設只更新圖片／meta，勾「強制覆蓋」才整筆替換）· 無變更項目不顯示
        </span>
      </div>

      <FocusSelector value={focus} onChange={setFocus} />

      <input
        value={pageId}
        onChange={(e) => setPageId(e.target.value)}
        placeholder="覆寫 Page ID（選填；留空使用 .env 對應頁面）"
        className="w-full rounded-2xl border-2 border-stone-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-[var(--color-primary)]"
      />

      <label className="flex items-center gap-2 rounded-xl bg-white px-4 py-3 text-xs text-stone-600 ring-1 ring-stone-100">
        <input
          type="checkbox"
          checked={forceRefresh}
          onChange={(e) => setForceRefresh(e.target.checked)}
        />
        強制重新抓取（略過「頁面未變更」捷徑；一般不需要，除非懷疑捷徑判斷錯誤）
      </label>

      {!preview && !result && (
        <button
          type="button"
          onClick={handleSync}
          disabled={syncing}
          className="w-full rounded-full bg-[var(--color-primary)] py-3 text-sm font-semibold text-white shadow-md transition hover:shadow-lg active:scale-[0.98] disabled:opacity-50"
        >
          {syncing ? "從 Notion 讀取中（若頁面資料量大或有變更，可能需要數分鐘）..." : "同步預覽"}
        </button>
      )}

      {preview && !result && (
        <div className="batch-complete-enter space-y-4">
          <div className="rounded-2xl bg-white p-5 ring-1 ring-orange-100">
            <p className="font-medium text-stone-800">{preview.page_title}</p>
            <p className="mt-1 text-xs text-stone-500">
              {preview.focus === "both" ? "單字 + 文法" : preview.focus === "vocabulary" ? "單字" : "文法"}
              {" · "}
              預覽 {preview.grammar_count} 文法 · {preview.vocabulary_count} 單字
              {preview.grammar_unchanged_count + preview.vocab_unchanged_count > 0 && (
                <>
                  {" · "}
                  <span className="text-stone-400">
                    已略過 {preview.grammar_unchanged_count + preview.vocab_unchanged_count} 無變更
                  </span>
                </>
              )}
              {(preview.grammar_new_count > 0 ||
                preview.grammar_updated_count > 0 ||
                preview.vocab_new_count > 0 ||
                preview.vocab_updated_count > 0) && (
                <>
                  {" · "}
                  <span className="text-emerald-600">
                    {preview.grammar_new_count + preview.vocab_new_count} 新增
                  </span>
                  {" · "}
                  <span className="text-amber-600">
                    {preview.grammar_updated_count + preview.vocab_updated_count} 更新
                  </span>
                </>
              )}
            </p>
            {preview.sources.length > 1 && (
              <ul className="mt-2 space-y-1 text-xs text-stone-500">
                {preview.sources.map((source) => (
                  <li key={source.page_id}>
                    {source.focus === "vocabulary" ? "單字" : "文法"}: {source.page_title}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {preview.unclassified_headings.length > 0 && (
            <div className="rounded-xl bg-amber-50 p-4 text-xs text-amber-900 ring-1 ring-amber-200">
              <p className="font-semibold">
                ⚠️ 以下 {preview.unclassified_headings.length} 個標題本次還沒判斷完（分類失敗，或新標題太多一次處理不完），暫時維持原樣、不拆分。
              </p>
              <p className="mt-1 font-semibold text-amber-950">
                請再跑一次「同步預覽」繼續處理剩下的標題。
              </p>
              <ul className="mt-1.5 list-disc space-y-0.5 pl-4">
                {preview.unclassified_headings.map((h) => (
                  <li key={h.notion_block_id}>{h.heading_text}</li>
                ))}
              </ul>
            </div>
          )}

          {!hasPreviewItems && (
            <div className="rounded-xl bg-stone-50 p-6 text-center text-sm text-stone-600 ring-1 ring-stone-200">
              與資料庫一致，沒有需要匯入的新增或更新項目。
            </div>
          )}

          {preview.parsed.grammars.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-stone-500">文法</p>
              {preview.parsed.grammars.map((item, index) => {
                const isNew = item.sync_change === "new";
                const isUpdated = item.sync_change === "updated";
                const ring = isNew
                  ? "ring-emerald-200 bg-emerald-50/40"
                  : isUpdated
                    ? "ring-amber-200 bg-amber-50/40"
                    : "ring-stone-100";
                return (
                  <label
                    key={`${item.notion_block_id ?? item.grammar_point}-${index}`}
                    className={`flex gap-3 rounded-xl bg-white p-3 ring-1 ${ring}`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedGrammar.has(index)}
                      onChange={() => toggleSet(setSelectedGrammar, index)}
                      className="mt-1"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-stone-800">
                        {item.grammar_point}
                        {isNew && (
                          <span className="ml-2 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-normal text-emerald-700">
                            全新
                          </span>
                        )}
                        {isUpdated && (
                          <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-normal text-amber-800">
                            有變更
                          </span>
                        )}
                      </p>
                      {isUpdated && item.notion_block_id && (
                        <label className="mt-2 flex items-center gap-2 text-xs text-amber-900">
                          <input
                            type="checkbox"
                            checked={forceOverwriteGrammar.has(item.notion_block_id)}
                            onChange={() =>
                              toggleBlockId(setForceOverwriteGrammar, item.notion_block_id!)
                            }
                          />
                          強制以 Notion 覆蓋正文與用法
                        </label>
                      )}
                      {item.usages.length > 1 ? (
                        <ul className="mt-1 space-y-0.5 text-xs text-stone-600">
                          {item.usages.map((usage, usageIndex) => (
                            <li key={usageIndex}>
                              {usageIndex + 1}. {usage.semantic_concept}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        item.usages[0]?.meaning_zh && (
                          <p className="mt-1 text-xs text-stone-600">{item.usages[0].meaning_zh}</p>
                        )
                      )}
                    </div>
                  </label>
                );
              })}
            </div>
          )}

          {preview.parsed.vocabularies.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-stone-500">
                單字（預設只補空例句／筆記；有變更可展開選擇要覆蓋的欄位）
              </p>
              {preview.parsed.vocabularies.map((item, index) => {
                const isNew = item.sync_change === "new";
                const isUpdated = item.sync_change === "updated";
                const ring = isNew
                  ? "ring-emerald-200 bg-emerald-50/40"
                  : isUpdated
                    ? "ring-amber-200 bg-amber-50/40"
                    : "ring-stone-100";
                const expanded = expandedVocabDiff.has(index);
                const vocabId = item.vocab_id;
                const overwriteSet = vocabId ? vocabFieldOverwrites[vocabId] : undefined;
                const diffRows = [
                  {
                    field: "meaning_zh",
                    label: "意思",
                    notion: item.definitions[0]?.meaning_zh,
                    current: item.current_meaning_zh,
                  },
                  {
                    field: "notes_zh",
                    label: "補充筆記",
                    notion: item.definitions[0]?.notes_zh,
                    current: item.current_notes_zh,
                  },
                  {
                    field: "example_sentences",
                    label: "例句",
                    notion: formatExamples(item.definitions[0]?.example_sentences),
                    current: formatExamples(item.current_example_sentences),
                  },
                ];
                return (
                  <div
                    key={`${item.word}-${index}`}
                    className={`rounded-xl bg-white p-3 ring-1 ${ring}`}
                  >
                    <label className="flex gap-3">
                      <input
                        type="checkbox"
                        checked={selectedVocab.has(index)}
                        onChange={() => toggleSet(setSelectedVocab, index)}
                        className="mt-1"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium">
                          {item.word}
                          {isNew && (
                            <span className="ml-2 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-normal text-emerald-700">
                              全新
                            </span>
                          )}
                          {isUpdated && (
                            <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-normal text-amber-800">
                              有變更
                            </span>
                          )}
                        </p>
                        <p className="text-xs text-stone-500">
                          {item.reading} — {item.definitions[0]?.meaning_zh}
                        </p>
                      </div>
                    </label>

                    {isUpdated && vocabId && (
                      <div className="mt-2 pl-7">
                        <button
                          type="button"
                          onClick={() => toggleVocabDiffExpanded(index)}
                          className="text-xs font-medium text-amber-800 underline decoration-dotted"
                        >
                          {expanded ? "收合差異" : "顯示 Notion／App 差異"}
                        </button>

                        {expanded && (
                          <div className="mt-2 space-y-2 rounded-lg bg-amber-50/60 p-3 ring-1 ring-amber-100">
                            {diffRows.map((row) => (
                              <label key={row.field} className="flex items-start gap-2">
                                <input
                                  type="checkbox"
                                  checked={overwriteSet?.has(row.field) ?? false}
                                  onChange={() =>
                                    toggleVocabFieldOverwrite(vocabId, row.field)
                                  }
                                  className="mt-0.5"
                                />
                                <span className="min-w-0 flex-1 text-xs">
                                  <span className="font-semibold text-stone-700">
                                    {row.label}
                                  </span>
                                  <span className="mt-0.5 block text-stone-500">
                                    Notion：{row.notion || "（無）"}
                                  </span>
                                  <span className="block text-stone-400">
                                    App：{row.current || "（無）"}
                                  </span>
                                </span>
                              </label>
                            ))}
                            <p className="text-[11px] text-amber-700">
                              勾選欄位＝確認匯入時以 Notion 內容覆蓋；不勾＝維持現狀（僅補空欄位）。
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {preview.orphaned_grammars.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-stone-500">
                Notion 已移除 · App 仍有（勾選則 archive）
              </p>
              {preview.orphaned_grammars.map((item) => (
                <label
                  key={item.id}
                  className="flex gap-3 rounded-xl bg-stone-50 p-3 ring-1 ring-stone-200"
                >
                  <input
                    type="checkbox"
                    checked={selectedArchive.has(item.id)}
                    onChange={() => toggleBlockId(setSelectedArchive, item.id)}
                    className="mt-1"
                  />
                  <div>
                    <p className="font-medium text-stone-700">{item.grammar_point}</p>
                    <p className="text-xs text-stone-500">僅存在於 App，Notion 頁面已找不到</p>
                  </div>
                </label>
              ))}
            </div>
          )}

          {preview.orphaned_vocabularies.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-stone-500">
                單字：Notion 已移除 · App 仍有（勾選則 archive）
              </p>
              {preview.orphaned_vocabularies.map((item) => (
                <label
                  key={item.id}
                  className="flex gap-3 rounded-xl bg-stone-50 p-3 ring-1 ring-stone-200"
                >
                  <input
                    type="checkbox"
                    checked={selectedArchiveVocab.has(item.id)}
                    onChange={() => toggleBlockId(setSelectedArchiveVocab, item.id)}
                    className="mt-1"
                  />
                  <div>
                    <p className="font-medium text-stone-700">
                      {item.word}
                      {item.reading && (
                        <span className="ml-1 text-xs text-stone-400">（{item.reading}）</span>
                      )}
                    </p>
                    <p className="text-xs text-stone-500">僅存在於 App，Notion 頁面已找不到</p>
                  </div>
                </label>
              ))}
            </div>
          )}

          <label className="flex items-center gap-2 rounded-xl bg-white px-4 py-3 text-xs text-stone-600 ring-1 ring-stone-100">
            <input
              type="checkbox"
              checked={forceConfirm}
              onChange={(e) => setForceConfirm(e.target.checked)}
            />
            強制寫入（略過整頁快取；同一頁重複 Confirm 時請勾選）
          </label>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleConfirm}
              disabled={
                confirming ||
                (selectedGrammar.size === 0 &&
                  selectedVocab.size === 0 &&
                  selectedArchive.size === 0 &&
                  selectedArchiveVocab.size === 0)
              }
              className="flex-1 rounded-full bg-emerald-600 py-3 text-sm font-semibold text-white shadow-md transition hover:shadow-lg active:scale-[0.98] disabled:opacity-50"
            >
              {confirming ? "匯入中..." : "確認匯入"}
            </button>
            <button
              type="button"
              onClick={() => setPreview(null)}
              className="rounded-full bg-stone-100 px-6 py-3 text-sm font-semibold text-stone-700 transition hover:bg-stone-200"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {error && <ErrorBox message={error} />}
      {result && <ResultCard result={result} />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// CSV Upload
// ═══════════════════════════════════════════════════════════════════════════

function CsvUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [focus, setFocus] = useState<FocusType>("both");
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<IngestionResponse | null>(null);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleUpload() {
    if (!file || uploading) return;
    setUploading(true);
    setError("");
    setResult(null);
    try {
      const res = await api.uploadFile(file, focus);
      setResult(res);
      setFile(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "上傳失敗");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-stone-600">
        上傳 CSV 檔案，格式請參考{" "}
        <code className="rounded bg-stone-100 px-1 text-xs">data/curated/vocabulary.csv</code>
        {" "}範例。不消耗 AI Token。
      </p>

      <DropZone
        accept=".csv"
        file={file}
        onFile={setFile}
        inputRef={inputRef}
        hint="支援 CSV 檔案"
      />
      <FocusSelector value={focus} onChange={setFocus} />
      <UploadButton
        disabled={!file || uploading}
        loading={uploading}
        onClick={handleUpload}
      />
      {error && <ErrorBox message={error} />}
      {result && <ResultCard result={result} />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Text Paste (Gemini parse + preview + confirm)
// ═══════════════════════════════════════════════════════════════════════════

function TextPaste() {
  const [text, setText] = useState("");
  const [focus, setFocus] = useState<FocusType>("both");
  const [parsing, setParsing] = useState(false);
  const [preview, setPreview] = useState<TextParsePreview | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<IngestionResponse | null>(null);
  const [error, setError] = useState("");

  async function handleParse() {
    if (!text.trim() || parsing) return;
    setParsing(true);
    setError("");
    setPreview(null);
    setResult(null);
    try {
      const res = await api.parseText(text.trim(), focus);
      setPreview(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "解析失敗");
    } finally {
      setParsing(false);
    }
  }

  async function handleConfirm() {
    if (!preview || confirming) return;
    setConfirming(true);
    setError("");
    try {
      const res = await api.confirmTextImport(preview.parsed, preview.content_hash, focus);
      setResult(res);
      setPreview(null);
      setText("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "匯入失敗");
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-stone-600">
        從筆記 App 複製文字貼到下方，AI 會自動整理成單字卡和文法。
      </p>
      <div className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800 ring-1 ring-amber-200">
        ⚠️ 此功能會呼叫 Gemini API，消耗約 500-2000 tokens
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="在這裡貼上你的筆記文字..."
        rows={8}
        className="w-full rounded-2xl border-2 border-stone-200 bg-white p-4 text-sm outline-none transition focus:border-[var(--color-primary)]"
      />

      <FocusSelector value={focus} onChange={setFocus} />

      {!preview && !result && (
        <button
          type="button"
          onClick={handleParse}
          disabled={!text.trim() || parsing}
          className="w-full rounded-full bg-[var(--color-primary)] py-3 text-sm font-semibold text-white shadow-md transition hover:shadow-lg active:scale-[0.98] disabled:opacity-50"
        >
          {parsing ? "AI 解析中..." : "解析預覽"}
        </button>
      )}

      {/* Preview */}
      {preview && !result && (
        <div className="batch-complete-enter space-y-4">
          <div className="rounded-2xl bg-white p-5 ring-1 ring-orange-100">
            <p className="text-sm font-medium text-stone-700">解析結果預覽</p>
            <div className="mt-3 grid grid-cols-2 gap-4">
              <div className="rounded-xl bg-orange-50 p-4 text-center">
                <p className="text-2xl font-bold text-[var(--color-primary-dark)]">
                  {preview.vocabulary_count}
                </p>
                <p className="text-xs text-stone-500">單字</p>
              </div>
              <div className="rounded-xl bg-green-50 p-4 text-center">
                <p className="text-2xl font-bold text-emerald-700">
                  {preview.grammar_count}
                </p>
                <p className="text-xs text-stone-500">文法</p>
              </div>
            </div>
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleConfirm}
              disabled={confirming}
              className="flex-1 rounded-full bg-emerald-600 py-3 text-sm font-semibold text-white shadow-md transition hover:shadow-lg active:scale-[0.98] disabled:opacity-50"
            >
              {confirming ? "匯入中..." : "確認匯入"}
            </button>
            <button
              type="button"
              onClick={() => setPreview(null)}
              className="rounded-full bg-stone-100 px-6 py-3 text-sm font-semibold text-stone-700 transition hover:bg-stone-200"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {error && <ErrorBox message={error} />}
      {result && <ResultCard result={result} />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// PDF / Image Upload
// ═══════════════════════════════════════════════════════════════════════════

function PdfUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [focus, setFocus] = useState<FocusType>("both");
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<IngestionResponse | null>(null);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleUpload() {
    if (!file || uploading) return;
    setUploading(true);
    setError("");
    setResult(null);
    try {
      const res = await api.uploadFile(file, focus);
      setResult(res);
      setFile(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "上傳失敗");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-stone-600">
        上傳 PDF 或圖片，AI 會自動辨識內容並解析。
      </p>
      <div className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800 ring-1 ring-amber-200">
        ⚠️ 實驗性功能 — 消耗約 1000-5000 tokens，圖片型 PDF 辨識率可能不完整
      </div>

      <DropZone
        accept=".pdf,.jpg,.jpeg,.png,.webp"
        file={file}
        onFile={setFile}
        inputRef={inputRef}
        hint="支援 PDF、JPEG、PNG、WebP（最大 10 MB）"
      />
      <FocusSelector value={focus} onChange={setFocus} />
      <UploadButton
        disabled={!file || uploading}
        loading={uploading}
        onClick={handleUpload}
        label="上傳並解析"
        loadingLabel="AI 解析中..."
      />
      {error && <ErrorBox message={error} />}
      {result && <ResultCard result={result} />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Shared components
// ═══════════════════════════════════════════════════════════════════════════

function DropZone({
  accept,
  file,
  onFile,
  inputRef,
  hint,
}: {
  accept: string;
  file: File | null;
  onFile: (f: File | null) => void;
  inputRef: React.RefObject<HTMLInputElement | null>;
  hint: string;
}) {
  const [dragOver, setDragOver] = useState(false);

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const f = e.dataTransfer.files[0];
        if (f) onFile(f);
      }}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-3xl border-2 border-dashed p-10 text-center transition ${
        dragOver
          ? "border-[var(--color-primary)] bg-orange-50"
          : "border-stone-300 bg-white hover:border-orange-300 hover:bg-orange-50/50"
      }`}
    >
      <p className="text-3xl">📄</p>
      <p className="mt-2 font-medium text-stone-700">
        {file ? file.name : "拖放檔案，或點擊選擇"}
      </p>
      <p className="mt-1 text-xs text-stone-400">{hint}</p>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
      />
    </div>
  );
}

function FocusSelector({
  value,
  onChange,
}: {
  value: FocusType;
  onChange: (v: FocusType) => void;
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-stone-500">解析範圍</p>
      <div className="flex gap-2">
        {([
          { value: "both" as const, label: "全部" },
          { value: "vocabulary" as const, label: "僅單字" },
          { value: "grammar" as const, label: "僅文法" },
        ]).map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
              value === opt.value
                ? "bg-[var(--color-primary)] text-white"
                : "bg-stone-100 text-stone-600 hover:bg-stone-200"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function UploadButton({
  disabled,
  loading,
  onClick,
  label = "上傳",
  loadingLabel = "處理中...",
}: {
  disabled: boolean;
  loading: boolean;
  onClick: () => void;
  label?: string;
  loadingLabel?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="w-full rounded-full bg-[var(--color-primary)] py-3 text-sm font-semibold text-white shadow-md transition hover:shadow-lg active:scale-[0.98] disabled:opacity-50"
    >
      {loading ? loadingLabel : label}
    </button>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-2xl bg-red-50 p-4 text-sm text-red-700 ring-1 ring-red-200">
      {message}
    </div>
  );
}

function ResultCard({ result }: { result: IngestionResponse }) {
  return (
    <div className="batch-complete-enter rounded-3xl bg-white p-6 shadow-lg ring-1 ring-orange-100">
      <div className="flex items-center gap-3">
        <span className="text-3xl">{result.cached ? "📋" : "✅"}</span>
        <p className="font-semibold text-[var(--color-primary-dark)]">
          {result.cached ? "已有相同資料（快取命中）" : "匯入完成！"}
        </p>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-4">
        <div className="rounded-xl bg-orange-50 p-4 text-center">
          <p className="text-2xl font-bold text-[var(--color-primary-dark)]">
            {result.vocabulary_count}
          </p>
          <p className="text-xs text-stone-500">單字寫入／更新</p>
        </div>
        <div className="rounded-xl bg-green-50 p-4 text-center">
          <p className="text-2xl font-bold text-emerald-700">
            {result.grammar_count}
          </p>
          <p className="text-xs text-stone-500">文法寫入／更新</p>
        </div>
      </div>
      {result.report && <SyncReportPanel report={result.report} />}
    </div>
  );
}

function SyncReportPanel({ report }: { report: SyncReport }) {
  const rows: {
    label: string;
    source: number;
    added: number;
    updated: number;
    skipped: number;
    deduped: number;
  }[] = [
    {
      label: "單字",
      source: report.vocab_source_rows,
      added: report.vocab_new,
      updated: report.vocab_updated,
      skipped: report.vocab_skipped,
      deduped: report.vocab_dedupe_removed,
    },
    {
      label: "文法",
      source: report.grammar_source_rows,
      added: report.grammar_new,
      updated: report.grammar_updated,
      skipped: report.grammar_skipped,
      deduped: report.grammar_dedupe_removed,
    },
  ];

  const hasAny = rows.some((r) => r.source > 0);
  if (!hasAny) {
    return (
      <p className="mt-4 rounded-xl bg-stone-50 px-4 py-3 text-center text-xs text-stone-500 ring-1 ring-stone-100">
        沒有來源項目可處理。
      </p>
    );
  }

  return (
    <div className="mt-5 overflow-hidden rounded-2xl ring-1 ring-stone-100">
      <div className="bg-stone-50 px-4 py-2 text-xs font-semibold text-stone-600">
        同步品質報表
      </div>
      <table className="w-full text-center text-xs">
        <thead>
          <tr className="border-b border-stone-100 text-stone-400">
            <th className="py-2 font-medium">類型</th>
            <th className="py-2 font-medium">來源</th>
            <th className="py-2 font-medium text-emerald-600">新增</th>
            <th className="py-2 font-medium text-amber-600">更新</th>
            <th className="py-2 font-medium">略過</th>
            <th className="py-2 font-medium">去重</th>
          </tr>
        </thead>
        <tbody>
          {rows
            .filter((r) => r.source > 0)
            .map((r) => (
              <tr key={r.label} className="border-b border-stone-50 last:border-0">
                <td className="py-2 font-medium text-stone-700">{r.label}</td>
                <td className="py-2 text-stone-600">{r.source}</td>
                <td className="py-2 font-semibold text-emerald-700">{r.added}</td>
                <td className="py-2 font-semibold text-amber-700">{r.updated}</td>
                <td className="py-2 text-stone-500">{r.skipped}</td>
                <td className="py-2 text-stone-400">{r.deduped}</td>
              </tr>
            ))}
        </tbody>
      </table>
      <p className="bg-stone-50/60 px-4 py-2 text-[11px] leading-relaxed text-stone-400">
        來源＝解析出的筆數；略過＝內容一致未變動；去重＝來源內重複而合併。
      </p>
    </div>
  );
}
