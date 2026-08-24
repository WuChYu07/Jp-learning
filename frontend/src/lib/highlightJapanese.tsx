import type { ReactNode } from "react";

type HighlightRange = { start: number; end: number };

function addRange(ranges: HighlightRange[], start: number, end: number) {
  const overlaps = ranges.some((r) => start < r.end && end > r.start);
  if (!overlaps) ranges.push({ start, end });
}

/** Finds the first occurrence of `needle` not already claimed by `ranges`,
 * so the same word appearing multiple times can each get its own mark. */
function findNextOccurrence(
  japanese: string,
  needle: string,
  ranges: HighlightRange[],
): HighlightRange | null {
  let from = 0;
  while (from <= japanese.length) {
    const idx = japanese.indexOf(needle, from);
    if (idx < 0) return null;
    const end = idx + needle.length;
    const overlaps = ranges.some((r) => idx < r.end && end > r.start);
    if (!overlaps) return { start: idx, end };
    from = idx + 1;
  }
  return null;
}

/** `explicitMarks` (author-tagged substrings) win when present; otherwise
 * falls back to the first `candidates` entry that appears in `japanese`. */
function findHighlightRanges(
  japanese: string,
  explicitMarks: string[],
  candidates: string[],
): HighlightRange[] {
  const ranges: HighlightRange[] = [];

  for (const mark of explicitMarks) {
    const needle = mark.trim();
    if (!needle) continue;
    const found = findNextOccurrence(japanese, needle, ranges);
    if (found) ranges.push(found);
  }
  if (ranges.length > 0) {
    return ranges.sort((a, b) => a.start - b.start);
  }

  for (const candidate of candidates) {
    const idx = japanese.indexOf(candidate);
    if (idx >= 0) {
      addRange(ranges, idx, idx + candidate.length);
      break;
    }
  }

  return ranges;
}

/** Merge new multi-mark `highlights` with the legacy single `highlight` field. */
export function exampleMarks(example: { highlight?: string; highlights?: string[] }): string[] {
  if (example.highlights?.length) return example.highlights;
  return example.highlight ? [example.highlight] : [];
}

/** Renders `japanese` with `<mark>` around whichever of `explicitMarks` /
 * `candidates` is found first (author tags take priority). */
export function renderHighlightedJapanese(
  japanese: string,
  explicitMarks: string[],
  candidates: string[],
): ReactNode {
  const ranges = findHighlightRanges(japanese, explicitMarks, candidates);
  if (ranges.length === 0) return japanese;

  const nodes: ReactNode[] = [];
  let cursor = 0;
  ranges.forEach((range, i) => {
    if (range.start > cursor) nodes.push(japanese.slice(cursor, range.start));
    nodes.push(
      <mark
        key={i}
        className="rounded px-0.5 bg-orange-200/90 font-bold text-[var(--color-primary-dark)] not-italic"
      >
        {japanese.slice(range.start, range.end)}
      </mark>,
    );
    cursor = range.end;
  });
  if (cursor < japanese.length) nodes.push(japanese.slice(cursor));

  return <>{nodes}</>;
}
