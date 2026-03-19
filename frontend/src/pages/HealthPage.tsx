import { useEffect, useCallback } from "react";
import { useAppContext } from "../context/AppContext.tsx";
import { wsClient, type WSEvent } from "../api/websocket";

const REFRESH_INTERVAL_MS = 30_000;

function getScoreColor(score: number): string {
  if (score > 80) return "border-green-500 text-green-400";
  if (score >= 50) return "border-yellow-500 text-yellow-400";
  return "border-red-500 text-red-400";
}

function getScoreBg(score: number): string {
  if (score > 80) return "bg-green-500/10";
  if (score >= 50) return "bg-yellow-500/10";
  return "bg-red-500/10";
}

function getStatusBadgeClass(status: string): string {
  const s = status.toLowerCase();
  if (s === "healthy") return "badge-green";
  if (s === "degraded") return "badge-yellow";
  return "badge-red";
}

function getAlertClass(message: string): string {
  const m = message.toLowerCase();
  if (m.includes("critical") || m.includes("error")) return "border-red-700/50 bg-red-900/20";
  if (m.includes("warning") || m.includes("degraded")) return "border-yellow-700/50 bg-yellow-900/20";
  return "border-surface-600 bg-surface-800/50";
}

function getEngineBadge(engine: string): string {
  const e = engine.toLowerCase();
  if (e === "postgres" || e === "postgresql") return "PostgreSQL";
  if (e === "couchbase") return "Couchbase";
  return engine;
}

export default function HealthPage() {
  const {
    connections,
    healthMap,
    activeConnectionId,
    setActiveConnectionId,
    setHealthForConnection,
    refreshHealthAll,
  } = useAppContext();

  useEffect(() => {
    refreshHealthAll(true);
    const interval = setInterval(() => refreshHealthAll(true), REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refreshHealthAll]);

  useEffect(() => {
    const unsubscribe = wsClient.subscribe((event: WSEvent) => {
      if (event.type === "health_update" && event.data) {
        const connId = (event.data as Record<string, unknown>).connection_id as string | undefined;
        if (connId) {
          setHealthForConnection(connId, {
            score: (event.data.score as number) ?? 0,
            status: (event.data.status as string) ?? "unknown",
            metrics: (event.data.metrics as Record<string, unknown>[]) ?? [],
            alerts: (event.data.alerts as { message: string }[]) ?? [],
            connection_id: connId,
          });
        }
      }
    });
    return unsubscribe;
  }, [setHealthForConnection]);

  const connIds = Object.keys(healthMap);
  const selectedId = activeConnectionId && healthMap[activeConnectionId] ? activeConnectionId : connIds[0] ?? null;

  if (connIds.length === 0) {
    return (
      <div className="p-8">
        <h1 className="text-2xl font-bold text-white mb-6">Database Health</h1>
        <div className="card">
          <p className="text-surface-400">
            No connection active. Connect to a database in Connections to view health metrics.
          </p>
        </div>
      </div>
    );
  }

  const selectedHealth = selectedId ? healthMap[selectedId] : null;
  const selectedConn = connections.find((c) => c.id === selectedId);
  const score = selectedHealth?.score ?? 0;
  const status = selectedHealth?.status ?? "unknown";
  const metrics = selectedHealth?.metrics ?? [];
  const alerts = selectedHealth?.alerts ?? [];

  return (
    <div className="p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-white tracking-tight">Database Health</h1>
      </header>

      {connIds.length > 1 && (
        <div className="flex gap-2 mb-6 overflow-x-auto">
          {connIds.map((cid) => {
            const h = healthMap[cid];
            const conn = connections.find((c) => c.id === cid);
            const isActive = cid === selectedId;
            return (
              <button
                key={cid}
                type="button"
                onClick={() => setActiveConnectionId(cid)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
                  isActive
                    ? "bg-primary-500/15 border-primary-500/30 text-primary-300"
                    : "bg-surface-800/50 border-surface-700/40 text-surface-300 hover:bg-surface-800 hover:text-white"
                }`}
              >
                <span className={`w-2.5 h-2.5 rounded-full ${h?.score !== undefined ? (h.score > 80 ? "bg-green-500" : h.score >= 50 ? "bg-yellow-500" : "bg-red-500") : "bg-surface-500"}`} />
                <span>{conn?.name ?? cid.slice(0, 8)}</span>
                <span className="text-[10px] text-surface-200/40">{conn ? getEngineBadge(conn.engine) : ""}</span>
                {h && <span className="text-[10px] font-mono text-surface-200/50">{h.score}</span>}
              </button>
            );
          })}
        </div>
      )}

      <div className="flex flex-wrap items-start gap-8 mb-8">
        <div className="flex flex-col items-center gap-4">
          <div className={`w-40 h-40 rounded-full border-4 flex items-center justify-center ${getScoreColor(score)} ${getScoreBg(score)}`}>
            <span className="text-4xl font-bold">{score}</span>
          </div>
          <span className={getStatusBadgeClass(status)}>{status}</span>
          {selectedConn && (
            <span className="text-xs text-surface-400">{selectedConn.name} ({getEngineBadge(selectedConn.engine)})</span>
          )}
        </div>

        <div className="flex-1 min-w-[280px]">
          <h2 className="text-sm font-medium text-surface-400 uppercase tracking-wider mb-4">Metrics</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {metrics.map((metric, i) => (
              <div key={i} className="card py-4">
                <dl className="space-y-1">
                  {Object.entries(metric).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-4 text-sm">
                      <dt className="text-surface-400">{String(k)}</dt>
                      <dd className="text-white font-medium truncate">{v !== null && v !== undefined ? String(v) : "-"}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </div>
          {metrics.length === 0 && <p className="text-surface-500 text-sm">No metrics available</p>}
        </div>
      </div>

      <section>
        <h2 className="text-sm font-medium text-surface-400 uppercase tracking-wider mb-4">Alerts</h2>
        {alerts.length === 0 ? (
          <p className="text-surface-500 text-sm">No alerts</p>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert, i) => (
              <div key={i} className={`card py-3 border ${getAlertClass(alert.message)}`}>
                <p className="text-sm text-white">{alert.message}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
