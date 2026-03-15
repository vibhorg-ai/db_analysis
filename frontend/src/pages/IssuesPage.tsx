import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAppContext, type IssueCategory } from "../context/AppContext.tsx";
import { wsClient, type WSEvent } from "../api/websocket";

type Severity = "critical" | "high" | "warning" | "info";
type Category = "all" | "performance" | "locks" | "schema" | "configuration" | "maintenance" | "security" | "other";

const SEVERITY_ORDER: Record<string, number> = { critical: 0, high: 1, warning: 2, info: 3 };
const POLL_INTERVAL_MS = 60_000;

function getSeverityBadgeClass(severity: string): string {
  switch (severity) {
    case "critical": return "badge-red";
    case "high": return "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-900/50 text-orange-400 border border-orange-700/50";
    case "warning": return "badge-yellow";
    default: return "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-900/50 text-blue-400 border border-blue-700/50";
  }
}

function getCategoryColor(cat: string): string {
  const colors: Record<string, string> = {
    performance: "text-amber-400",
    locks: "text-red-400",
    schema: "text-purple-400",
    configuration: "text-cyan-400",
    maintenance: "text-emerald-400",
    security: "text-rose-400",
    other: "text-surface-400",
  };
  return colors[cat] ?? "text-surface-400";
}

const CATEGORY_TABS: { value: Category; label: string }[] = [
  { value: "all", label: "All" },
  { value: "performance", label: "Performance" },
  { value: "locks", label: "Locks" },
  { value: "schema", label: "Schema" },
  { value: "configuration", label: "Configuration" },
  { value: "maintenance", label: "Maintenance" },
  { value: "security", label: "Security" },
  { value: "other", label: "Other" },
];

export default function IssuesPage() {
  const { issues, addIssues, resolveIssue: resolveInCtx, refreshIssues, connections } = useAppContext();
  const navigate = useNavigate();
  const [category, setCategory] = useState<Category>("all");
  const [resolving, setResolving] = useState<string | null>(null);

  useEffect(() => {
    refreshIssues();
  }, [refreshIssues]);

  useEffect(() => {
    const interval = setInterval(() => refreshIssues(), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refreshIssues]);

  useEffect(() => {
    const unsubscribe = wsClient.subscribe((event: WSEvent) => {
      if (event.type === "issue_new" && event.data) {
        const d = event.data as Record<string, unknown>;
        addIssues([{
          id: String(d.id ?? `ws-${Date.now()}`),
          title: String(d.title ?? "Issue"),
          description: String(d.description ?? ""),
          severity: (String(d.severity ?? "info")) as Severity,
          category: (String(d.category ?? "other")) as IssueCategory,
          timestamp: String(d.timestamp ?? event.timestamp),
          source: String(d.source ?? ""),
          resolved: false,
          connection_id: String(d.connection_id ?? ""),
        }]);
      }
      if (event.type === "monitoring_run_complete" && event.data) {
        refreshIssues();
      }
    });
    return unsubscribe;
  }, [addIssues, refreshIssues]);

  const handleResolve = useCallback(async (issueId: string) => {
    setResolving(issueId);
    try {
      await api.resolveIssue(issueId);
      resolveInCtx(issueId);
    } catch {
      /* ignore */
    } finally {
      setResolving(null);
    }
  }, [resolveInCtx]);

  const handleFix = useCallback((issue: { title: string; description: string }) => {
    const msg = `Fix this issue: ${issue.title} — ${issue.description}. Provide the exact SQL commands needed.`;
    navigate(`/chat?prefill=${encodeURIComponent(msg)}`);
  }, [navigate]);

  const openIssues = issues.filter((i) => !i.resolved);
  const filtered = category === "all" ? openIssues : openIssues.filter((i) => i.category === category);
  const sorted = [...filtered].sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9));

  const categoryCounts: Record<string, number> = {};
  for (const i of openIssues) {
    categoryCounts[i.category] = (categoryCounts[i.category] ?? 0) + 1;
  }

  return (
    <div className="p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-white tracking-tight">Issues</h1>
        <p className="mt-1 text-surface-400">
          {openIssues.length} open issue{openIssues.length !== 1 ? "s" : ""} detected across {connections.length} connection{connections.length !== 1 ? "s" : ""}
        </p>
      </header>

      <div className="flex gap-2 mb-6 overflow-x-auto pb-1">
        {CATEGORY_TABS.map((tab) => {
          const count = tab.value === "all" ? openIssues.length : (categoryCounts[tab.value] ?? 0);
          return (
            <button
              key={tab.value}
              onClick={() => setCategory(tab.value)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors border ${
                category === tab.value
                  ? "bg-primary-500/15 border-primary-500/30 text-primary-300"
                  : "bg-surface-800/50 border-surface-700/40 text-surface-300 hover:bg-surface-800 hover:text-white"
              }`}
            >
              {tab.label}
              {count > 0 && (
                <span className="text-[10px] bg-surface-700/60 text-surface-200/60 rounded-full px-1.5 py-0.5 font-mono">
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {sorted.length === 0 ? (
        <div className="card flex flex-col items-center justify-center min-h-[200px] text-center">
          <p className="text-surface-400">
            {category === "all" ? "No issues detected. System is healthy." : `No ${category} issues found.`}
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {sorted.map((issue) => (
            <li key={issue.id} className="card py-4">
              <div className="flex items-start justify-between gap-4 mb-2">
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-medium text-white">{issue.title}</h3>
                  <span className={getSeverityBadgeClass(issue.severity)}>{issue.severity}</span>
                  <span className={`text-[10px] font-medium uppercase tracking-wider ${getCategoryColor(issue.category)}`}>
                    {issue.category}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => handleFix(issue)}
                    className="chat-action-btn text-emerald-400 bg-emerald-500/10 border-emerald-500/25 hover:bg-emerald-500/20"
                  >
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Fix
                  </button>
                  <button
                    type="button"
                    onClick={() => handleResolve(issue.id)}
                    disabled={resolving === issue.id}
                    className="chat-action-btn text-surface-300 bg-surface-700/30 border-surface-600/30 hover:bg-surface-700/50"
                  >
                    {resolving === issue.id ? "..." : "Resolve"}
                  </button>
                </div>
              </div>
              {issue.description && (
                <p className="text-surface-300 text-sm mb-2">{issue.description}</p>
              )}
              <div className="flex items-center gap-3 text-xs text-surface-500">
                <span>{issue.timestamp}</span>
                {issue.source && <span>Source: {issue.source}</span>}
                {issue.connection_id && (
                  <span>Connection: {connections.find((c) => c.id === issue.connection_id)?.name ?? issue.connection_id.slice(0, 8)}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
