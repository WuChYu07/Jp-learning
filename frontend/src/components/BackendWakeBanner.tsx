import { useEffect, useState } from "react";
import { fetchWithRetry } from "../lib/apiTransport";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";

type WakeState = "hidden" | "waking" | "failed";

/** Shown on production when Render free tier is cold-starting. */
export default function BackendWakeBanner() {
  const [state, setState] = useState<WakeState>("hidden");

  useEffect(() => {
    if (!API_BASE || API_BASE.includes("localhost") || API_BASE.includes("127.0.0.1")) {
      return;
    }

    let cancelled = false;
    setState("waking");

    fetchWithRetry(`${API_BASE}/health`, undefined, {
      onRetry: () => {
        if (!cancelled) setState("waking");
      },
    })
      .then((res) => {
        if (cancelled) return;
        setState(res.ok ? "hidden" : "failed");
      })
      .catch(() => {
        if (!cancelled) setState("failed");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "hidden") return null;

  return (
    <div
      className={`border-b px-4 py-2 text-center text-sm ${
        state === "waking"
          ? "border-amber-200 bg-amber-50 text-amber-900"
          : "border-red-200 bg-red-50 text-red-800"
      }`}
      role="status"
    >
      {state === "waking" ? (
        <span>後端醒來中（Render 免費版約 30–60 秒）…</span>
      ) : (
        <span className="inline-flex flex-wrap items-center justify-center gap-2">
          後端暫時連不上，請稍後再試。
          <button
            type="button"
            className="rounded-lg bg-white px-3 py-1 text-xs font-medium shadow-sm ring-1 ring-red-200"
            onClick={() => window.location.reload()}
          >
            重試
          </button>
        </span>
      )}
    </div>
  );
}
