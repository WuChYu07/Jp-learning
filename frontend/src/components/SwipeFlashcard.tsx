import {
  useCallback,
  useRef,
  useState,
  type PointerEvent,
  type ReactNode,
} from "react";

const SWIPE_THRESHOLD = 88;
const DRAG_START = 10;

type SwipeFlashcardProps = {
  front: ReactNode;
  back: ReactNode;
  flipped: boolean;
  onFlip: () => void;
  onSwipeLeft: () => void;
  onSwipeRight: () => void;
  onRateHard?: () => void;
  onRateEasy?: () => void;
  disabled?: boolean;
};

export default function SwipeFlashcard({
  front,
  back,
  flipped,
  onFlip,
  onSwipeLeft,
  onSwipeRight,
  onRateHard,
  onRateEasy,
  disabled = false,
}: SwipeFlashcardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const startX = useRef(0);
  const startY = useRef(0);
  const dragged = useRef(false);
  const suppressClick = useRef(false);

  const [dragX, setDragX] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [exiting, setExiting] = useState<"left" | "right" | null>(null);

  const progress = Math.min(Math.abs(dragX) / SWIPE_THRESHOLD, 1);
  const rotation = dragX * 0.06;
  const swipeEnabled = !disabled && !exiting;

  const commitSwipe = useCallback((direction: "left" | "right") => {
    suppressClick.current = true;
    setExiting(direction);
  }, []);

  const handleTransitionEnd = () => {
    if (!exiting) return;
    const handler = exiting === "left" ? onSwipeLeft : onSwipeRight;
    setExiting(null);
    setDragX(0);
    handler();
  };

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
      dragged.current = true;
    }
    if (dragged.current) setDragX(dx);
  };

  const finishDrag = () => {
    if (!isDragging) return;
    setIsDragging(false);

    if (!dragged.current) return;

    if (dragX <= -SWIPE_THRESHOLD) {
      commitSwipe("left");
    } else if (dragX >= SWIPE_THRESHOLD) {
      commitSwipe("right");
    } else {
      suppressClick.current = true;
      setDragX(0);
    }
    dragged.current = false;
  };

  const handleClick = () => {
    if (suppressClick.current) {
      suppressClick.current = false;
      return;
    }
    if (exiting || disabled) return;
    onFlip();
  };

  const exitTransform =
    exiting === "right"
      ? "translateX(130%) rotate(28deg) scale(0.92)"
      : exiting === "left"
        ? "translateX(-130%) rotate(-28deg) scale(0.92)"
        : `translateX(${dragX}px) rotate(${rotation}deg)`;

  const leftOpacity = dragX < 0 ? progress : 0;
  const rightOpacity = dragX > 0 ? progress : 0;

  return (
    <div className="swipe-card-stage relative mx-auto w-full max-w-xl select-none touch-none">
      <div
        aria-hidden
        className="swipe-card-shadow absolute inset-x-4 top-3 h-full rounded-3xl bg-orange-100/60"
      />

      <div
        ref={cardRef}
        role="button"
        tabIndex={0}
        onClick={handleClick}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={finishDrag}
        onPointerCancel={finishDrag}
        onTransitionEnd={handleTransitionEnd}
        className={`swipe-card relative w-full cursor-grab rounded-3xl bg-white px-12 py-16 text-center shadow-lg ring-1 ring-orange-100 active:cursor-grabbing ${
          exiting ? "swipe-card-exit" : isDragging ? "" : "swipe-card-spring"
        } ${!exiting ? "swipe-card-ready" : ""}`}
        style={{
          transform: exitTransform,
          opacity: exiting ? 0 : 1,
        }}
      >
        {/* Red overlay when dragging left */}
        <div
          aria-hidden
          className="swipe-overlay swipe-overlay-left pointer-events-none absolute inset-0 rounded-3xl"
          style={{ opacity: leftOpacity }}
        />
        {/* Green overlay when dragging right */}
        <div
          aria-hidden
          className="swipe-overlay swipe-overlay-right pointer-events-none absolute inset-0 rounded-3xl"
          style={{ opacity: rightOpacity }}
        />

        {/* Stamp: 不熟 */}
        <div
          aria-hidden
          className="swipe-stamp pointer-events-none absolute left-6 top-6 rounded-xl border-4 border-red-500 px-3 py-1 text-lg font-bold text-red-500"
          style={{
            opacity: leftOpacity,
            transform: `rotate(-12deg) scale(${0.85 + progress * 0.15})`,
          }}
        >
          不熟
        </div>
        {/* Stamp: 熟悉 */}
        <div
          aria-hidden
          className="swipe-stamp pointer-events-none absolute right-6 top-6 rounded-xl border-4 border-emerald-500 px-3 py-1 text-lg font-bold text-emerald-600"
          style={{
            opacity: rightOpacity,
            transform: `rotate(12deg) scale(${0.85 + progress * 0.15})`,
          }}
        >
          熟悉
        </div>

        {/* Sparkle on right-swipe exit */}
        {exiting === "right" && <div aria-hidden className="swipe-sparkle" />}

        <div className="relative z-10">{!flipped ? front : back}</div>
      </div>

      {!exiting && (
        <>
          <p className="mt-4 text-center text-sm text-stone-400">
            <span className="text-red-400">← 重來</span>
            <span className="mx-3">·</span>
            <span className="text-stone-500">點擊翻面</span>
            <span className="mx-3">·</span>
            <span className="text-emerald-600">良好 →</span>
          </p>
          {flipped && onRateHard && onRateEasy && (
            <div className="mx-auto mt-4 grid max-w-xl grid-cols-2 gap-3">
              <button
                type="button"
                disabled={disabled}
                onClick={onRateHard}
                className="rounded-xl bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800 ring-1 ring-amber-200 disabled:opacity-50"
              >
                有點難 Hard
              </button>
              <button
                type="button"
                disabled={disabled}
                onClick={onRateEasy}
                className="rounded-xl bg-sky-50 px-4 py-3 text-sm font-semibold text-sky-800 ring-1 ring-sky-200 disabled:opacity-50"
              >
                很簡單 Easy
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
