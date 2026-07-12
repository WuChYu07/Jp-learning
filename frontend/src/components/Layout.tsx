import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/vocab", label: "Vocabulary", end: false },
  { to: "/grammar", label: "Grammar", end: false },
  { to: "/map", label: "Map", end: false },
  { to: "/quiz", label: "Quiz", end: false },
  { to: "/upload", label: "Upload", end: false },
] as const;

const BOTTOM_NAV = [
  { to: "/", label: "首頁", end: true },
  { to: "/vocab", label: "單字", end: false },
  { to: "/grammar", label: "文法", end: false },
  { to: "/quiz", label: "測驗", end: false },
  { to: "/map", label: "地圖", end: false },
] as const;

function linkClass(isActive: boolean, compact = false) {
  const base = compact
    ? "flex flex-1 flex-col items-center gap-0.5 rounded-xl px-1 py-2 text-[11px] font-medium transition"
    : "rounded-full px-3 py-1.5 text-sm font-medium transition";
  return `${base} ${
    isActive
      ? compact
        ? "bg-orange-50 text-[var(--color-primary)]"
        : "bg-[var(--color-primary)] text-white"
      : compact
        ? "text-stone-500"
        : "text-stone-600 hover:bg-orange-50"
  }`;
}

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-stone-800">
      <header className="sticky top-0 z-40 border-b border-orange-100/80 bg-[var(--color-bg)]/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="min-w-0">
            <p className="font-[family-name:var(--font-display)] text-xl font-bold tracking-tight text-[var(--color-primary-dark)] sm:text-2xl">
              Komorebi
            </p>
            <p className="truncate text-[11px] text-stone-500 sm:text-xs">你的日文學習空間</p>
          </div>

          <nav className="hidden items-center gap-1 md:flex">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => linkClass(isActive)}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <button
            type="button"
            aria-label={menuOpen ? "關閉選單" : "開啟選單"}
            aria-expanded={menuOpen ? "true" : "false"}
            onClick={() => setMenuOpen((v) => !v)}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-[var(--color-primary-dark)] ring-1 ring-orange-100 md:hidden"
          >
            <span className="sr-only">選單</span>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
              {menuOpen ? (
                <path
                  d="M6 6l12 12M18 6L6 18"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              ) : (
                <path
                  d="M4 7h16M4 12h16M4 17h16"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              )}
            </svg>
          </button>
        </div>
      </header>

      {menuOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            type="button"
            aria-label="關閉選單"
            className="absolute inset-0 bg-stone-900/40"
            onClick={() => setMenuOpen(false)}
          />
          <div className="absolute right-0 top-0 flex h-full w-[min(18rem,85vw)] flex-col bg-[var(--color-bg)] shadow-xl">
            <div className="flex items-center justify-between border-b border-orange-100 px-4 py-4">
              <p className="font-[family-name:var(--font-display)] text-lg font-bold text-[var(--color-primary-dark)]">
                選單
              </p>
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                className="rounded-full px-3 py-1.5 text-sm text-stone-600 ring-1 ring-orange-100"
              >
                關閉
              </button>
            </div>
            <nav className="flex flex-col gap-1 p-3">
              {NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `rounded-xl px-4 py-3 text-base font-medium transition ${
                      isActive
                        ? "bg-[var(--color-primary)] text-white"
                        : "text-stone-700 hover:bg-orange-50"
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
        </div>
      )}

      <main className="mx-auto max-w-6xl px-4 py-5 pb-24 sm:px-6 sm:py-8 md:pb-10">
        <Outlet />
      </main>

      <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-orange-100 bg-[var(--color-bg)]/95 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-1 backdrop-blur-md md:hidden">
        <div className="mx-auto flex max-w-lg items-stretch gap-0.5">
          {BOTTOM_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => linkClass(isActive, true)}
            >
              {({ isActive }) => (
                <>
                  <BottomIcon to={item.to} active={isActive} />
                  <span>{item.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}

function BottomIcon({ to, active }: { to: string; active: boolean }) {
  const color = active ? "var(--color-primary)" : "currentColor";
  const common = { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none" as const, "aria-hidden": true };
  if (to === "/") {
    return (
      <svg {...common}>
        <path d="M4 10.5L12 4l8 6.5V20a1 1 0 01-1 1h-5v-6H10v6H5a1 1 0 01-1-1v-9.5z" stroke={color} strokeWidth="1.8" strokeLinejoin="round" />
      </svg>
    );
  }
  if (to === "/vocab") {
    return (
      <svg {...common}>
        <path d="M6 4h9a2 2 0 012 2v14l-4.5-2.5L8 20V6a2 2 0 012-2" stroke={color} strokeWidth="1.8" strokeLinejoin="round" />
        <path d="M10 8h5M10 12h5" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  if (to === "/grammar") {
    return (
      <svg {...common}>
        <path d="M5 6h14M5 12h10M5 18h14" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  if (to === "/quiz") {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="8" stroke={color} strokeWidth="1.8" />
        <path d="M9.5 10a2.5 2.5 0 114 2c-.7.7-1.5 1.2-1.5 2.5M12 17h.01" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <circle cx="12" cy="12" r="3" stroke={color} strokeWidth="1.8" />
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
