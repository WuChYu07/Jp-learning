import { useRef, useState } from "react";
import { api, IngestionResponse, NotionSyncPreview, TextParsePreview } from "../lib/api";

type UploadTab = "csv" | "text" | "pdf" | "notion";
type FocusType = "vocabulary" | "grammar" | "both";

export default function UploadPage() {
  const [tab, setTab] = useState<UploadTab>("csv");

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold">
        匯入學習資料
      </h1>

      {/* Tab bar */}
      <div className="flex rounded-full bg-stone-100 p-1">
        {([
          { id: "csv" as const, label: "CSV 檔案" },
          { id: "text" as const, label: "文字貼上" },
          { id: "pdf" as const, label: "PDF / 圖片" },
          { id: "notion" as const, label: "Notion" },
        ]).map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`flex-1 rounded-full px-4 py-2 text-sm font-semibold transition ${
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
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Notion Sync (preview → confirm)
// ═══════════════════════════════════════════════════════════════════════════

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
  const [forceConfirm, setForceConfirm] = useState(false);
  const [result, setResult] = useState<IngestionResponse | null>(null);
  const [error, setError] = useState("");

  async function handleSync() {
    if (syncing) return;
    setSyncing(true);
    setError("");
    setPreview(null);
    setResult(null);
    setForceOverwriteGrammar(new Set());
    setSelectedArchive(new Set());
    setForceConfirm(false);
    try {
      const res = await api.notionSync(focus, pageId.trim() || undefined);
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

  const hasPreviewItems =
    preview &&
    (preview.parsed.grammars.length > 0 ||
      preview.parsed.vocabularies.length > 0 ||
      preview.orphaned_grammars.length > 0);

  return (
    <div className="space-y-4">
      <p className="text-sm text-stone-600">
        從 Notion 筆記同步。在 backend/.env 分別設定 NOTION_VOCAB_PAGE_ID 與 NOTION_GRAMMAR_PAGE_ID。
      </p>
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

      {!preview && !result && (
        <button
          type="button"
          onClick={handleSync}
          disabled={syncing}
          className="w-full rounded-full bg-[var(--color-primary)] py-3 text-sm font-semibold text-white shadow-md transition hover:shadow-lg active:scale-[0.98] disabled:opacity-50"
        >
          {syncing ? "從 Notion 讀取中..." : "同步預覽"}
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
                單字（已存在者不覆寫意思，只補空例句／筆記）
              </p>
              {preview.parsed.vocabularies.map((item, index) => {
                const isNew = item.sync_change === "new";
                const isUpdated = item.sync_change === "updated";
                const ring = isNew
                  ? "ring-emerald-200 bg-emerald-50/40"
                  : isUpdated
                    ? "ring-amber-200 bg-amber-50/40"
                    : "ring-stone-100";
                return (
                  <label
                    key={`${item.word}-${index}`}
                    className={`flex gap-3 rounded-xl bg-white p-3 ring-1 ${ring}`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedVocab.has(index)}
                      onChange={() => toggleSet(setSelectedVocab, index)}
                      className="mt-1"
                    />
                    <div>
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
                  selectedArchive.size === 0)
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
          <p className="text-xs text-stone-500">單字</p>
        </div>
        <div className="rounded-xl bg-green-50 p-4 text-center">
          <p className="text-2xl font-bold text-emerald-700">
            {result.grammar_count}
          </p>
          <p className="text-xs text-stone-500">文法</p>
        </div>
      </div>
    </div>
  );
}
