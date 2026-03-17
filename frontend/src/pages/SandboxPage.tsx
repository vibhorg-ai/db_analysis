import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import { useAppContext } from "../context/AppContext.tsx";

const HISTORY_KEY = "sandbox_query_history";
const MAX_HISTORY = 20;

interface HistoryEntry {
  query: string;
  timestamp: number;
  rowCount: number;
  success: boolean;
}

function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveHistory(entries: HistoryEntry[]) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, MAX_HISTORY)));
}

export default function SandboxPage() {
  const { connections, activeConnectionId } = useAppContext();
  const [connectionId, setConnectionId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [rowCount, setRowCount] = useState<number | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>(loadHistory);

  const effectiveConnectionId = connectionId ?? activeConnectionId ?? connections[0]?.id ?? null;

  useEffect(() => {
    if (connections.length === 1 && !connectionId) {
      setConnectionId(connections[0].id);
    } else if (!connectionId && activeConnectionId) {
      setConnectionId(activeConnectionId);
    } else if (!connectionId && connections[0]) {
      setConnectionId(connections[0].id);
    }
  }, [connections, activeConnectionId, connectionId]);

  const handleExecute = useCallback(async () => {
    if (!query.trim()) return;
    setError(null);
    setRows([]);
    setRowCount(null);
    setLoading(true);
    try {
      const data = await api.sandbox({ query, connection_id: effectiveConnectionId ?? undefined });
      if (!data.success && data.error) {
        setError(data.error);
        const entry: HistoryEntry = { query, timestamp: Date.now(), rowCount: 0, success: false };
        const updated = [entry, ...history.filter((h) => h.query !== query)].slice(0, MAX_HISTORY);
        setHistory(updated);
        saveHistory(updated);
        return;
      }
      setRows(data.rows);
      setRowCount(data.row_count);
      const entry: HistoryEntry = { query, timestamp: Date.now(), rowCount: data.row_count, success: true };
      const updated = [entry, ...history.filter((h) => h.query !== query)].slice(0, MAX_HISTORY);
      setHistory(updated);
      saveHistory(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Query failed");
    } finally {
      setLoading(false);
    }
  }, [query, history, effectiveConnectionId]);

  const loadFromHistory = (entry: HistoryEntry) => {
    setQuery(entry.query);
  };

  const clearHistory = () => {
    setHistory([]);
    localStorage.removeItem(HISTORY_KEY);
  };

  const columns = rows.length > 0 ? Object.keys(rows[0]) : [];

  return (
    <div className="p-8 flex gap-6">
      <div className="flex-1 min-w-0">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-white tracking-tight">Query Sandbox</h1>
          <p className="mt-1 text-surface-400">Execute read-only queries safely with automatic rollback</p>
          {connections.length > 0 && (
            <div className="mt-4">
              <label htmlFor="sandbox-connection" className="block text-sm font-medium text-surface-400 mb-1">
                Connection
              </label>
              <select
                id="sandbox-connection"
                className="input-field w-auto min-w-[200px]"
                value={effectiveConnectionId ?? ""}
                onChange={(e) => setConnectionId(e.target.value || null)}
              >
                {connections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </header>

        <div className="space-y-6 max-w-5xl">
          <div className="bg-amber-950/30 border border-amber-700/50 rounded-xl p-4">
            <p className="text-amber-200/90 text-sm">
              All queries run in isolated transactions with automatic rollback. Production data is never modified.
            </p>
          </div>

          <div className="card">
            <label className="block text-sm font-medium text-surface-400 mb-2">SQL Query</label>
            <textarea
              className="input-field min-h-[160px] resize-y font-mono text-sm"
              placeholder="SELECT * FROM users LIMIT 10;"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={6}
            />
            <div className="mt-4">
              <button type="button" className="btn-primary" onClick={handleExecute} disabled={loading || !query.trim()}>
                {loading ? "Executing..." : "Execute"}
              </button>
            </div>
          </div>

          {loading && (
            <div className="card flex items-center gap-3">
              <div className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" role="status" aria-label="Loading" />
              <span className="text-surface-400">Running query...</span>
            </div>
          )}

          {error && (
            <div className="card border-red-700/50 bg-red-950/20">
              <p className="text-red-400 font-medium">Error</p>
              <p className="text-surface-300 text-sm mt-1">{error}</p>
            </div>
          )}

          {rowCount !== null && !loading && (
            <div className="card">
              <p className="text-sm font-medium text-surface-400 mb-3">
                {rowCount} row{rowCount !== 1 ? "s" : ""}
              </p>
              <div className="overflow-x-auto rounded-lg border border-surface-700">
                <table className="min-w-full text-sm text-left text-surface-300">
                  <thead className="bg-surface-800 text-surface-400">
                    <tr>
                      {columns.map((col) => (
                        <th key={col} className="px-4 py-3 font-medium whitespace-nowrap">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, i) => (
                      <tr key={i} className="border-t border-surface-700 bg-surface-900/50 hover:bg-surface-800/50">
                        {columns.map((col) => (
                          <td key={col} className="px-4 py-2 whitespace-nowrap max-w-[200px] truncate" title={String(row[col] ?? "")}>
                            {row[col] == null ? "NULL" : String(row[col])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="w-72 shrink-0">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-medium text-surface-400 uppercase tracking-wider">Recent Queries</h2>
          {history.length > 0 && (
            <button type="button" onClick={clearHistory} className="text-[10px] text-surface-200/40 hover:text-red-400 transition-colors">
              Clear
            </button>
          )}
        </div>
        {history.length === 0 ? (
          <div className="card">
            <p className="text-surface-500 text-sm">No query history yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {history.map((entry, i) => (
              <button
                key={i}
                type="button"
                onClick={() => loadFromHistory(entry)}
                className="w-full text-left card py-3 px-4 hover:bg-surface-800/80 transition-colors cursor-pointer"
              >
                <p className="text-xs font-mono text-surface-200 truncate mb-1">{entry.query}</p>
                <div className="flex items-center gap-2 text-[10px] text-surface-500">
                  <span className={entry.success ? "text-green-500" : "text-red-500"}>
                    {entry.success ? `${entry.rowCount} rows` : "failed"}
                  </span>
                  <span>{new Date(entry.timestamp).toLocaleTimeString()}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
