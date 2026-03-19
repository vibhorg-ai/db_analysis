import { useEffect, useState, useCallback } from "react";
import { useAppContext } from "../context/AppContext.tsx";
import { api, type InsightResponse } from "../api/client.ts";
import { wsClient, type WSEvent } from "../api/websocket.ts";

type Category = "all" | "performance" | "schema" | "risk" | "workload";

const CATEGORY_TABS: { value: Category; label: string }[] = [
  { value: "all", label: "All" },
  { value: "performance", label: "Performance" },
  { value: "schema", label: "Schema" },
  { value: "risk", label: "Risk" },
  { value: "workload", label: "Workload" },
];

const POLL_INTERVAL_MS = 60_000;

function getImpactBadgeClass(impact: string): string {
  const i = impact.toLowerCase();
  if (i === "high") return "badge-red";
  if (i === "medium") return "badge-yellow";
  return "badge-green";
}

function getRiskBadgeClass(risk: string): string {
  const r = risk.toLowerCase();
  if (r === "high") return "badge-red";
  if (r === "medium") return "badge-yellow";
  return "badge-green";
}

function formatTimestamp(ts: number): string {
  if (!ts) return "";
  const d = new Date(ts);
  return d.toLocaleString();
}

export default function InsightsPage() {
  const { connections } = useAppContext();
  const [insights, setInsights] = useState<InsightResponse[]>([]);
  const [category, setCategory] = useState<Category>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dismissing, setDismissing] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const loadInsights = useCallback(async () => {
    try {
      setError(null);
      const data = await api.getInsights(category === "all" ? undefined : category);
      setInsights(data.filter((i) => !i.dismissed));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load insights");
      setInsights([]);
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => {
    setLoading(true);
    loadInsights();
  }, [loadInsights]);

  useEffect(() => {
    const interval = setInterval(loadInsights, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [loadInsights]);

  useEffect(() => {
    const unsubscribe = wsClient.subscribe((event: WSEvent) => {
      if (event.type === "advisor_insights") {
        loadInsights();
      }
    });
    return unsubscribe;
  }, [loadInsights]);

  const handleRunAdvisor = useCallback(async () => {
    setRunning(true);
    try {
      await api.runAdvisor();
      await loadInsights();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to run advisor");
    } finally {
      setRunning(false);
    }
  }, [loadInsights]);

  const handleDismiss = useCallback(async (id: string) => {
    setDismissing(id);
    try {
      await api.dismissInsight(id);
      setInsights((prev) => prev.filter((i) => i.id !== id));
    } catch {
      /* ignore */
    } finally {
      setDismissing(null);
    }
  }, []);

  const connectionName = (connId: string) =>
    connections.find((c) => c.id === connId)?.name ?? connId.slice(0, 8);

  const categoryCounts: Record<string, number> = {};
  for (const i of insights) {
    const cat = i.category?.toLowerCase() ?? "other";
    categoryCounts[cat] = (categoryCounts[cat] ?? 0) + 1;
  }

  const filtered =
    category === "all"
      ? insights
      : insights.filter((i) => i.category?.toLowerCase() === category);

  return (
    <div className="p-8">
      <header className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            Autonomous Insights
          </h1>
          <p className="mt-1 text-surface-400">
            AI-powered recommendations from the Autonomous Database Advisor
          </p>
        </div>
        <button
          type="button"
          onClick={handleRunAdvisor}
          disabled={loading || running}
          className="btn-primary shrink-0"
        >
          {running ? "Running…" : "Run Advisor Now"}
        </button>
      </header>

      <div className="flex gap-2 mb-6 overflow-x-auto pb-1">
        {CATEGORY_TABS.map((tab) => {
          const count =
            tab.value === "all"
              ? insights.length
              : (categoryCounts[tab.value] ?? 0);
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

      {loading && insights.length === 0 ? (
        <div className="card flex flex-col items-center justify-center min-h-[200px]">
          <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin mb-3" />
          <p className="text-surface-400">Loading insights…</p>
        </div>
      ) : error && insights.length === 0 ? (
        <div className="card flex flex-col items-center justify-center min-h-[200px] text-center">
          <p className="text-red-400 mb-2">{error}</p>
          <button type="button" onClick={loadInsights} className="btn-secondary">
            Retry
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="card flex flex-col items-center justify-center min-h-[200px] text-center">
          <p className="text-surface-400">
            {category === "all"
              ? "No insights yet. Run the advisor to get recommendations."
              : `No ${category} insights found.`}
          </p>
          {category === "all" && (
            <button
              type="button"
              onClick={handleRunAdvisor}
              disabled={running}
              className="btn-primary mt-3"
            >
              {running ? "Running…" : "Run Advisor Now"}
            </button>
          )}
        </div>
      ) : (
        <ul className="space-y-3">
          {filtered.map((insight) => (
            <li key={insight.id} className="card py-4">
              <div className="flex items-start justify-between gap-4 mb-2">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-bold text-white">
                    {insight.title}
                  </h3>
                  <span className={getImpactBadgeClass(insight.impact)}>
                    {insight.impact}
                  </span>
                  <span className={getRiskBadgeClass(insight.risk)}>
                    {insight.risk}
                  </span>
                  <span className="text-xs text-surface-400">
                    {insight.confidence}% confidence
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleDismiss(insight.id)}
                  disabled={dismissing === insight.id}
                  className="btn-secondary text-sm shrink-0"
                >
                  {dismissing === insight.id ? "…" : "Dismiss"}
                </button>
              </div>
              {insight.description && (
                <p className="text-surface-300 text-sm mb-2">
                  {insight.description}
                </p>
              )}
              {insight.recommendation && (
                <p className="text-surface-300 text-sm mb-2">
                  <span className="text-surface-200 font-medium">
                    Recommendation:
                  </span>{" "}
                  {insight.recommendation}
                </p>
              )}
              {insight.suggested_sql && (
                <pre className="bg-surface-950 border border-surface-700 rounded-lg p-3 text-sm text-surface-200 overflow-x-auto mb-3 font-mono">
                  <code>{insight.suggested_sql}</code>
                </pre>
              )}
              <div className="flex items-center gap-3 text-xs text-surface-500">
                <span>{formatTimestamp(insight.timestamp)}</span>
                {insight.connection_id && (
                  <span>
                    Connection: {connectionName(insight.connection_id)}
                  </span>
                )}
                {insight.source && (
                  <span>Source: {insight.source}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
