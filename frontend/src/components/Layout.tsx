import { NavLink, Outlet, useLocation } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/vocab", label: "Vocabulary" },
  { to: "/grammar", label: "Grammar" },
  { to: "/map", label: "Map" },
  { to: "/quiz", label: "Quiz" },
  { to: "/upload", label: "Upload" },
];

export default function Layout() {
  const location = useLocation();
  const wide = location.pathname === "/map";

  return (
    <div className="min-h-screen bg-[var(--color-paper)]">
      <header className="border-b border-orange-100 bg-[var(--color-surface)]">
        <div
          className={`mx-auto flex items-center justify-between px-4 py-4 ${
            wide ? "max-w-6xl" : "max-w-4xl"
          }`}
        >
          <div>
            <p className="font-[family-name:var(--font-display)] text-xl font-bold text-[var(--color-primary-dark)]">
              Komorebi
            </p>
            <p className="text-sm text-stone-600">你的日文學習空間</p>
          </div>
          <nav className="flex flex-wrap justify-end gap-2">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === "/"}
                className={({ isActive }) =>
                  `rounded-full px-4 py-2 text-sm font-medium transition ${
                    isActive
                      ? "bg-[var(--color-primary)] text-white"
                      : "text-stone-700 hover:bg-orange-50"
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main
        className={`mx-auto px-4 py-8 ${wide ? "max-w-6xl" : "max-w-4xl"}`}
      >
        <Outlet />
      </main>
    </div>
  );
}
