/** Shared fetch with Render cold-start retries and user-facing errors. */

export class ApiWakeError extends Error {
  constructor(
    message = "後端正在醒來（Render 免費版約需 30–60 秒），請稍候再試。",
  ) {
    super(message);
    this.name = "ApiWakeError";
  }
}

const WAKE_STATUS = new Set([502, 503, 504, 524]);
const MAX_ATTEMPTS = 3;
const TIMEOUT_MS = 45_000;
const RETRY_DELAY_MS = 2_000;

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isRetriableNetworkError(err: unknown): boolean {
  if (err instanceof TypeError) return true;
  if (err instanceof DOMException && err.name === "AbortError") return true;
  return false;
}

export function formatApiError(body: string, statusText: string): string {
  try {
    const parsed = JSON.parse(body) as { detail?: string };
    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }
  } catch {
    // not JSON
  }
  return body || statusText;
}

export function formatUserFacingError(err: unknown): string {
  if (err instanceof ApiWakeError) return err.message;
  if (err instanceof Error) {
    const msg = err.message;
    if (
      msg.includes("Failed to fetch") ||
      msg.includes("NetworkError") ||
      msg.includes("Load failed")
    ) {
      return "無法連線後端。若使用 Render 免費版，可能正在醒來，請等 30–60 秒後重整。";
    }
    return msg;
  }
  return "發生未知錯誤";
}

export async function fetchWithRetry(
  url: string,
  init?: RequestInit,
  opts?: { onRetry?: (attempt: number) => void },
): Promise<Response> {
  let lastError: unknown;

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
      const res = await fetch(url, { ...init, signal: controller.signal });
      clearTimeout(timer);

      if (WAKE_STATUS.has(res.status) && attempt < MAX_ATTEMPTS) {
        opts?.onRetry?.(attempt);
        await sleep(RETRY_DELAY_MS * attempt);
        continue;
      }

      return res;
    } catch (err) {
      clearTimeout(timer);
      lastError = err;

      if (attempt < MAX_ATTEMPTS && isRetriableNetworkError(err)) {
        opts?.onRetry?.(attempt);
        await sleep(RETRY_DELAY_MS * attempt);
        continue;
      }
      break;
    }
  }

  if (isRetriableNetworkError(lastError)) {
    throw new ApiWakeError();
  }

  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}

export async function pingHealth(apiBase: string): Promise<boolean> {
  const base = apiBase.replace(/\/$/, "");
  const res = await fetchWithRetry(`${base}/health`);
  return res.ok;
}
