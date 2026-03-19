import React, { createContext, useContext, useEffect, useRef, useState, useCallback, useMemo } from "react";
import { api } from "../api/client.ts";

export interface Connection {
  id: string;
  name: string;
  engine: string;
  default: boolean;
  connected?: boolean;
}

export interface DBHealthResponse {
  score: number;
  status: string;
  metrics: Record<string, unknown>[];
  alerts: { message: string }[];
  connection_id?: string;
}

export interface TableMeta {
  table_name: string;
  columns: { column_name: string; data_type: string; is_nullable: string }[];
  primary_keys: string[];
  foreign_keys: { column: string; references_table: string; references_column: string }[];
}

export type Severity = "critical" | "high" | "warning" | "info";
export type IssueCategory = "performance" | "locks" | "schema" | "configuration" | "maintenance" | "security" | "other";

export interface Issue {
  id: string;
  title: string;
  description: string;
  severity: Severity;
  category: IssueCategory;
  timestamp: string;
  source: string;
  resolved: boolean;
  connection_id?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatContextSummary {
  session_id: string;
  message_count: number;
  reports_loaded: string[];
  has_schema: boolean;
  has_health: boolean;
  analysis_count: number;
  has_connection: boolean;
}

interface AppContextType {
  connections: Connection[];
  activeConnectionId: string | null;
  setActiveConnectionId: (id: string | null) => void;
  refreshConnections: (force?: boolean) => Promise<void>;
  healthMap: Record<string, DBHealthResponse>;
  setHealthForConnection: (connId: string, health: DBHealthResponse) => void;
  refreshHealthAll: (force?: boolean) => Promise<void>;
  schemaMap: Record<string, TableMeta[]>;
  setSchemaForConnection: (connId: string, tables: TableMeta[]) => void;
  fetchSchemaIfNeeded: (connId: string) => Promise<TableMeta[]>;
  issues: Issue[];
  addIssues: (newIssues: Issue[]) => void;
  resolveIssue: (id: string) => void;
  refreshIssues: () => Promise<void>;
  chatMessages: ChatMessage[];
  setChatMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  chatSessionId: string | null;
  setChatSessionId: (id: string | null) => void;
  chatContextSummary: ChatContextSummary | null;
  setChatContextSummary: (summary: ChatContextSummary | null) => void;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [activeConnectionId, setActiveConnectionId] = useState<string | null>(null);
  const [healthMap, setHealthMap] = useState<Record<string, DBHealthResponse>>({});
  const [schemaMap, setSchemaMap] = useState<Record<string, TableMeta[]>>({});
  const [issues, setIssues] = useState<Issue[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatSessionId, setChatSessionId] = useState<string | null>(() =>
    localStorage.getItem("chat_session_id")
  );
  const [chatContextSummary, setChatContextSummary] = useState<ChatContextSummary | null>(null);

  const STALE_MS = 30_000;
  const lastFetchRef = useRef<Record<string, number>>({});
  /** Backend instance_id; when it changes (restart), we clear stale chat state. */
  const lastBackendInstanceIdRef = useRef<string | null>(null);

  const isStale = useCallback((key: string) => {
    const last = lastFetchRef.current[key] ?? 0;
    return Date.now() - last > STALE_MS;
  }, []);

  const markFetched = useCallback((key: string) => {
    lastFetchRef.current[key] = Date.now();
  }, []);

  const refreshConnections = useCallback(async (force?: boolean) => {
    if (!force && !isStale("connections")) return;
    try {
      const res = await fetch("/api/connections");
      if (!res.ok) throw new Error(`Failed to fetch connections: ${res.status}`);
      const data: Connection[] = await res.json();
      setConnections(data);
      markFetched("connections");

      // Auto-set activeConnectionId: if none set, pick first connected; if current is gone, clear.
      setActiveConnectionId((prev) => {
        if (prev && data.some((c) => c.id === prev)) return prev;
        const firstConnected = data.find((c) => c.connected);
        return firstConnected?.id ?? data[0]?.id ?? null;
      });
    } catch (e) {
      if ((e as Error)?.message?.includes("429")) return;
      console.warn("Connections fetch failed, using empty list", e);
      setConnections([]);
      markFetched("connections");
    }
  }, [isStale, markFetched]);

  const setHealthForConnection = useCallback((connId: string, health: DBHealthResponse) => {
    setHealthMap((prev) => ({ ...prev, [connId]: health }));
  }, []);

