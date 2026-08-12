import { Fragment, type ReactNode } from "react";

/** Renders `~~text~~` as struck-through; everything else stays plain text.
 * Lets free-text fields (e.g. connection rules) mark excluded/incorrect forms. */
export function renderStrikethrough(text: string): ReactNode {
  const parts = text.split(/(~~[^~]+~~)/g);
  if (parts.length === 1) return text;
  return parts.map((part, i) => {
    const m = part.match(/^~~([^~]+)~~$/);
    if (m) {
      return (
        <span key={i} className="text-stone-400 line-through">
          {m[1]}
        </span>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}
