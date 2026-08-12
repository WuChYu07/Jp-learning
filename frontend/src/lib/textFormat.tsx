import { Fragment, type ReactNode } from "react";

const TOKEN_RE = /(~~[^~]+~~|==[^=]+==)/g;
const MARK_RE = /~~([^~]+)~~|==([^=]+)==/g;

/** Strips `~~`/`==` markup down to the plain inner text (e.g. for truncated labels). */
export function stripFormatting(text: string): string {
  return text.replace(MARK_RE, (_, strike, mark) => strike ?? mark);
}

/** Renders `~~text~~` as struck-through and `==text==` as highlighted;
 * everything else stays plain text. Lets free-text fields (semantic
 * concept, connection rules, meaning) mark excluded forms or key points. */
export function renderFormattedText(text: string): ReactNode {
  const parts = text.split(TOKEN_RE);
  if (parts.length === 1) return text;
  return parts.map((part, i) => {
    const strike = part.match(/^~~([^~]+)~~$/);
    if (strike) {
      return (
        <span key={i} className="text-stone-400 line-through">
          {strike[1]}
        </span>
      );
    }
    const mark = part.match(/^==([^=]+)==$/);
    if (mark) {
      return (
        <mark
          key={i}
          className="rounded px-0.5 bg-orange-200/90 font-bold text-[var(--color-primary-dark)] not-italic"
        >
          {mark[1]}
        </mark>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}
