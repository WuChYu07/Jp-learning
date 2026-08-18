import { useState, type FormEvent } from "react";
import type { ExampleSentence, Vocabulary, VocabularyWriteInput } from "../lib/api";
import { autoGrow } from "../lib/autoGrow";
import EditModalShell from "./EditModalShell";

const JLPT_OPTIONS = ["unknown", "N5", "N4", "N3", "N2", "N1"];

const POS_OPTIONS: { value: string; label: string }[] = [
  { value: "other", label: "其他" },
  { value: "noun", label: "名詞" },
  { value: "verb", label: "動詞" },
  { value: "i_adjective", label: "い形容詞" },
  { value: "na_adjective", label: "な形容詞" },
  { value: "adverb", label: "副詞" },
  { value: "particle", label: "助詞" },
  { value: "counter", label: "量詞" },
  { value: "expression", label: "表現" },
];

type Draft = {
  word: string;
  reading: string;
  jlpt_level: string;
  meaning_zh: string;
  part_of_speech: string;
  example_sentences: ExampleSentence[];
  notes_zh: string;
};

function fromVocab(vocab: Vocabulary): Draft {
  const def = vocab.definitions[0];
  return {
    word: vocab.word || "",
    reading: vocab.reading || "",
    jlpt_level: vocab.jlpt_level || "unknown",
    meaning_zh: def?.meaning_zh || "",
    part_of_speech: def?.part_of_speech || "other",
    example_sentences:
      def?.example_sentences && def.example_sentences.length > 0
        ? def.example_sentences.map((ex) => ({
            japanese: ex.japanese || "",
            reading: ex.reading || "",
            chinese: ex.chinese || "",
          }))
        : [{ japanese: "", reading: "", chinese: "" }],
    notes_zh: def?.notes_zh || "",
  };
}

function toPayload(draft: Draft): VocabularyWriteInput {
  return {
    word: draft.word.trim(),
    reading: draft.reading.trim() || undefined,
    jlpt_level: draft.jlpt_level || "unknown",
    meaning_zh: draft.meaning_zh.trim(),
    part_of_speech: draft.part_of_speech || "other",
    example_sentences: draft.example_sentences
      .filter((ex) => ex.japanese.trim())
      .map((ex) => ({
        japanese: ex.japanese.trim(),
        reading: ex.reading?.trim() || undefined,
        chinese: ex.chinese?.trim() || undefined,
      })),
    notes_zh: draft.notes_zh.trim() || undefined,
  };
}

