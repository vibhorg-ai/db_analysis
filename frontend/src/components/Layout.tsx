import { NavLink, Outlet, useLocation } from "react-router-dom";
import ChatWidget from "./ChatWidget.tsx";
import { useAppContext } from "../context/AppContext.tsx";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" },
  { to: "/query", label: "Query Analysis", icon: "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" },
  { to: "/health", label: "DB Health", icon: "M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" },
  { to: "/issues", label: "Issues", icon: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" },
  { to: "/chat", label: "Chatbot", icon: "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" },
  { to: "/sandbox", label: "Sandbox", icon: "M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" },
  { to: "/graph", label: "Knowledge Graph", icon: "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" },
  { to: "/insights", label: "Insights", icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" },
  { to: "/simulation", label: "Simulation", icon: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" },
  { to: "/connections", label: "Connections", icon: "M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" },
];

function SvgIcon({ d }: { d: string }) {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d={d} />
    </svg>
  );
}

function getStatusColor(score: number | undefined): string {
  if (score === undefined) return "bg-surface-500";
  if (score > 80) return "bg-green-500";
  if (score >= 50) return "bg-yellow-500";
  return "bg-red-500";
}

function getEngineBadge(engine: string): string {
  const e = engine.toLowerCase();
  if (e === "postgres" || e === "postgresql") return "PG";
  if (e === "couchbase") return "CB";
  return engine.substring(0, 2).toUpperCase();
}

function ConnectionStatusBar() {
  const { connections, healthMap, activeConnectionId, setActiveConnectionId } = useAppContext();

  if (connections.length === 0) return null;

  return (
    <div className="flex items-center gap-2 px-4 py-1.5 bg-surface-900/80 border-b border-surface-700/60 overflow-x-auto">
      <span className="text-[10px] text-surface-200/40 uppercase tracking-widest font-medium shrink-0">
        Connections
      </span>
      {connections.map((c) => {
        const health = healthMap[c.id];
        const isActive = activeConnectionId === c.id;
        const isConnected = !!c.connected;
        return (
          <button
            key={c.id}
            type="button"
            onClick={() => setActiveConnectionId(c.id)}
            aria-label={`Select connection ${c.name}`}
            aria-pressed={isActive}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition-colors ${
              isActive
                ? "bg-primary-500/15 border border-primary-500/30 text-primary-300"
                : isConnected
                  ? "bg-surface-800/50 border border-surface-700/40 text-surface-300 hover:bg-surface-800 hover:text-white"
                  : "bg-surface-900/30 border border-surface-800/30 text-surface-500"
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${isConnected ? getStatusColor(health?.score) : "bg-surface-600"} shrink-0`} />
            <span className="font-medium truncate max-w-[120px]">{c.name}</span>
            <span className="text-[9px] text-surface-200/40 font-mono">{getEngineBadge(c.engine)}</span>
            {health && isConnected && (
              <span className="text-[9px] text-surface-200/50 font-mono">{health.score}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export default function Layout() {
  const { pathname } = useLocation();
  const onChatPage = pathname === "/chat";

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 bg-surface-900 border-r border-surface-700 flex flex-col">
        <div className="h-14 flex items-center px-5 border-b border-surface-700">
          <span className="text-lg font-bold text-primary-400 tracking-tight">DB Analyzer</span>
          <span className="ml-1.5 text-xs text-surface-200/60 font-medium mt-0.5">v5</span>
        </div>
        <nav className="flex-1 py-3 overflow-y-auto" role="navigation" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
                  isActive
                    ? "text-primary-400 bg-primary-500/10 border-r-2 border-primary-400"
                    : "text-surface-200 hover:text-white hover:bg-surface-800"
                }`
              }
            >
              <SvgIcon d={item.icon} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-surface-700 text-xs text-surface-200/50">
          DB Analyzer AI &copy; 2026
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden min-h-0">
        <ConnectionStatusBar />
        <main className="flex-1 overflow-y-auto bg-surface-950 min-h-0 min-w-0">
          <Outlet />
        </main>
      </div>

      {!onChatPage && <ChatWidget />}
    </div>
  );
}