  const refreshHealthAll = useCallback(async (force?: boolean) => {
    if (!force && !isStale("health")) return;
    try {
      const allRes = await fetch("/api/db-health/all");
      if (!allRes.ok) return;
      const allData = await allRes.json();
      const conns = (allData.connections ?? allData) as Record<string, DBHealthResponse>;
      const next: Record<string, DBHealthResponse> = {};
      for (const [connId, h] of Object.entries(conns)) {
        next[connId] = { ...h, connection_id: connId };
      }
      setHealthMap((prev) => ({ ...prev, ...next }));
      markFetched("health");
    } catch {
      /* ignore */
    }
  }, [isStale, markFetched]);

  const setSchemaForConnection = useCallback((connId: string, tables: TableMeta[]) => {
    setSchemaMap((prev) => ({ ...prev, [connId]: tables }));
  }, []);

  const fetchSchemaIfNeeded = useCallback(
    async (connId: string): Promise<TableMeta[]> => {
      const cached = schemaMap[connId];
      if (cached) return cached;
      const res = await fetch(`/api/schema?connection_id=${encodeURIComponent(connId)}`);
      if (!res.ok) {
        if (res.status === 400) {
          setSchemaMap((prev) => ({ ...prev, [connId]: [] }));
          return [];
        }
        throw new Error(`Failed to fetch schema: ${res.status}`);
      }
      const data = await res.json();
      const tables = data.tables ?? data;
      setSchemaMap((prev) => ({ ...prev, [connId]: tables }));
      return tables;
    },
    [schemaMap]
  );

  const addIssues = useCallback((newIssues: Issue[]) => {
    setIssues((prev) => {
      const byId = new Map(prev.map((i) => [i.id, i]));
      for (const i of newIssues) byId.set(i.id, i);
      return Array.from(byId.values());
    });
  }, []);

  const resolveIssue = useCallback((id: string) => {
    setIssues((prev) =>
      prev.map((i) => (i.id === id ? { ...i, resolved: true } : i))
    );
  }, []);

  const refreshIssues = useCallback(async () => {
    if (!isStale("issues")) return;
    try {
      const res = await fetch("/api/issues");
      if (!res.ok) return;
      const data = await res.json();
      const list = Array.isArray(data) ? data : data.issues ?? data.items ?? [];
      setIssues(list);
      markFetched("issues");
    } catch {
      /* ignore */
    }
  }, [isStale, markFetched]);

  useEffect(() => {
    refreshConnections();
    refreshHealthAll().catch(() => {});
    refreshIssues().catch(() => {});
  }, [refreshConnections, refreshHealthAll, refreshIssues]);

  // Validate persisted chat session on load and clear if backend restarted (sessions are in-memory).
  useEffect(() => {
    const sid = localStorage.getItem("chat_session_id");
    if (!sid) return;
    api
      .validateChatSession(sid)
      .then((result) => {
        if (result === null) {
          localStorage.removeItem("chat_session_id");
          setChatSessionId(null);
          setChatMessages([]);
          setChatContextSummary(null);
        } else {
          setChatContextSummary(result.context_summary);
        }
      })
      .catch(() => {
        localStorage.removeItem("chat_session_id");
        setChatSessionId(null);
        setChatMessages([]);
        setChatContextSummary(null);
      });
  }, []);

  // Detect backend restart (instance_id change) and clear chat state so we don't show stale data.
  useEffect(() => {
    const checkBackendInstance = async () => {
      try {
        const h = await api.getHealth();
        const prev = lastBackendInstanceIdRef.current;
        if (prev != null && prev !== h.instance_id) {
          localStorage.removeItem("chat_session_id");
          setChatSessionId(null);
          setChatMessages([]);
          setChatContextSummary(null);
        }
        lastBackendInstanceIdRef.current = h.instance_id;
      } catch {
        /* ignore */
      }
    };
    checkBackendInstance();
    const interval = setInterval(checkBackendInstance, 25_000);
    return () => clearInterval(interval);
  }, []);

  const value = useMemo<AppContextType>(
    () => ({
      connections,
      activeConnectionId,
      setActiveConnectionId,
      refreshConnections,
      healthMap,
      setHealthForConnection,
      refreshHealthAll,
      schemaMap,
      setSchemaForConnection,
      fetchSchemaIfNeeded,
      issues,
      addIssues,
      resolveIssue,
      refreshIssues,
      chatMessages,
      setChatMessages,
      chatSessionId,
      setChatSessionId,
      chatContextSummary,
      setChatContextSummary,
    }),
    [
      connections,
      activeConnectionId,
      refreshConnections,
      healthMap,
      setHealthForConnection,
      refreshHealthAll,
      schemaMap,
      setSchemaForConnection,
      fetchSchemaIfNeeded,
      issues,
      addIssues,
      resolveIssue,
      refreshIssues,
      chatMessages,
      chatSessionId,
      chatContextSummary,
    ]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppContext(): AppContextType {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppContext must be used within AppProvider");
  return ctx;
}
