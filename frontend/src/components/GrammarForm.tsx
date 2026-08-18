import { useState, type FormEvent } from "react";
import type { ExampleSentence, Grammar, GrammarWriteInput } from "../lib/api";
import { autoGrow } from "../lib/autoGrow";

type UsageDraft = {
  semantic_concept: string;
  connection_rule: string;
  meaning_zh: string;
  example_sentences: ExampleSentence[];
};

type FormDraft = {
  grammar_point: string;
  jlpt_level: string;
  usages: UsageDraft[];
};

const JLPT_OPTIONS = ["unknown", "N5", "N4", "N3", "N2", "N1", "N3/N2", "N4/N3", "N2/N1"];

function emptyExample(): ExampleSentence {
  return { japanese: "", reading: "", chinese: "", highlights: [] };
}

function emptyUsage(): UsageDraft {
  return {
    semantic_concept: "",
    connection_rule: "",
    meaning_zh: "",
    example_sentences: [emptyExample()],
  };
}

/** Merge legacy single `highlight` into `highlights` when loading old data. */
function marksOf(ex: ExampleSentence): string[] {
  if (ex.highlights?.length) return ex.highlights;
  return ex.highlight ? [ex.highlight] : [];
}

function fromGrammar(grammar: Grammar): FormDraft {
  return {
    grammar_point: grammar.grammar_point,
    jlpt_level: grammar.jlpt_level || "unknown",
    usages:
      grammar.usages.length > 0
        ? grammar.usages.map((usage) => ({
            semantic_concept: usage.semantic_concept || "",
            connection_rule: usage.connection_rule || "",
            meaning_zh: usage.meaning_zh || "",
            example_sentences:
              usage.example_sentences.length > 0
                ? usage.example_sentences.map((ex) => ({
                    japanese: ex.japanese || "",
                    reading: ex.reading || "",
                    chinese: ex.chinese || "",
                    highlights: marksOf(ex),
                  }))
                : [emptyExample()],
          }))
        : [emptyUsage()],
  };
}

function emptyDraft(): FormDraft {
  return {
    grammar_point: "",
    jlpt_level: "unknown",
    usages: [emptyUsage()],
  };
}

function toPayload(draft: FormDraft): GrammarWriteInput {
  return {
    grammar_point: draft.grammar_point.trim(),
    jlpt_level: draft.jlpt_level.trim() || "unknown",
    usages: draft.usages.map((usage) => ({
      semantic_concept: usage.semantic_concept.trim() || draft.grammar_point.trim(),
      connection_rule: usage.connection_rule.trim(),
      meaning_zh: usage.meaning_zh.trim() || undefined,
      example_sentences: usage.example_sentences
        .filter((ex) => ex.japanese.trim())
        .map((ex) => ({
          japanese: ex.japanese.trim(),
          reading: ex.reading?.trim() || undefined,
          chinese: ex.chinese?.trim() || undefined,
          highlights: (ex.highlights ?? []).map((h) => h.trim()).filter(Boolean),
        })),
    })),
  };
}

