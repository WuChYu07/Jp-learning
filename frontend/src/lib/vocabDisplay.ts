/** Display helpers for vocabulary headwords. */

const PLACEHOLDER = /^(?:[-–—－‐]|\s*)$/;

export function hasKanji(text: string): boolean {
  return /[\u4e00-\u9fff]/.test(text);
}

/**
 * When the stored word has no kanji (or is "-"), show reading/kana as the
 * primary headword — without converting script.
 */
export function vocabDisplay(word: string, reading?: string | null): {
  primary: string;
  secondary?: string;
  isKanaOnly: boolean;
} {
  const w = (word || "").trim();
  const r = (reading || "").trim();
  const placeholder = PLACEHOLDER.test(w);
  const kanaOnly = placeholder || !hasKanji(w);

  if (!kanaOnly) {
    return {
      primary: w,
      secondary: r && r !== w ? r : undefined,
      isKanaOnly: false,
    };
  }

  const primary = r || (!placeholder ? w : "") || "—";
  return {
    primary,
    secondary: undefined,
    isKanaOnly: true,
  };
}
