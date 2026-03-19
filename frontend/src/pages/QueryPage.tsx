import { useState, useCallback } from "react";
import { api } from "../api/client";
import { useAppContext } from "../context/AppContext.tsx";
import ChatMessageRenderer, { type SandboxResult } from "../components/ChatMessageRenderer.tsx";

type AnalysisMode = "full" | "fast" | "query_only" | "index_only";

const MODES: { value: AnalysisMode; label: string }[] = [
  { value: "full", label: "Full" },
  { value: "fast", label: "Fast" },
  { value: "query_only", label: "Query Only" },
  { value: "index_only", label: "Index Only" },
];

const STAGE_LABELS: Record<string, string> = {
  schema_intelligence: "Schema Intelligence",
  workload_intelligence: "Workload Intelligence",
  query_analysis: "Query Analysis",
  optimizer: "Optimizer",
  index_advisor: "Index Advisor",
  blast_radius: "Blast Radius",
  self_critic: "Self Critic",
  learning_agent: "Learning Agent",
  query: "Query",
  schema_metadata: "Schema Metadata",
};

function extractMarkdown(value: unknown): string | null {
  if (!value || typeof value !== "object") return null;
  const obj = value as Record<string, unknown>;
  if (obj.error) return null;
  if (typeof obj.raw_response === "string") return obj.raw_response;
  return null;
}

function isAgentResult(key: string): boolean {
  return key !== "query" && key !== "schema_metadata" && key !== "engine";
}

