import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  api,
  DailyReviewCount,
  DashboardStats,
  DashboardTrends,
  JlptMastery,
  formatUserFacingError,
} from "../lib/api";
import { useSlowLoadHint } from "../lib/backendStatus";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [trends, setTrends] = useState<DashboardTrends | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const loadHint = useSlowLoadHint(loading);

  useEffect(() => {
    setLoading(true);
    api
      .dashboardStats()
      .then(setStats)
      .catch((err: unknown) => setError(formatUserFacingError(err)))
      .finally(() => setLoading(false));
    api
      .dashboardTrends(14)
      .then(setTrends)
      .catch(() => setTrends(null));
  }, []);

  return (
    <div className="space-y-8">
      {/* Hero */}
      <section className="rounded-2xl bg-[var(--color-surface)] p-8 shadow-sm">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold text-[var(--color-primary-dark)]">
          歡迎回來
        </h1>
        <p className="mt-2 text-stone-600">今天也一起保持初心，穩步學習吧。</p>
        {loading && !stats && (
          <p className="mt-4 text-sm font-medium text-amber-800">{loadHint}</p>
        )}
        {stats && (
          <div className="mt-5 grid gap-4 sm:grid-cols-[auto_1fr] sm:items-center">
            <div className="rounded-xl bg-orange-50 px-4 py-3 text-center ring-1 ring-orange-100">
              <p className="text-2xl font-bold text-[var(--color-primary)]">
                {stats.streak_days} 天
              </p>
              <p className="text-xs text-stone-500">連續複習</p>
            </div>
            <div>
              <div className="flex justify-between text-sm text-stone-600">
                <span>今日目標</span>
                <span>
                  {stats.reviewed_today ?? 0} / {stats.daily_goal || 20} 張
                </span>
              </div>
              <div className="mt-2 h-3 overflow-hidden rounded-full bg-stone-100">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-orange-300 to-[var(--color-primary)]"
                  style={{
                    width: `${Math.min(
                      100,
                      ((stats.reviewed_today ?? 0) / (stats.daily_goal || 20)) * 100,
                    )}%`,
                  }}
                />
              </div>
            </div>
          </div>
        )}
        {error && <p className="mt-4 text-red-600">{error}</p>}
      </section>

      {/* Stats grid */}
      {stats && (
        <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard
            label="單字待複習"
            value={stats.vocab_due_count}
            accent="text-[var(--color-primary)]"
          />
          <StatCard
            label="文法待複習"
            value={stats.grammar_due_count ?? 0}
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

      {/* Trends */}
      {trends && trends.daily_counts.some((d) => d.count > 0) && (
        <section className="rounded-2xl bg-white p-6 ring-1 ring-orange-100">
          <p className="text-sm font-medium text-stone-700">近 14 天複習量</p>
          <DailyReviewChart data={trends.daily_counts} />
        </section>
      )}

      {trends && (trends.vocab_jlpt.length > 0 || trends.grammar_jlpt.length > 0) && (
        <section className="grid gap-4 md:grid-cols-2">
          {trends.vocab_jlpt.length > 0 && (
            <div className="rounded-2xl bg-white p-6 ring-1 ring-orange-100">
              <p className="text-sm font-medium text-stone-700">單字熟練度（依 JLPT 級別）</p>
              <JlptBreakdownList items={trends.vocab_jlpt} accent="bg-[var(--color-primary)]" />
            </div>
          )}
          {trends.grammar_jlpt.length > 0 && (
            <div className="rounded-2xl bg-white p-6 ring-1 ring-orange-100">
              <p className="text-sm font-medium text-stone-700">文法熟練度（依 JLPT 級別）</p>
              <JlptBreakdownList items={trends.grammar_jlpt} accent="bg-violet-500" />
            </div>
          )}
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
          title="文法卡"
          description="複習文法句型：正面句型、背面意思與接續。"
          to="/grammar/review"
          cta="開始文法卡"
          emoji="🧾"
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
          description="四選一、例句挖空，或翻譯練習搭配 AI 批改。"
          to="/quiz"
          cta="開始測驗"
          emoji="✏️"
        />
        <ActionCard
          title="AI 練習"
          description="日文問答評分，或中文翻譯（附文法／單字提示）。"
          to="/practice"
          cta="開始練習"
          emoji="🗣️"
        />
        <ActionCard
          title="唱歌學文法"
          description="搜尋日文歌，AI 逐句解釋文法、翻譯與文化補充。"
          to="/songs"
          cta="開始聽歌學習"
          emoji="🎵"
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

function DailyReviewChart({ data }: { data: DailyReviewCount[] }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <div className="mt-4 flex h-28 items-end gap-1.5">
      {data.map((d) => {
        const day = new Date(`${d.date}T00:00:00Z`);
        const label = `${day.getUTCMonth() + 1}/${day.getUTCDate()}`;
        return (
          <div key={d.date} className="flex flex-1 flex-col items-center gap-1">
            <div className="flex h-20 w-full items-end">
              <div
                className={`w-full rounded-t-md transition-all ${
                  d.count > 0 ? "bg-[var(--color-primary)]" : "bg-stone-100"
                }`}
                style={{ height: `${Math.max(4, (d.count / max) * 100)}%` }}
                title={`${d.date}：${d.count} 次`}
              />
            </div>
            <p className="text-[10px] text-stone-400">{label}</p>
          </div>
        );
      })}
    </div>
  );
}

function JlptBreakdownList({ items, accent }: { items: JlptMastery[]; accent: string }) {
  return (
    <ul className="mt-4 space-y-2.5">
      {items.map((item) => (
        <li key={item.jlpt_level}>
          <div className="flex items-center justify-between text-xs text-stone-500">
            <span className="font-semibold text-stone-700">{item.jlpt_level}</span>
            <span>
              {Math.round(item.avg_score)} 分 · 已學 {item.reviewed}/{item.total}
            </span>
          </div>
          <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-stone-100">
            <div
              className={`h-full rounded-full ${accent} transition-all`}
              style={{ width: `${Math.min(100, item.avg_score)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
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
