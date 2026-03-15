import { useState, useCallback } from "react";
import { api } from "../api/client";
import { useAppContext } from "../context/AppContext.tsx";
import type { ConnectRequest } from "../api/client";

type Engine = "postgres" | "couchbase";

interface FormState {
  engine: Engine;
  host: string;
  port: string;
  database: string;
  user: string;
  password: string;
  connection_string: string;
  bucket: string;
  username: string;
}

const INITIAL_FORM: FormState = {
  engine: "postgres",
  host: "",
  port: "5432",
  database: "",
  user: "",
  password: "",
  connection_string: "",
  bucket: "",
  username: "",
};

function getEngineBadgeClass(engine: string): string {
  const e = engine.toLowerCase();
  if (e === "postgres" || e === "postgresql") return "badge-green";
  if (e === "couchbase") return "badge-yellow";
  return "badge-red";
}

export default function ConnectionsPage() {
  const { connections, refreshConnections, refreshHealthAll } = useAppContext();
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);

  const clearFeedback = () => {
    setTimeout(() => setFeedback(null), 4000);
  };

  const handleConnect = useCallback(async (conn: { id: string; engine: string }) => {
    setConnecting(conn.id);
    setFeedback(null);
    try {
      const body: ConnectRequest = { engine: conn.engine, connection_id: conn.id };
      const res = await api.connect(body);
      if (res.success) {
        setFeedback({ type: "success", message: res.message ?? "Connected" });
        clearFeedback();
        await refreshConnections();
        refreshHealthAll().catch(() => {});
      } else {
        setFeedback({ type: "error", message: cleanErrorMessage(res.message ?? "Connection failed") });
        clearFeedback();
      }
    } catch (err) {
      setFeedback({
        type: "error",
        message: cleanErrorMessage(err instanceof Error ? err.message : "Connection failed"),
      });
      clearFeedback();
    } finally {
      setConnecting(null);
    }
  }, [refreshConnections, refreshHealthAll]);

  const handleDisconnect = useCallback(async (id: string) => {
    setDisconnecting(id);
    setFeedback(null);
    try {
      await api.disconnect(id);
      setFeedback({ type: "success", message: "Disconnected" });
      clearFeedback();
      await refreshConnections();
      refreshHealthAll().catch(() => {});
    } catch (err) {
      setFeedback({
        type: "error",
        message: err instanceof Error ? err.message : "Disconnect failed",
      });
      clearFeedback();
    } finally {
      setDisconnecting(null);
    }
  }, [refreshConnections, refreshHealthAll]);

  const [addingConnection, setAddingConnection] = useState(false);

  function cleanErrorMessage(raw: string): string {
    let msg = raw.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
    if (msg.length > 200) msg = msg.slice(0, 200) + "...";
    return msg;
  }

  const handleAddConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    setFeedback(null);
    setAddingConnection(true);
    try {
      const body: ConnectRequest =
        form.engine === "couchbase"
          ? {
              engine: "couchbase",
              connection_string: form.connection_string || undefined,
              bucket: form.bucket || undefined,
              username: form.username || undefined,
              password: form.password || undefined,
            }
          : {
              engine: "postgres",
              host: form.host || undefined,
              port: form.port ? parseInt(form.port, 10) : undefined,
              database: form.database || undefined,
              user: form.user || undefined,
              password: form.password || undefined,
            };

      const res = await api.connect(body);
      if (res.success) {
        setFeedback({ type: "success", message: res.message ?? "Connected" });
        clearFeedback();
        setForm(INITIAL_FORM);
        setExpanded(false);
        await refreshConnections();
        refreshHealthAll().catch(() => {});
      } else {
        setFeedback({ type: "error", message: cleanErrorMessage(res.message ?? "Connection failed") });
        clearFeedback();
      }
    } catch (err) {
      setFeedback({
        type: "error",
        message: cleanErrorMessage(err instanceof Error ? err.message : "Connection failed"),
      });
      clearFeedback();
    } finally {
      setAddingConnection(false);
    }
  };

  return (
    <div className="p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white tracking-tight">Connections</h1>
        <p className="mt-1 text-surface-400">Manage database connections</p>
      </header>

      {feedback && (
        <div
          className={`mb-6 px-4 py-3 rounded-lg ${
            feedback.type === "success"
              ? "bg-green-900/30 border border-green-700/50 text-green-400"
              : "bg-red-900/30 border border-red-700/50 text-red-400"
          }`}
        >
          {feedback.message}
        </div>
      )}

      <div className="mb-6">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="btn-primary"
        >
          {expanded ? "Cancel" : "Add Connection"}
        </button>
      </div>

      {expanded && (
        <form onSubmit={handleAddConnection} className="card mb-8">
          <h2 className="text-lg font-semibold text-white mb-4">New Connection</h2>

          <div className="mb-4">
            <label className="block text-sm font-medium text-surface-300 mb-2">Engine</label>
            <select
              value={form.engine}
              onChange={(e) => setForm((f) => ({ ...f, engine: e.target.value as Engine }))}
              className="input-field"
            >
              <option value="postgres">PostgreSQL</option>
              <option value="couchbase">Couchbase</option>
            </select>
          </div>

          {form.engine === "postgres" ? (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-surface-300 mb-2">Host</label>
                  <input type="text" value={form.host} onChange={(e) => setForm((f) => ({ ...f, host: e.target.value }))} placeholder="localhost" className="input-field" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-300 mb-2">Port</label>
                  <input type="text" value={form.port} onChange={(e) => setForm((f) => ({ ...f, port: e.target.value }))} placeholder="5432" className="input-field" />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-surface-300 mb-2">Database</label>
                  <input type="text" value={form.database} onChange={(e) => setForm((f) => ({ ...f, database: e.target.value }))} placeholder="mydb" className="input-field" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-300 mb-2">User</label>
                  <input type="text" value={form.user} onChange={(e) => setForm((f) => ({ ...f, user: e.target.value }))} placeholder="postgres" className="input-field" />
                </div>
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-surface-300 mb-2">Password</label>
                <input type="password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} placeholder="" className="input-field" />
              </div>
            </>
          ) : (
            <>
              <div className="mb-4">
                <label className="block text-sm font-medium text-surface-300 mb-2">Connection String</label>
                <input type="text" value={form.connection_string} onChange={(e) => setForm((f) => ({ ...f, connection_string: e.target.value }))} placeholder="couchbase://localhost" className="input-field" />
                <p className="mt-1 text-xs text-surface-500">e.g. couchbase://hostname or just the hostname — the scheme is added automatically</p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-surface-300 mb-2">Bucket</label>
                  <input type="text" value={form.bucket} onChange={(e) => setForm((f) => ({ ...f, bucket: e.target.value }))} placeholder="default" className="input-field" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-300 mb-2">Username</label>
                  <input type="text" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} placeholder="" className="input-field" />
                </div>
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-surface-300 mb-2">Password</label>
                <input type="password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} placeholder="" className="input-field" />
              </div>
            </>
          )}

          <div className="flex gap-3">
            <button type="submit" disabled={addingConnection} className="btn-primary disabled:opacity-50">
              {addingConnection ? "Connecting..." : "Connect"}
            </button>
            <button type="button" onClick={() => { setExpanded(false); setForm(INITIAL_FORM); }} className="btn-secondary" disabled={addingConnection}>Cancel</button>
          </div>
        </form>
      )}

      <h2 className="text-sm font-medium text-surface-400 uppercase tracking-wider mb-4">
        Existing Connections
      </h2>

      {connections.length === 0 ? (
        <div className="card">
          <p className="text-surface-500">No connections configured. Add a connection above.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {connections.map((conn) => (
            <div key={conn.id} className="card flex flex-col">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <h3 className="font-semibold text-white">{conn.name}</h3>
                  <span className={getEngineBadgeClass(conn.engine)}>{conn.engine}</span>
                  {conn.default && <span className="ml-2 badge-green">Default</span>}
                </div>
              </div>
              <div className="mt-auto flex gap-2 pt-4">
                <button type="button" onClick={() => handleConnect(conn)} disabled={connecting === conn.id} className="btn-primary flex-1 text-sm py-1.5">
                  {connecting === conn.id ? "Connecting..." : "Connect"}
                </button>
                <button type="button" onClick={() => handleDisconnect(conn.id)} disabled={disconnecting === conn.id} className="btn-secondary text-sm py-1.5">
                  {disconnecting === conn.id ? "..." : "Disconnect"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
