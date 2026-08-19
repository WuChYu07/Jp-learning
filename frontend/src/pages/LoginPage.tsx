/** Site-wide login gate — a single shared password, not per-user accounts.
 * No signup: the only credential that will ever exist is the one set via
 * the backend's ADMIN_PASSWORD_HASH env var. */
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";

export default function LoginPage() {
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const { token } = await api.login(password);
      localStorage.setItem("access_token", token);
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
          Komorebi
        </h1>
        <p className="mt-2 text-sm text-stone-600">請輸入密碼繼續。</p>

        <label className="mt-6 block text-sm">
          密碼
          <input
            type="password"
            required
            autoFocus
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
          {loading ? "登入中..." : "登入"}
        </button>
      </form>
    </div>
  );
}
