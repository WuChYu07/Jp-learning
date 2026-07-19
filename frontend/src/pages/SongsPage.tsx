import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  api,
  SongCandidate,
  SongDetail,
  SongHistoryItem,
  SongListItem,
  formatUserFacingError,
} from "../lib/api";

export default function SongsPage() {
  const [query, setQuery] = useState("");
  const [candidates, setCandidates] = useState<SongCandidate[]>([]);
  const [library, setLibrary] = useState<SongListItem[]>([]);
  const [history, setHistory] = useState<SongHistoryItem[]>([]);
  const [song, setSong] = useState<SongDetail | null>(null);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [selecting, setSelecting] = useState(false);
  const [error, setError] = useState("");
  const [showPaste, setShowPaste] = useState(false);
  const [pasteTitle, setPasteTitle] = useState("");
  const [pasteArtist, setPasteArtist] = useState("");
  const [pasteJa, setPasteJa] = useState("");
  const [pasteZh, setPasteZh] = useState("");

  const loadLibrary = useCallback(() => {
    api
      .listSongs(30)
      .then(setLibrary)
      .catch(() => setLibrary([]));
    api
      .songHistory(10)
      .then(setHistory)
      .catch(() => setHistory([]));
  }, []);

  useEffect(() => {
    loadLibrary();
  }, [loadLibrary]);

  async function onSearch(e?: FormEvent) {
    e?.preventDefault();
    if (!query.trim() || loading) return;
    setLoading(true);
    setError("");
    setSong(null);
    try {
      const rows = await api.searchSongs(query.trim());
      setCandidates(rows);
      if (!rows.length) {
        setError("找不到相符歌曲。可改貼 MARUMARU play 網址，或使用下方「貼上歌詞」。");
      }
    } catch (err) {
      setError(formatUserFacingError(err));
      setCandidates([]);
    } finally {
      setLoading(false);
    }
  }

  async function onRecommend() {
    if (loading) return;
    setLoading(true);
    setError("");
    setSong(null);
    try {
      const rows = await api.recommendSongs(12);
      setCandidates(rows);
      if (!rows.length) setError("暫時無法取得推薦，請稍後再試。");
    } catch (err) {
      setError(formatUserFacingError(err));
      setCandidates([]);
    } finally {
      setLoading(false);
    }
  }

  async function onSelectCandidate(c: SongCandidate) {
    if (selecting) return;
    if (c.cached_song_id && c.cached_status === "enriched") {
      setSelecting(true);
      setError("");
      try {
        const detail = await api.getSong(c.cached_song_id);
        setSong(detail);
        setExpanded({});
        loadLibrary();
      } catch (err) {
        setError(formatUserFacingError(err));
      } finally {
        setSelecting(false);
      }
      return;
    }

    setSelecting(true);
    setError("");
    try {
      const detail = await api.selectSong({
        marumaru_id: c.marumaru_id,
        source_url: c.source_url,
        title: c.title,
        artist: c.artist,
        enrich: true,
      });
      setSong(detail);
      setExpanded({});
      loadLibrary();
    } catch (err) {
      setError(formatUserFacingError(err));
      setShowPaste(true);
    } finally {
      setSelecting(false);
    }
  }

  async function openSongById(id: string) {
    if (selecting) return;
    setSelecting(true);
    setError("");
    try {
      const detail = await api.getSong(id);
      setSong(detail);
      setExpanded({});
      loadLibrary();
    } catch (err) {
      setError(formatUserFacingError(err));
    } finally {
      setSelecting(false);
    }
  }

  async function onPasteSubmit(e: FormEvent) {
    e.preventDefault();
    if (!pasteJa.trim() || selecting) return;
    setSelecting(true);
    setError("");
    try {
      const detail = await api.selectSong({
        title: pasteTitle.trim() || "自訂歌詞",
        artist: pasteArtist.trim() || "",
        paste_ja: pasteJa,
        paste_zh: pasteZh.trim() || null,
        enrich: true,
      });
      setSong(detail);
      setExpanded({});
      setShowPaste(false);
      loadLibrary();
    } catch (err) {
      setError(formatUserFacingError(err));
    } finally {
      setSelecting(false);
    }
  }

  function toggleLine(n: number) {
    setExpanded((prev) => ({ ...prev, [n]: !prev[n] }));
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold text-[var(--color-primary-dark)]">
          唱歌學文法
        </h1>
        <p className="max-w-2xl text-sm text-stone-600">
          搜尋日文歌（來源：MARUMARU），取得日中歌詞後由 AI 逐句解釋文法與知識補充。處理過的歌曲會存進曲庫，之後可直接重看。
        </p>
      </header>

      <form onSubmit={onSearch} className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="歌名、歌手，或貼上 MARUMARU play 網址"
          className="min-w-0 flex-1 rounded-2xl border-0 bg-white px-4 py-3 text-sm shadow-sm ring-1 ring-orange-100 placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
        />
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="rounded-full bg-[var(--color-primary)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {loading ? "搜尋中…" : "搜尋"}
          </button>
          <button
            type="button"
            onClick={onRecommend}
            disabled={loading}
            className="rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-[var(--color-primary-dark)] ring-1 ring-orange-200 disabled:opacity-50"
          >
            推薦一首
          </button>
        </div>
      </form>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <button
          type="button"
          onClick={() => setShowPaste((v) => !v)}
          className="text-[var(--color-primary-dark)] underline-offset-2 hover:underline"
        >
          {showPaste ? "收起貼上歌詞" : "找不到？貼上歌詞"}
        </button>
        {selecting && (
          <span className="text-stone-500">正在抓歌詞並請 AI 解釋，可能需要數十秒…</span>
        )}
      </div>

      {showPaste && (
        <form
          onSubmit={onPasteSubmit}
          className="space-y-3 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-orange-100"
        >
          <p className="text-sm font-semibold text-stone-700">貼上歌詞後備</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              value={pasteTitle}
              onChange={(e) => setPasteTitle(e.target.value)}
              placeholder="歌名（選填）"
              className="rounded-xl bg-stone-50 px-3 py-2 text-sm ring-1 ring-stone-200 focus:outline-none focus:ring-[var(--color-primary)]"
            />
            <input
              value={pasteArtist}
              onChange={(e) => setPasteArtist(e.target.value)}
              placeholder="歌手（選填）"
              className="rounded-xl bg-stone-50 px-3 py-2 text-sm ring-1 ring-stone-200 focus:outline-none focus:ring-[var(--color-primary)]"
            />
          </div>
          <textarea
            value={pasteJa}
            onChange={(e) => setPasteJa(e.target.value)}
            rows={6}
            required
            placeholder="日文歌詞（一行一句）"
            className="w-full rounded-xl bg-stone-50 px-3 py-2 text-sm ring-1 ring-stone-200 focus:outline-none focus:ring-[var(--color-primary)]"
          />
          <textarea
            value={pasteZh}
            onChange={(e) => setPasteZh(e.target.value)}
            rows={4}
            placeholder="中文歌詞（選填，一行對一句；空白則由 AI 翻譯）"
            className="w-full rounded-xl bg-stone-50 px-3 py-2 text-sm ring-1 ring-stone-200 focus:outline-none focus:ring-[var(--color-primary)]"
          />
          <button
            type="submit"
            disabled={selecting || !pasteJa.trim()}
            className="rounded-full bg-[var(--color-primary)] px-5 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            分析這首歌
          </button>
        </form>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {candidates.length > 0 && !song && (
        <section className="space-y-3">
          <h2 className="text-sm font-bold text-stone-700">搜尋結果</h2>
          <ul className="grid gap-2 sm:grid-cols-2">
            {candidates.map((c) => (
              <li key={c.marumaru_id}>
                <button
                  type="button"
                  onClick={() => onSelectCandidate(c)}
                  disabled={selecting}
                  className="flex w-full flex-col items-start gap-1 rounded-2xl bg-white px-4 py-3 text-left shadow-sm ring-1 ring-orange-100 transition hover:bg-orange-50/60 disabled:opacity-60"
                >
                  <span className="font-semibold text-stone-800">{c.title}</span>
                  <span className="text-sm text-stone-500">{c.artist || "未知歌手"}</span>
                  <span className="text-xs text-stone-400">
                    {c.release_date || ""}
                    {c.cached_status === "enriched" ? " · 已在曲庫" : ""}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {song && (
        <section className="space-y-4">
          <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-orange-100">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="font-[family-name:var(--font-display)] text-2xl font-bold text-[var(--color-primary-dark)]">
                  {song.title}
                </h2>
                <p className="text-stone-600">{song.artist}</p>
                <p className="mt-1 text-xs text-stone-400">
                  {song.release_date || ""}
                  {song.status ? ` · ${statusLabel(song.status)}` : ""}
                  {song.zh_source ? ` · 中文來源：${song.zh_source}` : ""}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {song.source_url && (
                  <a
                    href={song.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-full bg-orange-50 px-3 py-1.5 text-xs font-semibold text-[var(--color-primary-dark)]"
                  >
                    MARUMARU 來源
                  </a>
                )}
                {song.youtube_url && (
                  <a
                    href={song.youtube_url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-full bg-stone-100 px-3 py-1.5 text-xs font-semibold text-stone-700"
                  >
                    YouTube
                  </a>
                )}
                <button
                  type="button"
                  onClick={() => setSong(null)}
                  className="rounded-full px-3 py-1.5 text-xs text-stone-500 ring-1 ring-stone-200"
                >
                  返回列表
                </button>
              </div>
            </div>
            {song.error_message && (
              <p className="mt-3 text-sm text-red-600">{song.error_message}</p>
            )}
          </div>

          {song.overview_zh && (
            <div className="rounded-2xl bg-orange-50/70 p-5 ring-1 ring-orange-100">
              <p className="mb-2 text-sm font-bold text-[var(--color-primary-dark)]">
                這首歌的背景與解讀
              </p>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-stone-700">
                {song.overview_zh}
              </p>
              <p className="mt-2 text-[11px] text-stone-400">由 AI 產生，僅供學習參考</p>
            </div>
          )}

          <ul className="space-y-2">
            {song.lines.map((ln) => {
              const open = !!expanded[ln.line_no];
              return (
                <li
                  key={ln.line_no}
                  className="rounded-2xl bg-white shadow-sm ring-1 ring-orange-100"
                >
                  <button
                    type="button"
                    onClick={() => toggleLine(ln.line_no)}
                    className="flex w-full items-start gap-3 px-4 py-3 text-left"
                  >
                    <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-orange-50 text-xs font-bold text-[var(--color-primary-dark)]">
                      {ln.line_no}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-stone-800">{ln.text_ja}</p>
                      {ln.text_zh && (
                        <p className="mt-0.5 text-sm text-stone-500">{ln.text_zh}</p>
                      )}
                    </div>
                    <span className="shrink-0 text-xs text-stone-400">{open ? "收合" : "文法"}</span>
                  </button>
                  {open && (
                    <div className="space-y-2 border-t border-orange-50 px-4 py-3 pl-14 text-sm">
                      {ln.grammar_zh ? (
                        <p>
                          <span className="font-semibold text-[var(--color-primary-dark)]">文法：</span>
                          {ln.grammar_zh}
                        </p>
                      ) : (
                        <p className="text-stone-400">尚無文法解釋</p>
                      )}
                      {ln.note_zh && (
                        <p>
                          <span className="font-semibold text-stone-700">補充：</span>
                          {ln.note_zh}
                        </p>
                      )}
                      {!!ln.jlpt_hints?.length && (
                        <p className="text-xs text-stone-500">
                          {ln.jlpt_hints.join(" · ")}
                        </p>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {!song && history.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-bold text-stone-700">最近看過</h2>
          <ul className="divide-y divide-orange-50 overflow-hidden rounded-2xl bg-white ring-1 ring-orange-100">
            {history.map((item) => (
              <li key={item.song_id}>
                <button
                  type="button"
                  onClick={() => openSongById(item.song_id)}
                  disabled={selecting}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-orange-50/50 disabled:opacity-60"
                >
                  <div>
                    <p className="font-semibold text-stone-800">{item.title}</p>
                    <p className="text-sm text-stone-500">
                      {item.artist || "未知歌手"} · {statusLabel(item.status)}
                    </p>
                  </div>
                  <span className="shrink-0 text-xs text-stone-400">
                    {formatRelativeTime(item.last_opened_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!song && library.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-bold text-stone-700">我的曲庫</h2>
          <ul className="divide-y divide-orange-50 overflow-hidden rounded-2xl bg-white ring-1 ring-orange-100">
            {library.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => openSongById(item.id)}
                  disabled={selecting}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-orange-50/50 disabled:opacity-60"
                >
                  <div>
                    <p className="font-semibold text-stone-800">{item.title}</p>
                    <p className="text-sm text-stone-500">
                      {item.artist} · {item.line_count} 句 · {statusLabel(item.status)}
                    </p>
                  </div>
                  <span className="text-xs text-stone-400">開啟</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function formatRelativeTime(iso: string): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffMs = Date.now() - then;
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "剛剛";
  if (minutes < 60) return `${minutes} 分鐘前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小時前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;
  return new Date(iso).toLocaleDateString("zh-TW");
}

function statusLabel(status: string): string {
  switch (status) {
    case "enriched":
      return "已完成解釋";
    case "lyrics_ready":
      return "已抓歌詞";
    case "enriching":
      return "解釋中";
    case "failed":
      return "失敗";
    case "pending":
      return "待處理";
    default:
      return status;
  }
}
