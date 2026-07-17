import { useBackendStatus } from "../lib/backendStatus";

/** Sticky banner while Render free tier is cold-starting. */
export default function BackendWakeBanner() {
  const { phase, elapsedSec, apiConfigured, retry } = useBackendStatus();
  const isProdHost =
    typeof window !== "undefined" &&
    !window.location.hostname.includes("localhost") &&
    window.location.hostname !== "127.0.0.1";

  // Production deploy missing VITE_API_BASE at build time → show fix hint.
  if (!apiConfigured) {
    if (!isProdHost) return null;
    return (
      <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-sm text-amber-900">
        未設定 <code className="rounded bg-amber-100 px-1">VITE_API_BASE</code>
        ，前端無法連到 Render。請在 Vercel 環境變數設定後 Redeploy。
      </div>
    );
  }

  if (phase === "ready" || phase === "idle") return null;

  return (
    <div
      className={`sticky top-0 z-50 border-b px-4 py-2.5 text-center text-sm shadow-sm ${
        phase === "waking"
          ? "border-amber-300 bg-amber-100 text-amber-950"
          : "border-red-200 bg-red-50 text-red-800"
      }`}
      role="status"
    >
      {phase === "waking" ? (
        <span className="inline-flex flex-wrap items-center justify-center gap-2 font-medium">
          <span
            className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-600"
            aria-hidden
          />
          後端醒來中（Render 免費版約 30–60 秒）· 已等 {elapsedSec} 秒
        </span>
      ) : (
        <span className="inline-flex flex-wrap items-center justify-center gap-2">
          後端暫時連不上，請稍後再試。
          <button
            type="button"
            className="rounded-lg bg-white px-3 py-1 text-xs font-medium shadow-sm ring-1 ring-red-200"
            onClick={retry}
          >
            重試連線
          </button>
        </span>
      )}
    </div>
  );
}
