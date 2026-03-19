import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAppContext } from "../context/AppContext.tsx";
import { wsClient, type WSEvent } from "../api/websocket";

export default function DashboardPage() {
  const { connections, healthMap, schemaMap, fetchSchemaIfNeeded, activeConnectionId } = useAppContext();
  const [mcpStatus, setMcpStatus] = useState<{ postgres: unknown; couchbase: unknown } | null>(null);
  const [wsEvents, setWsEvents] = useState<WSEvent[]>([]);

  useEffect(() => {
    api.getMcpStatus().then(setMcpStatus).catch(() => setMcpStatus(null));
  }, []);

  useEffect(() => {
    const unsubscribe = wsClient.subscribe((event) => {
      setWsEvents((prev) => [event, ...prev].slice(0, 10));
    });
    return unsubscribe;
  }, []);

  const effectiveConnId = activeConnectionId ?? connections[0]?.id ?? null;
  useEffect(() => {
    if (effectiveConnId) fetchSchemaIfNeeded(effectiveConnId).catch(() => {});
  }, [effectiveConnId, fetchSchemaIfNeeded]);

  const activeHealth = activeConnectionId ? healthMap[activeConnectionId] : Object.values(healthMap)[0];
  const healthScore = activeHealth?.score ?? null;
  const schemaTablesCount = effectiveConnId ? (schemaMap[effectiveConnId]?.length ?? 0) : 0;

  const mcpLabel =
    mcpStatus !== null
      ? `${Object.keys(mcpStatus.postgres || {}).length > 0 ? "P" : ""}${Object.keys(mcpStatus.couchbase || {}).length > 0 ? "C" : ""}`.replace(/^$/, "N/A")
      : "N/A";

  return (
    <div className="p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-white tracking-tight">DB Analyzer AI v7</h1>
        <p className="mt-1 text-surface-400">Enterprise Database Intelligence Platform</p>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="card">
          <h3 className="text-sm font-medium text-surface-400 uppercase tracking-wider mb-2">
            Health Score
          </h3>
          <p className="text-2xl font-bold text-white">
            {healthScore !== null ? healthScore : "N/A"}
          </p>
        </div>
        <div className="card">
          <h3 className="text-sm font-medium text-surface-400 uppercase tracking-wider mb-2">
            Active Connections
          </h3>
          <p className="text-2xl font-bold text-white">
            {connections.filter((c) => c.connected).length}
          </p>
        </div>
        <div className="card">
          <h3 className="text-sm font-medium text-surface-400 uppercase tracking-wider mb-2">
            Schema Tables
          </h3>
          <p className="text-2xl font-bold text-white">
            {schemaTablesCount}
          </p>
        </div>
        <div className="card">
          <h3 className="text-sm font-medium text-surface-400 uppercase tracking-wider mb-2">
            MCP Status
          </h3>
          <p className="text-2xl font-bold text-white">{mcpLabel}</p>
        </div>
      </div>

      <section>
        <h2 className="text-lg font-semibold text-white mb-4">Recent WebSocket Events</h2>
        <div className="card min-h-[200px]">
          {wsEvents.length === 0 ? (
            <p className="text-surface-500 text-sm">No events yet</p>
          ) : (
            <ul className="space-y-2 font-mono text-sm">
              {wsEvents.map((ev, i) => (
                <li key={i} className="flex gap-3 text-surface-300">
                  <span className="text-surface-500 shrink-0">{ev.timestamp}</span>
                  <span className="text-primary-400">{ev.type}</span>
                  <span className="truncate">
                    {JSON.stringify(ev.data)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
