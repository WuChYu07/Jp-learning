import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { fetchWithRetry } from "../lib/apiTransport";

const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";

export type BackendPhase = "idle" | "waking" | "ready" | "failed";

type BackendStatusValue = {
  phase: BackendPhase;
  elapsedSec: number;
  apiConfigured: boolean;
  retry: () => void;
};

const BackendStatusContext = createContext<BackendStatusValue | null>(null);

function isRemoteApi(base: string): boolean {
  return Boolean(base && !base.includes("localhost") && !base.includes("127.0.0.1"));
}

export function BackendStatusProvider({ children }: { children: ReactNode }) {
  const apiConfigured = isRemoteApi(API_BASE);
  const [phase, setPhase] = useState<BackendPhase>(apiConfigured ? "waking" : "idle");
  const [elapsedSec, setElapsedSec] = useState(0);
  const [nonce, setNonce] = useState(0);

  const retry = useCallback(() => {
    if (!apiConfigured) return;
    setPhase("waking");
    setElapsedSec(0);
    setNonce((n) => n + 1);
  }, [apiConfigured]);

  useEffect(() => {
    if (!apiConfigured) return;

    let cancelled = false;
    setPhase("waking");
    setElapsedSec(0);
    const started = Date.now();
    const tick = window.setInterval(() => {
      if (!cancelled) setElapsedSec(Math.floor((Date.now() - started) / 1000));
    }, 400);

    fetchWithRetry(`${API_BASE}/health`)
      .then((res) => {
        if (cancelled) return;
        setPhase(res.ok ? "ready" : "failed");
      })
      .catch(() => {
        if (!cancelled) setPhase("failed");
      })
      .finally(() => {
        window.clearInterval(tick);
      });

    return () => {
      cancelled = true;
      window.clearInterval(tick);
    };
  }, [apiConfigured, nonce]);

  const value = useMemo(
    () => ({ phase, elapsedSec, apiConfigured, retry }),
    [phase, elapsedSec, apiConfigured, retry],
  );

  return (
    <BackendStatusContext.Provider value={value}>{children}</BackendStatusContext.Provider>
  );
}

export function useBackendStatus(): BackendStatusValue {
  const ctx = useContext(BackendStatusContext);
  if (!ctx) {
    return {
      phase: "idle",
      elapsedSec: 0,
      apiConfigured: false,
      retry: () => undefined,
    };
  }
  return ctx;
}

/** Loading copy that explains Render cold start when waits get long. */
export function useSlowLoadHint(loading: boolean, slowAfterSec = 2): string | null {
  const { phase, elapsedSec } = useBackendStatus();
  const [localElapsed, setLocalElapsed] = useState(0);

  useEffect(() => {
    if (!loading) {
      setLocalElapsed(0);
      return;
    }
    const started = Date.now();
    const tick = window.setInterval(() => {
      setLocalElapsed(Math.floor((Date.now() - started) / 1000));
    }, 400);
    return () => window.clearInterval(tick);
  }, [loading]);

  if (!loading) return null;
  if (phase === "waking" || localElapsed >= slowAfterSec) {
    const sec = Math.max(elapsedSec, localElapsed);
    return `後端醒來中／載入中（已等 ${sec} 秒，約需 30–60 秒）…`;
  }
  return "載入中...";
}
