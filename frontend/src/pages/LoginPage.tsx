/**
 * Login page — kept for future multi-user mode.
 * Route is commented out in App.tsx while AUTH_ENABLED=false.
 */
import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { signIn, signUp, supabaseConfigured } from "../lib/supabase";

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!supabaseConfigured) {
      setError("請在 frontend/.env 設定 VITE_SUPABASE_URL 與 VITE_SUPABASE_ANON_KEY");
      return;
    }
    setLoading(true);
    setError("");
    try {
      if (mode === "login") {
        await signIn(email, password);
      } else {
        await signUp(email, password);
      }
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登入失敗");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-paper)] px-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md rounded-2xl bg-white p-8 shadow-sm ring-1 ring-orange-100"
      >
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold text-[var(--color-primary-dark)]">
          {mode === "login" ? "登入" : "註冊"} Komorebi
        </h1>
        <p className="mt-2 text-sm text-stone-600">登入後可使用 SRS 複習功能。</p>

        <label className="mt-6 block text-sm">
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-lg border border-orange-100 px-3 py-2"
          />
        </label>
        <label className="mt-4 block text-sm">
          密碼
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-lg border border-orange-100 px-3 py-2"
          />
        </label>

        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="mt-6 w-full rounded-full bg-[var(--color-primary)] py-3 font-semibold text-white disabled:opacity-60"
        >
          {loading ? "處理中..." : mode === "login" ? "登入" : "建立帳號"}
        </button>

        <button
          type="button"
          onClick={() => setMode(mode === "login" ? "signup" : "login")}
          className="mt-4 w-full text-sm text-stone-500"
        >
          {mode === "login" ? "還沒有帳號？註冊" : "已有帳號？登入"}
        </button>

        <Link to="/" className="mt-4 block text-center text-sm text-[var(--color-primary)]">
          略過，先瀏覽內容
        </Link>
      </form>
    </div>
  );
}
