import React, { createContext, useContext, useEffect, useState, useCallback } from "react";

export interface Connection {
  id: string;
  name: string;
  engine: string;
  default: boolean;
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
  refreshConnections: () => Promise<void>;
  healthMap: Record<string, DBHealthResponse>;
  setHealthForConnection: (connId: string, health: DBHealthResponse) => void;
  refreshHealthAll: () => Promise<void>;
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

  const refreshConnections = useCallback(async () => {
    const res = await fetch("/api/connections");
    if (!res.ok) throw new Error(`Failed to fetch connections: ${res.status}`);
    const data = await res.json();
    setConnections(data);
  }, []);

  const setHealthForConnection = useCallback((connId: string, health: DBHealthResponse) => {
    setHealthMap((prev) => ({ ...prev, [connId]: health }));
  }, []);

  const refreshHealthAll = useCallback(async () => {
    try {
      const res = await fetch("/api/connections");
      if (!res.ok) return;
      const conns: Connection[] = await res.json();
      const next: Record<string, DBHealthResponse> = {};
      for (const c of conns) {
        try {
          const hRes = await fetch(`/api/db-health?connection_id=${encodeURIComponent(c.id)}`);
          if (hRes.ok) {
            const h = await hRes.json();
            next[c.id] = { ...h, connection_id: c.id };
          }
        } catch {
          /* ignore */
        }
      }
      setHealthMap((prev) => ({ ...prev, ...next }));
    } catch {
      /* ignore */
    }
  }, []);

  const setSchemaForConnection = useCallback((connId: string, tables: TableMeta[]) => {
    setSchemaMap((prev) => ({ ...prev, [connId]: tables }));
  }, []);

  const fetchSchemaIfNeeded = useCallback(
    async (connId: string): Promise<TableMeta[]> => {
      const cached = schemaMap[connId];
      if (cached) return cached;
      const res = await fetch(`/api/schema?connection_id=${encodeURIComponent(connId)}`);
      if (!res.ok) throw new Error(`Failed to fetch schema: ${res.status}`);
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
    try {
      const res = await fetch("/api/issues");
      if (!res.ok) return;
      const data = await res.json();
      const list = Array.isArray(data) ? data : data.issues ?? data.items ?? [];
      setIssues(list);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    refreshConnections();
    refreshHealthAll().catch(() => {});
    refreshIssues().catch(() => {});
  }, [refreshConnections, refreshHealthAll, refreshIssues]);

  const value: AppContextType = {
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
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppContext(): AppContextType {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppContext must be used within AppProvider");
  return ctx;
}
