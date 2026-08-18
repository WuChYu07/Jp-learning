/** Shared "keep failed cards in rotation" logic for the vocab/grammar review
 * flashcard pages. Swiping left ("again") re-inserts the card a few slots
 * later in the current session instead of letting it vanish until the next
 * SRS-scheduled reappearance. */

/** How many cards later a failed card resurfaces within the same batch. */
export const REQUEUE_GAP = 4;

/** Re-insert `cards[index]` a few slots later in the array (used right after
 * a swipe-left/"again" rating, before advancing to the next card). */
export function requeueAfterFail<T>(cards: T[], index: number, gap: number = REQUEUE_GAP): T[] {
  const current = cards[index];
  const rest = cards.filter((_, i) => i !== index);
  const insertAt = Math.min(rest.length, index + gap);
  const next = [...rest];
  next.splice(insertAt, 0, current);
  return next;
}

/** Merge still-unmastered "leech" cards from a prior batch into a freshly
 * fetched one, spreading them out rather than dumping them all up front. */
export function interleaveLeeches<T extends { id: string }>(
  fresh: T[],
  leeches: T[],
  gap: number = REQUEUE_GAP,
): T[] {
  if (leeches.length === 0) return fresh;
  const freshIds = new Set(fresh.map((item) => item.id));
  const result = [...fresh];
  let inserted = 0;
  for (const leech of leeches) {
    if (freshIds.has(leech.id)) continue; // already present from the server's own due pool
    const pos = Math.min(result.length, (inserted + 1) * gap);
    result.splice(pos, 0, leech);
    inserted += 1;
  }
  return result;
}
