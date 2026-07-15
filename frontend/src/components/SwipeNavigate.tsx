import {
  useCallback,
  useRef,
  useState,
  type PointerEvent,
  type ReactNode,
} from "react";

const SWIPE_THRESHOLD = 88;
const DRAG_START = 12;

const INTERACTIVE_SELECTOR =
  "button, a, input, textarea, select, label, [role='button'], [contenteditable='true']";

type SwipeNavigateProps = {
  children: ReactNode;
  onSwipeRight: () => void;
  onSwipeLeft?: () => void;
  disabled?: boolean;
  hint?: string;
};

/** Horizontal swipe wrapper for vocab detail navigation (right = next). */
export default function SwipeNavigate({
  children,
  onSwipeRight,
  onSwipeLeft,
  disabled = false,
  hint = "右滑或按下方按鈕 → 下一個（低分優先）",
}: SwipeNavigateProps) {
  const startX = useRef(0);
  const startY = useRef(0);
  const activePointerId = useRef<number | null>(null);
  const dragged = useRef(false);
  const dragXRef = useRef(0);
  const [dragX, setDragX] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  const progress = Math.min(Math.abs(dragX) / SWIPE_THRESHOLD, 1);
  const swipeEnabled = !disabled;

  const setOffset = (value: number) => {
    dragXRef.current = value;
    setDragX(value);
  };

  const resetDrag = useCallback(() => {
    activePointerId.current = null;
    dragged.current = false;
    dragXRef.current = 0;
    setIsDragging(false);
    setDragX(0);
  }, []);

  const finishDrag = useCallback(
    (e?: PointerEvent<HTMLDivElement>) => {
      if (activePointerId.current == null) return;
      if (e && e.pointerId !== activePointerId.current) return;

      const dx = dragXRef.current;
      const didDrag = dragged.current;
      if (e?.currentTarget.hasPointerCapture(activePointerId.current)) {
        e.currentTarget.releasePointerCapture(activePointerId.current);
      }
      resetDrag();

      if (!didDrag) return;
      if (dx >= SWIPE_THRESHOLD) {
        onSwipeRight();
        return;
      }
      if (dx <= -SWIPE_THRESHOLD && onSwipeLeft) {
        onSwipeLeft();
      }
    },
    [onSwipeLeft, onSwipeRight, resetDrag],
  );

  const handlePointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (!swipeEnabled) return;
    if (e.button !== 0 && e.pointerType === "mouse") return;
    const target = e.target as HTMLElement | null;
    if (target?.closest(INTERACTIVE_SELECTOR)) return;

    startX.current = e.clientX;
    startY.current = e.clientY;
    activePointerId.current = e.pointerId;
    dragged.current = false;
    setIsDragging(false);
    setOffset(0);
  };

  const handlePointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (!swipeEnabled || activePointerId.current !== e.pointerId) return;
    const dx = e.clientX - startX.current;
    const dy = e.clientY - startY.current;

    if (!dragged.current) {
      if (Math.abs(dx) <= DRAG_START && Math.abs(dy) <= DRAG_START) return;
      // Vertical scroll — abandon horizontal swipe
      if (Math.abs(dx) < Math.abs(dy)) {
        resetDrag();
        return;
      }
      dragged.current = true;
      setIsDragging(true);
      // Capture only after a real horizontal gesture so button clicks still work
      if (!e.currentTarget.hasPointerCapture(e.pointerId)) {
        e.currentTarget.setPointerCapture(e.pointerId);
      }
    }

    setOffset(dx);
  };

  return (
    <div className="space-y-2">
      <div
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={finishDrag}
        onPointerCancel={finishDrag}
        className="touch-pan-y"
        style={{
          transform: dragX ? `translateX(${dragX * 0.35}px)` : undefined,
          transition: isDragging ? "none" : "transform 0.2s ease",
          opacity: 1 - progress * 0.08,
        }}
      >
        {children}
      </div>
      {hint && <p className="text-center text-xs text-stone-400">{hint}</p>}
    </div>
  );
}