export default function VocabEditModal({
  initial,
  source,
  saving,
  onClose,
  onConfirm,
}: {
  initial: Vocabulary;
  source: "manual" | "ai";
  saving: boolean;
  onClose: () => void;
  onConfirm: (payload: VocabularyWriteInput) => Promise<void>;
}) {
  const [draft, setDraft] = useState<Draft>(() => fromVocab(initial));
  const [localError, setLocalError] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLocalError("");
    if (!draft.word.trim()) {
      setLocalError("請填寫單字");
      return;
    }
    if (!draft.meaning_zh.trim()) {
      setLocalError("請填寫中文意思");
      return;
    }
    try {
      await onConfirm(toPayload(draft));
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "儲存失敗");
    }
  }

  return (
    <EditModalShell
      title={source === "ai" ? "確認 AI 補充" : "編輯單字"}
      subtitle={
        source === "ai"
          ? "可再修改內容，確定後才會寫入筆記"
          : "直接修改後確定套用"
      }
      onClose={onClose}
    >
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        {localError && <p className="text-sm text-red-600">{localError}</p>}

        <label className="block space-y-1">
          <span className="text-xs font-semibold text-stone-500">單字</span>
          <textarea
            ref={autoGrow}
            value={draft.word}
            onChange={(e) => {
              setDraft((p) => ({ ...p, word: e.target.value }));
              autoGrow(e.currentTarget);
            }}
            rows={1}
            className="w-full resize-y rounded-xl border border-orange-100 bg-stone-50 px-3 py-2 text-sm outline-none focus:border-orange-300"
            required
          />
        </label>

        <label className="block space-y-1">
          <span className="text-xs font-semibold text-stone-500">發音</span>
          <textarea
            ref={autoGrow}
            value={draft.reading}
            onChange={(e) => {
              setDraft((p) => ({ ...p, reading: e.target.value }));
              autoGrow(e.currentTarget);
            }}
            rows={1}
            className="w-full resize-y rounded-xl border border-orange-100 bg-stone-50 px-3 py-2 text-sm outline-none focus:border-orange-300"
          />
        </label>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block space-y-1">
            <span className="text-xs font-semibold text-stone-500">JLPT</span>
            <select
              value={draft.jlpt_level}
              onChange={(e) => setDraft((p) => ({ ...p, jlpt_level: e.target.value }))}
              className="w-full rounded-xl border border-orange-100 bg-stone-50 px-3 py-2 text-sm outline-none focus:border-orange-300"
            >
              {JLPT_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt === "unknown" ? "待分類" : opt}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-semibold text-stone-500">詞性</span>
            <select
              value={draft.part_of_speech}
              onChange={(e) => setDraft((p) => ({ ...p, part_of_speech: e.target.value }))}
              className="w-full rounded-xl border border-orange-100 bg-stone-50 px-3 py-2 text-sm outline-none focus:border-orange-300"
            >
              {POS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="block space-y-1">
          <span className="text-xs font-semibold text-stone-500">中文</span>
          <textarea
            ref={autoGrow}
            value={draft.meaning_zh}
            onChange={(e) => {
              setDraft((p) => ({ ...p, meaning_zh: e.target.value }));
              autoGrow(e.currentTarget);
            }}
            rows={4}
            className="w-full resize-y rounded-xl border border-orange-100 bg-stone-50 px-3 py-2 text-sm outline-none focus:border-orange-300"
            required
          />
        </label>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-stone-500">例句</span>
            <button
              type="button"
              onClick={() =>
                setDraft((p) => ({
                  ...p,
                  example_sentences: [
                    ...p.example_sentences,
                    { japanese: "", reading: "", chinese: "" },
                  ],
                }))
              }
              className="rounded-full bg-orange-50 px-3 py-1 text-xs font-semibold text-orange-700"
            >
              ＋ 例句
            </button>
          </div>
          {draft.example_sentences.map((ex, i) => (
            <div key={i} className="space-y-2 rounded-xl bg-stone-50 p-3 ring-1 ring-stone-100">
              <textarea
                ref={autoGrow}
                value={ex.japanese}
                onChange={(e) => {
                  setDraft((p) => ({
                    ...p,
                    example_sentences: p.example_sentences.map((row, j) =>
                      j === i ? { ...row, japanese: e.target.value } : row,
                    ),
                  }));
                  autoGrow(e.currentTarget);
                }}
                rows={1}
                placeholder="日文例句"
                className="w-full resize-y rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-sm outline-none"
              />
              <textarea
                ref={autoGrow}
                value={ex.chinese || ""}
                onChange={(e) => {
                  setDraft((p) => ({
                    ...p,
                    example_sentences: p.example_sentences.map((row, j) =>
                      j === i ? { ...row, chinese: e.target.value } : row,
                    ),
                  }));
                  autoGrow(e.currentTarget);
                }}
                rows={1}
                placeholder="中文翻譯"
                className="w-full resize-y rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-sm outline-none"
              />
              {draft.example_sentences.length > 1 && (
                <button
                  type="button"
                  onClick={() =>
                    setDraft((p) => ({
                      ...p,
                      example_sentences: p.example_sentences.filter((_, j) => j !== i),
                    }))
                  }
                  className="text-xs text-red-600"
                >
                  移除此句
                </button>
              )}
            </div>
          ))}
        </div>

        <label className="block space-y-1">
          <span className="text-xs font-semibold text-stone-500">補充</span>
          <textarea
            ref={autoGrow}
            value={draft.notes_zh}
            onChange={(e) => {
              setDraft((p) => ({ ...p, notes_zh: e.target.value }));
              autoGrow(e.currentTarget);
            }}
            rows={4}
            placeholder="用法、近義差別、助詞搭配…"
            className="w-full resize-y rounded-xl border border-orange-100 bg-stone-50 px-3 py-2 text-sm outline-none focus:border-orange-300"
          />
        </label>

        <div className="sticky bottom-0 flex gap-3 border-t border-stone-100 bg-white pt-4">
          <button
            type="button"
            onClick={onClose}
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
            {saving ? "套用中..." : "確定套用"}
          </button>
        </div>
      </form>
    </EditModalShell>
  );
}