export default function GrammarForm({
  mode,
  initial,
  saving,
  onCancel,
  onSubmit,
  title,
  submitLabel,
  embedded = false,
}: {
  mode: "create" | "edit";
  initial?: Grammar | null;
  saving: boolean;
  onCancel: () => void;
  onSubmit: (payload: GrammarWriteInput) => Promise<void>;
  title?: string;
  submitLabel?: string;
  /** When true, omit outer card chrome (used inside EditModalShell). */
  embedded?: boolean;
}) {
  const [draft, setDraft] = useState<FormDraft>(() =>
    mode === "edit" && initial ? fromGrammar(initial) : emptyDraft(),
  );
  const [localError, setLocalError] = useState("");

  function updateUsage(index: number, patch: Partial<UsageDraft>) {
    setDraft((prev) => ({
      ...prev,
      usages: prev.usages.map((usage, i) => (i === index ? { ...usage, ...patch } : usage)),
    }));
  }

  /** Wraps the current textarea selection in `==...==` so it renders as highlighted. */
  function wrapSelectionAsMark(
    usageIndex: number,
    field: "semantic_concept" | "connection_rule" | "meaning_zh",
    input: HTMLTextAreaElement,
  ) {
    const { selectionStart, selectionEnd, value } = input;
    if (selectionStart == null || selectionEnd == null || selectionStart === selectionEnd) return;
    const selected = value.slice(selectionStart, selectionEnd);
    if (!selected.trim() || selected.includes("==") || selected.includes("~~")) return;
    const before = value.slice(0, selectionStart);
    const after = value.slice(selectionEnd);
    updateUsage(usageIndex, { [field]: `${before}==${selected}==${after}` });
  }

  function markSelectionAsHighlight(
    usageIndex: number,
    exampleIndex: number,
    input: HTMLTextAreaElement,
    existing: string[],
  ) {
    const { selectionStart, selectionEnd, value } = input;
    if (selectionStart == null || selectionEnd == null || selectionStart === selectionEnd) return;
    const text = value.slice(selectionStart, selectionEnd).trim();
    if (!text) return;
    updateExample(usageIndex, exampleIndex, { highlights: [...existing, text] });
  }

  function removeHighlight(
    usageIndex: number,
    exampleIndex: number,
    existing: string[],
    markIndex: number,
  ) {
    updateExample(usageIndex, exampleIndex, {
      highlights: existing.filter((_, i) => i !== markIndex),
    });
  }

  function updateExample(
    usageIndex: number,
    exampleIndex: number,
    patch: Partial<ExampleSentence>,
  ) {
    setDraft((prev) => ({
      ...prev,
      usages: prev.usages.map((usage, i) => {
        if (i !== usageIndex) return usage;
        return {
          ...usage,
          example_sentences: usage.example_sentences.map((ex, j) =>
            j === exampleIndex ? { ...ex, ...patch } : ex,
          ),
        };
      }),
    }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLocalError("");
    if (!draft.grammar_point.trim()) {
      setLocalError("請填寫文法標題");
      return;
    }
    if (draft.usages.length === 0) {
      setLocalError("至少需要一個用法");
      return;
    }
    try {
      await onSubmit(toPayload(draft));
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "儲存失敗");
    }
  }

  const heading =
    title || (mode === "create" ? "新增文法" : "編輯文法");
  const confirmText = submitLabel || (saving ? "儲存中..." : "儲存");

  return (
    <form
      onSubmit={handleSubmit}
      className={
        embedded
          ? "space-y-5"
          : "space-y-5 rounded-2xl bg-white p-6 ring-1 ring-orange-100"
      }
    >
      {!embedded && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-bold text-[var(--color-primary-dark)]">{heading}</h2>
          <button
            type="button"
            onClick={onCancel}
            className="text-sm text-stone-500 hover:text-stone-800"
          >
            取消
          </button>
        </div>
      )}

      {localError && <p className="text-sm text-red-600">{localError}</p>}

      <label className="block space-y-1">
        <span className="text-xs font-semibold text-stone-500">文法標題</span>
        <textarea
          ref={autoGrow}
          value={draft.grammar_point}
          onChange={(e) => {
            setDraft((prev) => ({ ...prev, grammar_point: e.target.value }));
            autoGrow(e.currentTarget);
          }}
          rows={1}
          className="w-full resize-y rounded-xl border border-orange-100 bg-stone-50 px-3 py-2 text-sm outline-none focus:border-orange-300"
          placeholder="例：〜おきに"
          required
        />
      </label>

      <label className="block space-y-1">
        <span className="text-xs font-semibold text-stone-500">JLPT</span>
        <select
          value={draft.jlpt_level}
          onChange={(e) => setDraft((prev) => ({ ...prev, jlpt_level: e.target.value }))}
          className="w-full rounded-xl border border-orange-100 bg-stone-50 px-3 py-2 text-sm outline-none focus:border-orange-300"
        >
          {JLPT_OPTIONS.map((opt) => (
            <option key={opt} value={opt}>
              {opt === "unknown" ? "待分類" : opt}
            </option>
          ))}
        </select>
      </label>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-bold text-stone-700">用法（{draft.usages.length}）</p>
          <button
            type="button"
            onClick={() =>
              setDraft((prev) => ({ ...prev, usages: [...prev.usages, emptyUsage()] }))
            }
            className="rounded-full bg-orange-50 px-3 py-1 text-xs font-semibold text-orange-700 ring-1 ring-orange-100"
          >
            ＋ 新增用法
          </button>
        </div>

        {draft.usages.map((usage, usageIndex) => (
          <div
            key={usageIndex}
            className="space-y-3 rounded-xl bg-stone-50 p-4 ring-1 ring-stone-200"
          >
            <div className="flex items-center justify-between">
              <p className="text-xs font-bold text-stone-500">用法 {usageIndex + 1}</p>
              {draft.usages.length > 1 && (
                <button
                  type="button"
                  onClick={() =>
                    setDraft((prev) => ({
                      ...prev,
                      usages: prev.usages.filter((_, i) => i !== usageIndex),
                    }))
                  }
                  className="text-xs text-red-600"
                >
                  移除此用法
                </button>
              )}
            </div>

            <label className="block space-y-1">
              <span className="text-xs font-semibold text-stone-500">
                中文語意標題（反白文字可標記重點）
              </span>
              <textarea
                ref={autoGrow}
                value={usage.semantic_concept}
                onChange={(e) => {
                  updateUsage(usageIndex, { semantic_concept: e.target.value });
                  autoGrow(e.currentTarget);
                }}
                onMouseUp={(e) =>
                  wrapSelectionAsMark(usageIndex, "semantic_concept", e.currentTarget)
                }
                onKeyUp={(e) =>
                  wrapSelectionAsMark(usageIndex, "semantic_concept", e.currentTarget)
                }
                rows={1}
                className="w-full resize-y rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm outline-none focus:border-orange-300"
                placeholder="例：表示每隔固定間隔"
              />
            </label>

            <label className="block space-y-1">
              <span className="text-xs font-semibold text-stone-500">
                接續規則（多行可用 Enter；反白文字可標記重點；用 ~~文字~~ 畫刪除線標示排除的用法）
              </span>
              <textarea
                ref={autoGrow}
                value={usage.connection_rule}
                onChange={(e) => {
                  updateUsage(usageIndex, { connection_rule: e.target.value });
                  autoGrow(e.currentTarget);
                }}
                onMouseUp={(e) =>
                  wrapSelectionAsMark(usageIndex, "connection_rule", e.currentTarget)
                }
                onKeyUp={(e) =>
                  wrapSelectionAsMark(usageIndex, "connection_rule", e.currentTarget)
                }
                rows={3}
                className="w-full resize-y rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm outline-none focus:border-orange-300"
                placeholder={"* V 普通形 + かな\n* なA / N + ~~だ~~／である"}
              />
            </label>

            <label className="block space-y-1">
              <span className="text-xs font-semibold text-stone-500">
                中文說明（反白文字可標記重點）
              </span>
              <textarea
                ref={autoGrow}
                value={usage.meaning_zh}
                onChange={(e) => {
                  updateUsage(usageIndex, { meaning_zh: e.target.value });
                  autoGrow(e.currentTarget);
                }}
                onMouseUp={(e) => wrapSelectionAsMark(usageIndex, "meaning_zh", e.currentTarget)}
                onKeyUp={(e) => wrapSelectionAsMark(usageIndex, "meaning_zh", e.currentTarget)}
                rows={2}
                className="w-full resize-y rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm outline-none focus:border-orange-300"
                placeholder="說明這個用法的意思"
              />
            </label>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-stone-500">例句</p>
                <button
                  type="button"
                  onClick={() =>
                    updateUsage(usageIndex, {
                      example_sentences: [...usage.example_sentences, emptyExample()],
                    })
                  }
                  className="text-xs font-semibold text-orange-700"
                >
                  ＋ 例句
                </button>
              </div>
              {usage.example_sentences.map((ex, exIndex) => {
                const marks = ex.highlights ?? [];
                return (
                <div
                  key={exIndex}
                  className="space-y-2 rounded-lg bg-white p-3 ring-1 ring-stone-100"
                >
                  <textarea
                    ref={autoGrow}
                    value={ex.japanese}
                    onChange={(e) => {
                      updateExample(usageIndex, exIndex, { japanese: e.target.value });
                      autoGrow(e.currentTarget);
                    }}
                    onMouseUp={(e) =>
                      markSelectionAsHighlight(usageIndex, exIndex, e.currentTarget, marks)
                    }
                    onKeyUp={(e) =>
                      markSelectionAsHighlight(usageIndex, exIndex, e.currentTarget, marks)
                    }
                    rows={1}
                    className="w-full resize-y rounded-md border border-stone-200 px-2 py-1.5 text-sm"
                    placeholder="日文例句"
                    title="反白選取文法重點的部分，會自動標記（可反白多處）"
                  />
                  <div className="flex flex-wrap items-center gap-1.5 text-xs text-stone-400">
                    <span>反白日文例句中的文字可標記文法重點（可多個）：</span>
                    {marks.length > 0 ? (
                      marks.map((mark, markIndex) => (
                        <span
                          key={markIndex}
                          className="inline-flex items-center gap-1 rounded-full bg-orange-100 px-2 py-0.5 font-semibold text-orange-800"
                        >
                          {mark}
                          <button
                            type="button"
                            onClick={() => removeHighlight(usageIndex, exIndex, marks, markIndex)}
                            className="text-orange-500 hover:text-orange-700"
                            aria-label="清除標記"
                          >
                            ×
                          </button>
                        </span>
                      ))
                    ) : (
                      <span className="italic">尚無標記</span>
                    )}
                  </div>
                  <textarea
                    ref={autoGrow}
                    value={ex.reading || ""}
                    onChange={(e) => {
                      updateExample(usageIndex, exIndex, { reading: e.target.value });
                      autoGrow(e.currentTarget);
                    }}
                    rows={1}
                    className="w-full resize-y rounded-md border border-stone-200 px-2 py-1.5 text-sm"
                    placeholder="讀音（可選）"
                  />
                  <textarea
                    ref={autoGrow}
                    value={ex.chinese || ""}
                    onChange={(e) => {
                      updateExample(usageIndex, exIndex, { chinese: e.target.value });
                      autoGrow(e.currentTarget);
                    }}
                    rows={1}
                    className="w-full resize-y rounded-md border border-stone-200 px-2 py-1.5 text-sm"
                    placeholder="中文翻譯（可選）"
                  />
                  {usage.example_sentences.length > 1 && (
                    <div className="flex items-center justify-end border-t border-stone-100 pt-2">
                      <button
                        type="button"
                        onClick={() =>
                          updateUsage(usageIndex, {
                            example_sentences: usage.example_sentences.filter(
                              (_, i) => i !== exIndex,
                            ),
                          })
                        }
                        className="rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-100"
                      >
                        刪
                      </button>
                    </div>
                  )}
                </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className={`flex flex-wrap gap-3 ${embedded ? "sticky bottom-0 border-t border-stone-100 bg-white pt-4" : ""}`}>
        {embedded ? (
          <>
            <button
              type="button"
              onClick={onCancel}
              disabled={saving}
              className="flex-1 rounded-full bg-stone-100 py-2.5 text-sm font-semibold text-stone-700 disabled:opacity-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 rounded-full bg-[var(--color-primary)] py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {saving ? "套用中..." : confirmText}
            </button>
          </>
        ) : (
          <>
            <button
              type="submit"
              disabled={saving}
              className="rounded-full bg-[var(--color-primary)] px-5 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {saving ? "儲存中..." : confirmText}
            </button>
            <button
              type="button"
              onClick={onCancel}
              className="rounded-full bg-stone-100 px-5 py-2 text-sm font-semibold text-stone-700"
            >
              取消
            </button>
          </>
        )}
      </div>
    </form>
  );
}
