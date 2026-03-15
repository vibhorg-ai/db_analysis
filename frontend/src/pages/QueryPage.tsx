import { useState } from "react";
import { api } from "../api/client";

type AnalysisMode = "full" | "query_only" | "index_only";

const MODES: { value: AnalysisMode; label: string }[] = [
  { value: "full", label: "Full" },
  { value: "query_only", label: "Query Only" },
  { value: "index_only", label: "Index Only" },
];

export default function QueryPage() {
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

  async function handleRunAnalysis() {
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const data = await api.analyzeQuery({ query, mode });
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-white tracking-tight">Query Analysis</h1>
      </header>

      <div className="space-y-6 max-w-4xl">
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
            disabled={loading}
          >
            {loading ? "Running..." : "Run Analysis"}
          </button>
        </div>

        {loading && (
          <div className="card flex items-center gap-3">
            <div
              className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"
              role="status"
              aria-label="Loading"
            />
            <span className="text-surface-400">Analyzing query...</span>
          </div>
        )}

        {error && (
          <div className="card border-red-700/50">
            <p className="text-red-400 font-medium">Error</p>
            <p className="text-surface-300 text-sm mt-1">{error}</p>
          </div>
        )}

        {result && !loading && (
          <div className="card space-y-4">
            <div className="flex flex-wrap gap-2">
              {result.run_id && (
                <span className="badge-green">Run ID: {result.run_id}</span>
              )}
              <span className="badge-yellow">Mode: {result.mode}</span>
              {Object.entries(result.timing || {}).map(([k, v]) => (
                <span key={k} className="badge-green">
                  {k}: {v}ms
                </span>
              ))}
            </div>
            <div>
              <h3 className="text-sm font-medium text-surface-400 mb-2">Results</h3>
              <pre className="bg-surface-800 rounded-lg p-4 overflow-x-auto text-sm text-surface-300 font-mono whitespace-pre-wrap">
                {JSON.stringify(result.results, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
