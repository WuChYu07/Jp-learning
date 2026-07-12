import { useState, type FormEvent } from "react";
import type { ExampleSentence, Grammar, GrammarWriteInput } from "../lib/api";

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

function emptyUsage(): UsageDraft {
  return {
    semantic_concept: "",
    connection_rule: "",
    meaning_zh: "",
    example_sentences: [{ japanese: "", reading: "", chinese: "" }],
  };
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
                  }))
                : [{ japanese: "", reading: "", chinese: "" }],
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
        <input
          value={draft.grammar_point}
          onChange={(e) => setDraft((prev) => ({ ...prev, grammar_point: e.target.value }))}
          className="w-full rounded-xl border border-orange-100 bg-stone-50 px-3 py-2 text-sm outline-none focus:border-orange-300"
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
              <span className="text-xs font-semibold text-stone-500">中文語意標題</span>
              <input
                value={usage.semantic_concept}
                onChange={(e) => updateUsage(usageIndex, { semantic_concept: e.target.value })}
                className="w-full rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm outline-none focus:border-orange-300"
                placeholder="例：表示每隔固定間隔"
              />
            </label>

            <label className="block space-y-1">
              <span className="text-xs font-semibold text-stone-500">接續規則（多行可用 Enter）</span>
              <textarea
                value={usage.connection_rule}
                onChange={(e) => updateUsage(usageIndex, { connection_rule: e.target.value })}
                rows={3}
                className="w-full rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm outline-none focus:border-orange-300"
                placeholder={"* V 普通形 + かな\n* なA / N + かな"}
              />
            </label>

            <label className="block space-y-1">
              <span className="text-xs font-semibold text-stone-500">中文說明</span>
              <textarea
                value={usage.meaning_zh}
                onChange={(e) => updateUsage(usageIndex, { meaning_zh: e.target.value })}
                rows={2}
                className="w-full rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm outline-none focus:border-orange-300"
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
                      example_sentences: [
                        ...usage.example_sentences,
                        { japanese: "", reading: "", chinese: "" },
                      ],
                    })
                  }
                  className="text-xs font-semibold text-orange-700"
                >
                  ＋ 例句
                </button>
              </div>
              {usage.example_sentences.map((ex, exIndex) => (
                <div
                  key={exIndex}
                  className="space-y-2 rounded-lg bg-white p-3 ring-1 ring-stone-100"
                >
                  <input
                    value={ex.japanese}
                    onChange={(e) =>
                      updateExample(usageIndex, exIndex, { japanese: e.target.value })
                    }
                    className="w-full rounded-md border border-stone-200 px-2 py-1.5 text-sm"
                    placeholder="日文例句"
                  />
                  <input
                    value={ex.reading || ""}
                    onChange={(e) =>
                      updateExample(usageIndex, exIndex, { reading: e.target.value })
                    }
                    className="w-full rounded-md border border-stone-200 px-2 py-1.5 text-sm"
                    placeholder="讀音（可選）"
                  />
                  <div className="flex gap-2">
                    <input
                      value={ex.chinese || ""}
                      onChange={(e) =>
                        updateExample(usageIndex, exIndex, { chinese: e.target.value })
                      }
                      className="w-full rounded-md border border-stone-200 px-2 py-1.5 text-sm"
                      placeholder="中文翻譯（可選）"
                    />
                    {usage.example_sentences.length > 1 && (
                      <button
                        type="button"
                        onClick={() =>
                          updateUsage(usageIndex, {
                            example_sentences: usage.example_sentences.filter(
                              (_, i) => i !== exIndex,
                            ),
                          })
                        }
                        className="shrink-0 text-xs text-red-600"
                      >
                        刪
                      </button>
                    )}
                  </div>
                </div>
              ))}
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
