import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, DashboardStats } from "../lib/api";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .dashboardStats()
      .then(setStats)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="space-y-8">
      {/* Hero */}
      <section className="rounded-2xl bg-[var(--color-surface)] p-8 shadow-sm">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold text-[var(--color-primary-dark)]">
          歡迎回來
        </h1>
        <p className="mt-2 text-stone-600">今天也一起保持初心，穩步學習吧。</p>
        {error && <p className="mt-4 text-red-600">{error}</p>}
      </section>

      {/* Stats grid */}
      {stats && (
        <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard
            label="待複習"
            value={stats.vocab_due_count}
            accent="text-[var(--color-primary)]"
          />
          <StatCard
            label="複習總分"
            value={stats.review_points}
            accent="text-[var(--color-primary)]"
          />
          <StatCard
            label="平均熟練度"
            value={Math.round(stats.review_score_avg)}
            accent="text-emerald-600"
          />
          <StatCard
            label="連續天數"
            value={stats.streak_days}
            accent="text-emerald-600"
          />
        </section>
      )}

      {stats && (
        <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard
            label="單字總數"
            value={stats.vocab_total}
            accent="text-[var(--color-primary-dark)]"
          />
          <StatCard
            label="文法總數"
            value={stats.grammar_total}
            accent="text-[var(--color-primary-dark)]"
          />
          <StatCard
            label="單字考試均分"
            value={
              stats.exam_vocab_avg != null
                ? Math.round(stats.exam_vocab_avg)
                : "—"
            }
            accent="text-sky-700"
            suffix={stats.exam_vocab_count ? `% · ${stats.exam_vocab_count} 次` : undefined}
          />
          <StatCard
            label="文法考試均分"
            value={
              stats.exam_grammar_avg != null
                ? Math.round(stats.exam_grammar_avg)
                : "—"
            }
            accent="text-violet-700"
            suffix={
              stats.exam_grammar_count
                ? `% · ${stats.exam_grammar_count} 次`
                : "尚無紀錄"
            }
          />
        </section>
      )}

      {/* Quick-start progress */}
      {stats && stats.vocab_total > 0 && (
        <section className="rounded-2xl bg-white p-6 ring-1 ring-orange-100">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-stone-700">學習進度</p>
            <p className="text-xs text-stone-400">
              {stats.vocab_total} 單字 · {stats.grammar_total} 文法
            </p>
          </div>
          <div className="mt-3 h-3 w-full overflow-hidden rounded-full bg-stone-100">
            <div
              className="h-full rounded-full bg-gradient-to-r from-orange-300 to-[var(--color-primary)] transition-all"
              style={{
                width: `${Math.min(
                  100,
                  stats.vocab_total > 0
                    ? Math.round(
                        ((stats.vocab_total - stats.vocab_due_count) /
                          stats.vocab_total) *
                          100,
                      )
                    : 0,
                )}%`,
              }}
            />
          </div>
          <p className="mt-1 text-xs text-stone-400">
            已複習{" "}
            {Math.max(0, stats.vocab_total - stats.vocab_due_count)} /{" "}
            {stats.vocab_total} 個單字
          </p>
        </section>
      )}

      {/* Action cards */}
      <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <ActionCard
          title="開始複習"
          description="Anki 風格單字卡，左滑不熟、右滑熟悉。"
          to="/vocab/review"
          cta="前往單字卡"
          emoji="📇"
        />
        <ActionCard
          title="單字庫"
          description="瀏覽全部單字、讀音、釋義與例句。"
          to="/vocab"
          cta="查看單字"
          emoji="📚"
        />
        <ActionCard
          title="文法中心"
          description="瀏覽句型、接續規則與例句。"
          to="/grammar"
          cta="查看文法"
          emoji="📖"
        />
        <ActionCard
          title="測驗"
          description="四選一讀音/意思測驗，或翻譯練習搭配 AI 批改。"
          to="/quiz"
          cta="開始測驗"
          emoji="✏️"
        />
        <ActionCard
          title="上傳資料"
          description="上傳 PDF 或圖片，自動解析單字與文法入庫。"
          to="/upload"
          cta="上傳檔案"
          emoji="📄"
        />
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
  suffix,
}: {
  label: string;
  value: number | string;
  accent: string;
  suffix?: string;
}) {
  return (
    <div className="rounded-xl bg-white p-4 ring-1 ring-orange-100">
      <p className="text-sm text-stone-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accent}`}>{value}</p>
      {suffix && <p className="mt-0.5 text-xs text-stone-400">{suffix}</p>}
    </div>
  );
}

function ActionCard({
  title,
  description,
  to,
  cta,
  emoji,
}: {
  title: string;
  description: string;
  to: string;
  cta: string;
  emoji: string;
}) {
  return (
    <div className="rounded-2xl bg-white p-6 ring-1 ring-orange-100 transition hover:shadow-md">
      <div className="flex items-center gap-3">
        <span className="text-2xl">{emoji}</span>
        <h2 className="text-lg font-semibold">{title}</h2>
      </div>
      <p className="mt-2 text-sm text-stone-600">{description}</p>
      <Link
        to={to}
        className="mt-4 inline-block rounded-full bg-[var(--color-secondary)] px-5 py-2 text-sm font-semibold text-white transition hover:opacity-90"
      >
        {cta}
      </Link>
    </div>
  );
}
