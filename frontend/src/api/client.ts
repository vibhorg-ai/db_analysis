const BASE = "/api";

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  getConnections: () => request<Connection[]>("/connections"),

  connect: (body: ConnectRequest) =>
    request<ConnectResponse>("/connect", { method: "POST", body: JSON.stringify(body) }),

  disconnect: (id: string) =>
    request<{ success: boolean }>(`/disconnect/${encodeURIComponent(id)}`, { method: "POST" }),

  getSchema: (connectionId?: string) =>
    request<SchemaResponse>(`/schema${connectionId ? `?connection_id=${connectionId}` : ""}`),

  analyzeQuery: (body: AnalyzeQueryRequest, signal?: AbortSignal) =>
    request<AnalyzeQueryResponse>("/analyze-query", { method: "POST", body: JSON.stringify(body), signal }),

  getIndexRecommendations: (connectionId?: string) =>
    request<IndexRecsResponse>(`/index-recommendations${connectionId ? `?connection_id=${connectionId}` : ""}`),

  getDbHealth: (connectionId?: string) =>
    request<DBHealthResponse>(`/db-health${connectionId ? `?connection_id=${connectionId}` : ""}`),

  getMcpStatus: () => request<MCPStatusResponse>("/mcp-status"),

  /** Backend health including instance_id (changes on restart). Used to clear stale chat state. */
  getHealth: () =>
    request<{ status: string; version: string; instance_id: string }>("/health"),

  /**
   * Validate that a chat session still exists on the backend (sessions are in-memory and lost on restart).
   * Returns context_summary if valid, null if session not found or expired (404).
   */
  validateChatSession: async (sessionId: string): Promise<{ context_summary: ChatContextSummary } | null> => {
    const res = await fetch(`${BASE}/chat/session/validate?session_id=${encodeURIComponent(sessionId)}`);
    if (res.status === 404) return null;
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  chat: async (message: string, sessionId?: string, files?: File[], connectionId?: string): Promise<ChatResponse> => {
    const form = new FormData();
    form.append("message", message);
    if (sessionId) form.append("session_id", sessionId);
    if (connectionId) form.append("connection_id", connectionId);
    if (files) {
      for (const f of files) form.append("files", f);
    }
    const res = await fetch(`${BASE}/chat`, { method: "POST", body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  sandbox: (body: SandboxRequest) =>
    request<SandboxResponse>("/sandbox", { method: "POST", body: JSON.stringify(body) }),

  getIssues: (params?: { category?: string; severity?: string }) => {
    const sp = new URLSearchParams();
    if (params?.category) sp.set("category", params.category);
    if (params?.severity) sp.set("severity", params.severity);
    const qs = sp.toString();
    return request<IssueResponse[]>(`/issues${qs ? `?${qs}` : ""}`);
  },

  resolveIssue: (issueId: string) =>
    request<{ success: boolean; message: string }>(`/issues/${issueId}/resolve`, { method: "POST" }),

  getAllDbHealth: () =>
    request<{ connections: Record<string, DBHealthResponse> }>("/db-health/all"),

  getInsights: async (category?: string): Promise<InsightResponse[]> => {
    const qs = category && category !== "all" ? `?category=${encodeURIComponent(category)}` : "";
    const data = await request<InsightResponse[] | { insights?: InsightResponse[]; items?: InsightResponse[] }>(`/insights${qs}`);
    return Array.isArray(data) ? data : data.insights ?? data.items ?? [];
  },

  dismissInsight: (id: string) =>
    request<{ success?: boolean }>(`/insights/${id}/dismiss`, { method: "POST" }),

  runAdvisor: () =>
    request<{ success?: boolean }>("/insights/run", { method: "POST" }),

  simulate: (body: SimulateRequest) =>
    request<SimulateResponse>("/simulate", { method: "POST", body: JSON.stringify(body) }),
};

// Types
export interface Connection {
  id: string;
  name: string;
  engine: string;
  default: boolean;
  connected?: boolean;
}

export interface ConnectRequest {
  engine?: string;
  connection_id?: string;
  dsn?: string;
  host?: string;
  port?: number;
  database?: string;
  user?: string;
  password?: string;
  connection_string?: string;
  bucket?: string;
  username?: string;
}

export interface ConnectResponse {
  success: boolean;
  message: string;
  connection_id?: string;
  details?: Record<string, unknown>;
}

export interface SchemaResponse {
  tables: TableMeta[];
  connection_id?: string;
}

export interface TableMeta {
  table_name: string;
  columns: { column_name: string; data_type: string; is_nullable: string }[];
  primary_keys: string[];
  foreign_keys: { column: string; references_table: string; references_column: string }[];
}

export interface AnalyzeQueryRequest {
  query: string;
  connection_id?: string;
  mode?: string;
}

export interface AnalyzeQueryResponse {
  run_id?: string;
  mode: string;
  results: Record<string, unknown>;
  timing: Record<string, number>;
}

export interface IndexRecsResponse {
  recommendations: Record<string, unknown>[];
}

export interface DBHealthResponse {
  score: number;
  status: string;
  metrics: Record<string, unknown>[];
  alerts: { message: string }[];
}

export interface MCPStatusResponse {
  postgres: Record<string, unknown>;
  couchbase: Record<string, unknown>;
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

export interface ChatResponse {
  reply: string;
  session_id: string;
  context_summary: ChatContextSummary;
}

export interface SandboxRequest {
  query: string;
  connection_id?: string;
}

export interface SandboxResponse {
  success: boolean;
  rows: Record<string, unknown>[];
  row_count: number;
  error?: string;
}

export interface IssueResponse {
  id: string;
  timestamp: number;
  severity: string;
  title: string;
  description: string;
  source: string;
  category: string;
  resolved: boolean;
  resolved_at: number | null;
  connection_id: string;
}

export interface InsightResponse {
  id: string;
  timestamp: number;
  category: string;
  title: string;
  description: string;
  recommendation: string;
  suggested_sql: string | null;
  impact: string;
  confidence: number;
  risk: string;
  connection_id: string;
  source: string;
  dismissed: boolean;
}

export interface SimulateRequest {
  change_type: string;
  connection_id?: string;
  table?: string;
  column?: string;
  columns?: string[];
  index_name?: string;
  partition_column?: string;
  target_rows?: number;
  original_query?: string;
  optimized_query?: string;
}

export interface SimulateResponse {
  id: string;
  simulation_type: string;
  input_description: string;
  result: Record<string, unknown>;
  connection_id: string;
  timestamp: number;
}
