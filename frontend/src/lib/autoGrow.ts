/** Resizes a textarea's height to fit its content, so fields with a lot of
 * text expand automatically instead of staying cramped behind a scrollbar.
 * Usable directly as a ref callback (`ref={autoGrow}`, sizes on mount for
 * pre-populated content) or from an onChange/onInput handler
 * (`autoGrow(e.currentTarget)`, resizes as the user types). */
export function autoGrow(el: HTMLTextAreaElement | null): void {
  if (!el) return;
  el.style.height = "auto";
  el.style.height = `${el.scrollHeight}px`;
}
