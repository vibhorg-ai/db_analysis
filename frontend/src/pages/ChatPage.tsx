import { useState, useRef, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client.ts";
import { useAppContext } from "../context/AppContext.tsx";
import ChatMessageRenderer, { type SandboxResult } from "../components/ChatMessageRenderer.tsx";

export default function ChatPage() {
  const {
    chatMessages: messages,
    setChatMessages: setMessages,
    chatSessionId: sessionId,
    setChatSessionId: setSessionIdCtx,
    chatContextSummary: contextSummary,
    setChatContextSummary: setContextSummary,
    activeConnectionId,
  } = useAppContext();

  const [sandboxResults, setSandboxResults] = useState<Map<string, SandboxResult>>(new Map());
  const [input, setInput] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const prefill = searchParams.get("prefill");
    if (prefill) {
      const decoded = decodeURIComponent(prefill);
      setInput(decoded);
      const next = new URLSearchParams(searchParams);
      next.delete("prefill");
      setSearchParams(next, { replace: true });
      sendMessage(decoded).then(() => setInput(""));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- only when prefill param is present
  }, [searchParams.get("prefill")]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const setSessionId = useCallback((id: string | null) => {
    setSessionIdCtx(id);
    if (id) localStorage.setItem("chat_session_id", id);
    else localStorage.removeItem("chat_session_id");
  }, [setSessionIdCtx]);

  const sendMessage = useCallback(
    async (text: string, attachedFiles?: File[]) => {
      if (!text.trim() && (!attachedFiles || attachedFiles.length === 0)) return;

      const userMsg = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`,
        role: "user" as const,
        content: attachedFiles && attachedFiles.length > 0
          ? `${text}\n[Attached: ${attachedFiles.map(f => f.name).join(", ")}]`
          : text,
      };
      setMessages((prev) => [...prev, userMsg]);
      setError(null);
      setLoading(true);

      try {
        const res = await api.chat(
          text || `Analyze the uploaded report${attachedFiles && attachedFiles.length > 1 ? "s" : ""}: ${attachedFiles?.map(f => f.name).join(", ")}`,
          sessionId ?? undefined,
          attachedFiles && attachedFiles.length > 0 ? attachedFiles : undefined,
          activeConnectionId ?? undefined,
        );
        setSessionId(res.session_id);
        setContextSummary(res.context_summary ?? null);

        if (attachedFiles && attachedFiles.length > 0) {
          setMessages((prev) => [
            ...prev,
            { id: `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`, role: "system" as const, content: `${attachedFiles.length} report${attachedFiles.length > 1 ? "s" : ""} uploaded and parsed: ${attachedFiles.map(f => f.name).join(", ")}` },
          ]);
        }

        setMessages((prev) => [...prev, { id: `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`, role: "assistant" as const, content: res.reply }]);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Chat failed");
      } finally {
        setLoading(false);
      }
    },
    [sessionId, activeConnectionId, setMessages, setSessionId, setContextSummary],
  );

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text && files.length === 0) return;
    const currentFiles = [...files];
    setInput("");
    setFiles([]);
    if (fileRef.current) fileRef.current.value = "";
    await sendMessage(text, currentFiles);
  }, [input, files, sendMessage]);

  const handleRunInSandbox = useCallback(
    async (sql: string) => {
      const key = sql.trim();
      setSandboxResults((prev) => new Map(prev).set(key, { loading: true }));
      try {
        const res = await api.sandbox({ query: sql, connection_id: activeConnectionId ?? undefined });
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

  const handleAnalyzeQuery = useCallback(
    (sql: string) => {
      sendMessage(
        `Analyze this SQL query for performance, potential issues, and optimization opportunities:\n\`\`\`sql\n${sql}\n\`\`\``,
      );
    },
    [sendMessage],
  );


  const handleBlastImpact = useCallback(
    (sql: string) => {
      sendMessage(
        `What is the blast radius / impact of running this query? Analyze which tables, indexes, constraints, dependent views, triggers, and downstream services would be affected:\n\`\`\`sql\n${sql}\n\`\`\``,
      );
    },
    [sendMessage],
  );

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const newFiles = e.target.files;
    if (newFiles && newFiles.length > 0) {
      setFiles((prev) => [...prev, ...Array.from(newFiles)]);
    }
  }

  function newSession() {
    setMessages([]);
    setSessionId(null);
    setContextSummary(null);
    setSandboxResults(new Map());
    setFiles([]);
    setError(null);
  }

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center justify-between px-6 py-4 border-b border-surface-700">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Chatbot</h1>
          <p className="text-sm text-surface-200/60 mt-0.5">
            Full-context AI assistant &mdash; upload reports, ask about schema, health, and more
          </p>
        </div>
        <div className="flex items-center gap-3">
          {contextSummary && (
            <div className="flex flex-wrap gap-1.5">
              {contextSummary.has_connection && <span className="badge-green">DB Connected</span>}
              {contextSummary.has_schema && <span className="badge-green">Schema</span>}
              {contextSummary.has_health && <span className="badge-green">Health</span>}
              {contextSummary.reports_loaded.length > 0 && (
                <span className="badge-yellow">
                  {contextSummary.reports_loaded.length} report{contextSummary.reports_loaded.length > 1 ? "s" : ""}
                </span>
              )}
            </div>
          )}
          <button type="button" className="btn-secondary text-sm" onClick={newSession}>
            New Session
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-surface-200/40">
            <svg className="w-16 h-16 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <p className="text-lg font-medium">Start a conversation</p>
            <p className="text-sm mt-1">Ask about your database, or upload an HTML report to analyze</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={msg.id ?? `msg-${i}`} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "user" ? (
              <div className="max-w-[75%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap bg-primary-600 text-white">
                {msg.content}
              </div>
            ) : msg.role === "system" ? (
              <div className="max-w-[85%] rounded-xl px-4 py-3 bg-surface-800/70 border border-surface-700/60">
                <ChatMessageRenderer content={msg.content} onRunInSandbox={handleRunInSandbox} onAnalyzeQuery={handleAnalyzeQuery} onBlastImpact={handleBlastImpact} sandboxResults={sandboxResults} />
              </div>
            ) : (
              <div className="max-w-[85%] rounded-2xl px-5 py-4 bg-surface-800 border border-surface-700">
                <ChatMessageRenderer content={msg.content} onRunInSandbox={handleRunInSandbox} onAnalyzeQuery={handleAnalyzeQuery} onBlastImpact={handleBlastImpact} sandboxResults={sandboxResults} />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-surface-800 border border-surface-700 rounded-2xl px-4 py-3 flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-surface-200/60">Thinking...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="flex justify-center">
            <div className="bg-red-900/30 border border-red-700/50 rounded-xl px-4 py-2 text-sm text-red-400">{error}</div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {files.length > 0 && (
        <div className="px-6 pb-1 flex flex-wrap gap-2">
          {files.map((f, i) => (
            <div key={i} className="inline-flex items-center gap-2 bg-surface-800 border border-surface-700 rounded-lg px-3 py-1.5 text-sm">
              <svg className="w-4 h-4 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
              <span className="text-surface-200">{f.name}</span>
              <button type="button" className="text-surface-200/50 hover:text-red-400" onClick={() => setFiles((prev) => prev.filter((_, j) => j !== i))}>
                &times;
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="px-6 py-4 border-t border-surface-700">
        <div className="flex items-end gap-3">
          <button type="button" className="flex-shrink-0 p-2.5 rounded-lg bg-surface-800 hover:bg-surface-700 text-surface-200 transition-colors" onClick={() => fileRef.current?.click()} title="Upload HTML report" aria-label="Upload HTML report">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
          </button>
          <input ref={fileRef} type="file" accept=".html,.htm" multiple className="hidden" onChange={handleFileChange} aria-label="Upload HTML report files" />
          <textarea className="input-field flex-1 resize-none min-h-[44px] max-h-[120px]" placeholder="Ask about your database, or upload a report..." value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} rows={1} aria-label="Chat message input" />
          <button type="button" className="btn-primary flex-shrink-0" onClick={send} disabled={loading || (!input.trim() && files.length === 0)}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