export default function QueryPage() {
  const { activeConnectionId } = useAppContext();
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<AnalysisMode>("full");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    run_id?: string;
    mode: string;
    results: Record<string, unknown>;
    timing: Record<string, number>;
  } | null>(null);
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [sandboxResults, setSandboxResults] = useState<Map<string, SandboxResult>>(new Map());
  const [longRunningMessage, setLongRunningMessage] = useState<string | null>(null);

  async function handleRunAnalysis() {
    setError(null);
    setResult(null);
    setActiveTab(null);
    setLoading(true);
    setLongRunningMessage(null);
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
      setLongRunningMessage("Still working… (analysis can take 1–2 minutes; please wait)");
    }, 20000);
    try {
      const data = await api.analyzeQuery(
        { query, mode, connection_id: activeConnectionId ?? undefined },
        controller.signal,
      );
      setResult(data);
      const firstAgent = Object.keys(data.results).find((k) => isAgentResult(k) && extractMarkdown(data.results[k]));
      setActiveTab(firstAgent ?? null);
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        setError("Request was cancelled or timed out.");
      } else {
        setError(e instanceof Error ? e.message : "Analysis failed");
      }
    } finally {
      window.clearTimeout(timeoutId);
      setLongRunningMessage(null);
      setLoading(false);
    }
  }

  const handleRunInSandbox = useCallback(
    async (sql: string) => {
      const key = sql.trim();
      if (!activeConnectionId) {
        setSandboxResults((prev) => new Map(prev).set(key, {
          loading: false,
          error: "Connect to a database first (Connections page or connection bar).",
        }));
        return;
      }
      setSandboxResults((prev) => new Map(prev).set(key, { loading: true }));
      try {
        const res = await api.sandbox({ query: sql, connection_id: activeConnectionId });
        if (!res.success) {
          setSandboxResults((prev) => new Map(prev).set(key, { loading: false, error: res.error || "Query failed" }));
          return;
        }
        setSandboxResults((prev) => new Map(prev).set(key, {
          loading: false,
          rows: res.rows,
          rowCount: res.row_count ?? res.rows?.length ?? 0,
        }));
      } catch (e) {
        setSandboxResults((prev) => new Map(prev).set(key, {
          loading: false,
          error: e instanceof Error ? e.message : "Failed",
        }));
      }
    },
    [activeConnectionId],
  );

  const agentEntries = result
    ? Object.entries(result.results).filter(([k]) => isAgentResult(k))
    : [];

  const totalTime = result?.timing
    ? Object.values(result.timing).reduce((sum, v) => sum + v, 0)
    : 0;

  return (
    <div className="p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-white tracking-tight">Query Analysis</h1>
        <p className="text-sm text-surface-200/60 mt-1">
          Run multi-agent analysis pipelines on your SQL queries
        </p>
      </header>

      <div className="space-y-6 max-w-5xl">
        <div className="card">
          <label className="block text-sm font-medium text-surface-400 mb-2">SQL Query</label>
          <textarea
            className="input-field min-h-[120px] resize-y font-mono text-sm"
            placeholder="SELECT * FROM users WHERE ..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div className="card">
          <label className="block text-sm font-medium text-surface-400 mb-2">Mode</label>
          <div className="flex gap-2">
            {MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                className={
                  mode === m.value ? "btn-primary" : "btn-secondary"
                }
                onClick={() => setMode(m.value)}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <button
            type="button"
            className="btn-primary"
            onClick={handleRunAnalysis}
            disabled={loading || !query.trim()}
          >
            {loading ? "Running..." : "Run Analysis"}
          </button>
        </div>

        {loading && (
          <div className="card flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <div
                className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"
                role="status"
                aria-label="Loading"
              />
              <span className="text-surface-400">
                Running {mode === "full" ? "full pipeline" : mode === "fast" ? "fast" : mode.replace("_", " ")} analysis...
              </span>
            </div>
            {longRunningMessage && (
              <p className="text-sm text-amber-400/90 pl-8">{longRunningMessage}</p>
            )}
          </div>
        )}

        {error && (
          <div className="card border-red-700/50">
            <p className="text-red-400 font-medium">Error</p>
            <p className="text-surface-300 text-sm mt-1">{error}</p>
          </div>
        )}

        {result && !loading && (
          <div className="space-y-4">
            {/* Summary bar */}
            <div className="card">
              <div className="flex flex-wrap items-center gap-2">
                {result.run_id && (
                  <span className="badge-green text-xs">Run: {result.run_id.slice(0, 8)}</span>
                )}
                <span className="badge-yellow text-xs">Mode: {result.mode}</span>
                <span className="badge-green text-xs">
                  Total: {totalTime > 1000 ? `${(totalTime / 1000).toFixed(1)}s` : `${Math.round(totalTime)}ms`}
                </span>
                <span className="text-xs text-surface-200/40 ml-auto">
                  {agentEntries.length} agent{agentEntries.length !== 1 ? "s" : ""} completed
                </span>
              </div>
            </div>

            {/* Tab navigation */}
            <div className="flex gap-1 overflow-x-auto pb-1">
              {agentEntries.map(([key, value]) => {
                const md = extractMarkdown(value);
                const hasError = !!(value && typeof value === "object" && (value as Record<string, unknown>).error);
                const timing = result.timing?.[key];
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setActiveTab(key)}
                    className={`flex items-center gap-2 px-3 py-2 rounded-t-lg text-xs font-medium whitespace-nowrap transition-colors ${
                      activeTab === key
                        ? "bg-surface-800 text-primary-400 border border-surface-700 border-b-surface-800"
                        : hasError
                          ? "bg-surface-900/50 text-red-400/70 hover:text-red-400 hover:bg-surface-800/50"
                          : "bg-surface-900/50 text-surface-300 hover:text-white hover:bg-surface-800/50"
                    }`}
                  >
                    {hasError && (
                      <span className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                    )}
                    {!hasError && md && (
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0" />
                    )}
                    {STAGE_LABELS[key] || key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                    {timing !== undefined && (
                      <span className="text-[10px] text-surface-200/40">
                        {timing > 1000 ? `${(timing / 1000).toFixed(1)}s` : `${Math.round(timing)}ms`}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Active tab content */}
            {activeTab && (() => {
              const value = result.results[activeTab];
              const md = extractMarkdown(value);
              const hasError = !!(value && typeof value === "object" && (value as Record<string, unknown>).error);
              const errorMsg: string | null = hasError ? String((value as Record<string, unknown>).error) : null;

              return (
                <div className="card">
                  <div className="flex items-center gap-3 mb-4 pb-3 border-b border-surface-700/50">
                    <h3 className="text-base font-semibold text-white">
                      {STAGE_LABELS[activeTab] || activeTab.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                    </h3>
                    {result.timing?.[activeTab] !== undefined && (
                      <span className="badge-green text-xs">
                        {result.timing[activeTab] > 1000
                          ? `${(result.timing[activeTab] / 1000).toFixed(1)}s`
                          : `${Math.round(result.timing[activeTab])}ms`}
                      </span>
                    )}
                  </div>

                  {hasError && (
                    <div className="rounded-lg bg-red-900/20 border border-red-700/30 px-4 py-3">
                      <p className="text-red-400 text-sm font-medium">Agent Failed</p>
                      <p className="text-red-300/70 text-sm mt-1">{errorMsg}</p>
                    </div>
                  )}

                  {md && (
                    <ChatMessageRenderer
                      content={md}
                      onRunInSandbox={handleRunInSandbox}
                      sandboxResults={sandboxResults}
                    />
                  )}

                  {!md && !hasError && (
                    <p className="text-surface-400 text-sm italic">No output from this agent.</p>
                  )}
                </div>
              );
            })()}
          </div>
        )}
      </div>
    </div>
  );
}
