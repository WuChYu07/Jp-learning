import {
  useCallback,
  useRef,
  useState,
  type PointerEvent,
  type ReactNode,
} from "react";

const SWIPE_THRESHOLD = 88;
const DRAG_START = 12;

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
  const dragged = useRef(false);
  const [dragX, setDragX] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  const progress = Math.min(Math.abs(dragX) / SWIPE_THRESHOLD, 1);
  const swipeEnabled = !disabled;

  const finishDrag = useCallback(() => {
    if (!isDragging) return;
    setIsDragging(false);
    if (!dragged.current) {
      setDragX(0);
      return;
    }
    if (dragX >= SWIPE_THRESHOLD) {
      setDragX(0);
      dragged.current = false;
      onSwipeRight();
      return;
    }
    if (dragX <= -SWIPE_THRESHOLD && onSwipeLeft) {
      setDragX(0);
      dragged.current = false;
      onSwipeLeft();
      return;
    }
    setDragX(0);
    dragged.current = false;
  }, [dragX, isDragging, onSwipeLeft, onSwipeRight]);

  const handlePointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (!swipeEnabled) return;
    startX.current = e.clientX;
    startY.current = e.clientY;
    dragged.current = false;
    setIsDragging(true);
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (!isDragging || !swipeEnabled) return;
    const dx = e.clientX - startX.current;
    const dy = e.clientY - startY.current;
    if (!dragged.current && (Math.abs(dx) > DRAG_START || Math.abs(dy) > DRAG_START)) {
      if (Math.abs(dx) < Math.abs(dy)) {
        // Vertical scroll — abandon horizontal swipe
        setIsDragging(false);
        setDragX(0);
        return;
      }
      dragged.current = true;
    }
    if (dragged.current) setDragX(dx);
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
