import { useState, useEffect } from "react";
import { api } from "../api/client.ts";
import { useAppContext } from "../context/AppContext.tsx";

import type { SimulateRequest, SimulateResponse } from "../api/client.ts";

const CHANGE_TYPES = [
  { value: "add_index", label: "Add Index" },
  { value: "remove_index", label: "Remove Index" },
  { value: "drop_column", label: "Drop Column" },
  { value: "partition_table", label: "Partition Table" },
  { value: "query_comparison", label: "Query Comparison" },
  { value: "growth", label: "Growth" },
  { value: "dependency_impact", label: "Dependency Impact" },
] as const;

type ChangeType = (typeof CHANGE_TYPES)[number]["value"];

function getImpactBadgeClass(level: string): string {
  const v = String(level).toLowerCase();
  if (v === "low") return "badge-green";
  if (v === "medium") return "badge-yellow";
  return "badge-red";
}

function getRiskBadgeClass(level: string): string {
  const v = String(level).toLowerCase();
  if (v === "low") return "badge-green";
  if (v === "medium") return "badge-yellow";
  return "badge-red";
}

const SKIP_DISPLAY_KEYS = new Set([
  "simulation_type",
  "original_plan",
  "optimized_plan",
  "plan",
]);

export default function SimulationPage() {
  const { activeConnectionId, connections, schemaMap, fetchSchemaIfNeeded } = useAppContext();
  const [changeType, setChangeType] = useState<ChangeType>("add_index");
  const [table, setTable] = useState("");
  const [column, setColumn] = useState("");
  const [columns, setColumns] = useState("");
  const [indexName, setIndexName] = useState("");
  const [partitionColumn, setPartitionColumn] = useState("");
  const [targetRows, setTargetRows] = useState<number>(0);
  const [originalQuery, setOriginalQuery] = useState("");
  const [optimizedQuery, setOptimizedQuery] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [history, setHistory] = useState<SimulateResponse[]>([]);

  const hasConnection = connections.length > 0;
  const effectiveConnectionId = activeConnectionId ?? connections[0]?.id ?? null;
  const tables = effectiveConnectionId ? (schemaMap[effectiveConnectionId] ?? []) : [];
  const tableNames = tables.map((t) => t.table_name);

  useEffect(() => {
    if (effectiveConnectionId) {
      fetchSchemaIfNeeded(effectiveConnectionId).catch(() => {});
    }
  }, [effectiveConnectionId, fetchSchemaIfNeeded]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const body: SimulateRequest = {
        change_type: changeType,
        connection_id: effectiveConnectionId ?? undefined,
      };

      switch (changeType) {
        case "add_index":
          body.table = table.trim();
          body.columns = columns
            .split(",")
            .map((c) => c.trim())
            .filter(Boolean);
          if (!body.table || !body.columns?.length) {
            throw new Error("Table and at least one column are required.");
          }
          break;
        case "remove_index":
          body.index_name = indexName.trim();
          if (!body.index_name) throw new Error("Index name is required.");
          break;
        case "drop_column":
          body.table = table.trim();
          body.column = column.trim();
          if (!body.table || !body.column) {
            throw new Error("Table and column are required.");
          }
          break;
        case "partition_table":
          body.table = table.trim();
          body.partition_column = partitionColumn.trim();
          if (!body.table || !body.partition_column) {
            throw new Error("Table and partition column are required.");
          }
          break;
        case "query_comparison":
          body.original_query = originalQuery.trim();
          body.optimized_query = optimizedQuery.trim();
          if (!body.original_query || !body.optimized_query) {
            throw new Error("Both original and optimized queries are required.");
          }
          break;
        case "growth":
          body.table = table.trim();
          body.target_rows = targetRows;
          if (!body.table) throw new Error("Table is required.");
          if (!targetRows || targetRows < 1) {
            throw new Error("Target rows must be a positive number.");
          }
          break;
        case "dependency_impact":
          body.table = table.trim();
          if (!body.table) throw new Error("Table is required.");
          break;
      }

      const resp = await api.simulate(body);
      setResult(resp);
      setHistory((prev) => [resp, ...prev.slice(0, 19)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      setLoading(false);
    }
  }

  const res = result?.result ?? {};
  const impactLevel = (res.impact_level ?? res.impact) as string | undefined;
  const riskLevel = (res.risk_level ?? res.risk) as string | undefined;
  const suggestedSql = (res.suggested_sql ?? res.change) as string | undefined;
  const recommendations = (res.recommendations ?? []) as string[];

  const displayEntries = Object.entries(res).filter(
    ([k]) =>
      !SKIP_DISPLAY_KEYS.has(k) &&
      k !== "impact" &&
      k !== "risk" &&
      k !== "impact_level" &&
      k !== "risk_level" &&
      k !== "change" &&
      k !== "suggested_sql" &&
      k !== "recommendations"
  );

  return (
    <div className="p-8 flex gap-8">
      <div className="flex-1 min-w-0 space-y-6">
        <header>
          <h1 className="text-3xl font-bold text-white tracking-tight">
            Database Simulation
          </h1>
          <p className="text-surface-400 mt-1">
            Run what-if scenarios to predict the impact of schema and query changes.
          </p>
        </header>

        {!hasConnection && (
          <div className="card border-yellow-700/50 bg-yellow-900/10">
            <p className="text-yellow-400 font-medium">No active connection</p>
            <p className="text-surface-300 text-sm mt-1">
              Connect to a database in Connections before running simulations.
            </p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="card">
            <label className="block text-sm font-medium text-surface-400 mb-2">
              Simulation Type
            </label>
            <select
              className="input-field"
              value={changeType}
              onChange={(e) => setChangeType(e.target.value as ChangeType)}
            >
              {CHANGE_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          {/* Dynamic fields */}
          <div className="card space-y-4">
            <h2 className="text-sm font-medium text-surface-400 uppercase tracking-wider">
              Parameters
            </h2>

            <datalist id="sim-table-list">
              {tableNames.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>

            {changeType === "add_index" && (
              <>
                <div>
                  <label className="block text-sm text-surface-500 mb-1">
                    Table name
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="e.g. users"
                    value={table}
                    onChange={(e) => setTable(e.target.value)}
                    list="sim-table-list"
                  />
                </div>
                <div>
                  <label className="block text-sm text-surface-500 mb-1">
                    Columns (comma-separated)
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="e.g. email, created_at"
                    value={columns}
                    onChange={(e) => setColumns(e.target.value)}
                  />
                </div>
              </>
            )}

            {changeType === "remove_index" && (
              <div>
                <label className="block text-sm text-surface-500 mb-1">
                  Index name
                </label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. idx_users_email"
                  value={indexName}
                  onChange={(e) => setIndexName(e.target.value)}
                />
              </div>
            )}

            {changeType === "drop_column" && (
              <>
                <div>
                  <label className="block text-sm text-surface-500 mb-1">
                    Table
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="e.g. users"
                    value={table}
                    onChange={(e) => setTable(e.target.value)}
                    list="sim-table-list"
                  />
                </div>
                <div>
                  <label className="block text-sm text-surface-500 mb-1">
                    Column
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="e.g. deprecated_field"
                    value={column}
                    onChange={(e) => setColumn(e.target.value)}
                  />
                </div>
              </>
            )}

            {changeType === "partition_table" && (
              <>
                <div>
                  <label className="block text-sm text-surface-500 mb-1">
                    Table
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="e.g. orders"
                    value={table}
                    onChange={(e) => setTable(e.target.value)}
                    list="sim-table-list"
                  />
                </div>
                <div>
                  <label className="block text-sm text-surface-500 mb-1">
                    Partition column
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="e.g. created_at"
                    value={partitionColumn}
                    onChange={(e) => setPartitionColumn(e.target.value)}
                  />
                </div>
              </>
            )}

            {changeType === "query_comparison" && (
              <>
                <div>
                  <label className="block text-sm text-surface-500 mb-1">
                    Original query
                  </label>
                  <textarea
                    className="input-field min-h-[100px] resize-y font-mono text-sm"
                    placeholder="SELECT * FROM users WHERE status = 'active'"
                    value={originalQuery}
                    onChange={(e) => setOriginalQuery(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-sm text-surface-500 mb-1">
                    Optimized query
                  </label>
                  <textarea
                    className="input-field min-h-[100px] resize-y font-mono text-sm"
                    placeholder="SELECT * FROM users WHERE status = 'active' AND created_at > NOW() - INTERVAL '30 days'"
                    value={optimizedQuery}
                    onChange={(e) => setOptimizedQuery(e.target.value)}
                  />
                </div>
              </>
            )}

            {changeType === "growth" && (
              <>
                <div>
                  <label className="block text-sm text-surface-500 mb-1">
                    Table
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="e.g. events"
                    value={table}
                    onChange={(e) => setTable(e.target.value)}
                    list="sim-table-list"
                  />
                </div>
                <div>
                  <label className="block text-sm text-surface-500 mb-1">
                    Target rows
                  </label>
                  <input
                    type="number"
                    min={1}
                    className="input-field"
                    placeholder="e.g. 10000000"
                    value={targetRows || ""}
                    onChange={(e) =>
                      setTargetRows(parseInt(e.target.value, 10) || 0)
                    }
                  />
                </div>
              </>
            )}

            {changeType === "dependency_impact" && (
              <div>
                <label className="block text-sm text-surface-500 mb-1">
                  Table
                </label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. users"
                  value={table}
                  onChange={(e) => setTable(e.target.value)}
                  list="sim-table-list"
                />
              </div>
            )}
          </div>

          <div className="flex gap-3">
            <button
              type="submit"
              className="btn-primary"
              disabled={loading || !hasConnection}
            >
              {loading ? "Running..." : "Run Simulation"}
            </button>
            {loading && (
              <div
                className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin self-center"
                role="status"
                aria-label="Loading"
              />
            )}
          </div>
        </form>

        {error && (
          <div className="card border-red-700/50 bg-red-900/10">
            <p className="text-red-400 font-medium">Error</p>
            <p className="text-surface-300 text-sm mt-1">{error}</p>
          </div>
        )}

        {result && !loading && (
          <div className="card space-y-6">
            <h2 className="text-sm font-medium text-surface-400 uppercase tracking-wider">
              Results
            </h2>

            <div className="flex flex-wrap gap-2">
              <span className="text-surface-500 text-sm">
                {result.simulation_type}
              </span>
              <span className="text-surface-400 text-sm">
                — {result.input_description}
              </span>
              {impactLevel && (
                <span className={getImpactBadgeClass(impactLevel)}>
                  Impact: {impactLevel}
                </span>
              )}
              {riskLevel && (
                <span className={getRiskBadgeClass(riskLevel)}>
                  Risk: {riskLevel}
                </span>
              )}
              {result.id && (
                <span className="text-surface-500 text-xs font-mono">
                  {result.id.slice(0, 8)}
                </span>
              )}
            </div>

            {suggestedSql && (
              <div>
                <h3 className="text-sm font-medium text-surface-400 mb-2">
                  Suggested SQL
                </h3>
                <pre className="bg-surface-800 rounded-lg p-4 overflow-x-auto text-sm text-surface-300 font-mono whitespace-pre-wrap border border-surface-700">
                  {suggestedSql}
                </pre>
              </div>
            )}

            {recommendations.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-surface-400 mb-2">
                  Recommendations
                </h3>
                <ul className="list-disc list-inside space-y-1 text-sm text-surface-300">
                  {recommendations.map((rec, i) => (
                    <li key={i}>{String(rec)}</li>
                  ))}
                </ul>
              </div>
            )}

            {displayEntries.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-surface-400 mb-2">
                  Details
                </h3>
                <dl className="space-y-2">
                  {displayEntries.map(([k, v]) => (
                    <div
                      key={k}
                      className="flex justify-between gap-4 text-sm border-b border-surface-800 pb-2 last:border-0"
                    >
                      <dt className="text-surface-400 capitalize">
                        {k.replace(/_/g, " ")}
                      </dt>
                      <dd className="text-white font-medium text-right break-all">
                        {typeof v === "object" && v !== null
                          ? JSON.stringify(v)
                          : String(v ?? "-")}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </div>
        )}

        {!result && !loading && !error && (
          <div className="card border-dashed border-surface-600 text-center py-12">
            <p className="text-surface-500 text-sm">
              Configure parameters above and run a simulation to see results.
            </p>
          </div>
        )}
      </div>

      <aside className="w-72 shrink-0 hidden lg:block">
        <div className="card sticky top-8">
          <h2 className="text-sm font-medium text-surface-400 uppercase tracking-wider mb-4">
            Recent Simulations
          </h2>
          {history.length === 0 ? (
            <p className="text-surface-500 text-sm">No simulations yet</p>
          ) : (
            <ul className="space-y-3 max-h-[400px] overflow-y-auto">
              {history.map((h) => (
                <li key={h.id}>
                  <button
                    type="button"
                    onClick={() => setResult(h)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                      result?.id === h.id
                        ? "bg-primary-500/15 border border-primary-500/30 text-primary-300"
                        : "bg-surface-800/50 border border-surface-700/40 text-surface-300 hover:bg-surface-800 hover:text-white"
                    }`}
                  >
                    <span className="font-medium block truncate">
                      {h.simulation_type}
                    </span>
                    <span className="text-xs text-surface-500 truncate block">
                      {h.input_description}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
}
