import { useState, useRef, useEffect, useCallback } from "react";
import { api } from "../api/client.ts";
import { useAppContext } from "../context/AppContext.tsx";
import ChatMessageRenderer, { type SandboxResult } from "./ChatMessageRenderer.tsx";

export default function ChatWidget() {
  const {
    chatMessages: messages,
    setChatMessages: setMessages,
    chatSessionId: sessionId,
    setChatSessionId: setSessionIdCtx,
    chatContextSummary: contextSummary,
    setChatContextSummary: setContextSummary,
    activeConnectionId,
  } = useAppContext();

  const [open, setOpen] = useState(false);
  const [sandboxResults, setSandboxResults] = useState<Map<string, SandboxResult>>(new Map());
  const [input, setInput] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const setSessionId = useCallback((id: string | null) => {
    setSessionIdCtx(id);
    if (id) localStorage.setItem("chat_session_id", id);
    else localStorage.removeItem("chat_session_id");
  }, [setSessionIdCtx]);

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  const genMsgId = () => Date.now() + "-" + Math.random().toString(36).substring(2, 11);

  const sendMessage = useCallback(
    async (text: string, attachedFiles?: File[]) => {
      if (!text.trim() && (!attachedFiles || attachedFiles.length === 0)) return;

      const userMsg = {
        id: genMsgId(),
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
            { id: genMsgId(), role: "system" as const, content: `${attachedFiles.length} report${attachedFiles.length > 1 ? "s" : ""} uploaded and parsed: ${attachedFiles.map(f => f.name).join(", ")}` },
          ]);
        }
        setMessages((prev) => [...prev, { id: genMsgId(), role: "assistant" as const, content: res.reply }]);
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

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-primary-600 hover:bg-primary-700 text-white shadow-lg flex items-center justify-center transition-all hover:scale-105"
        title="Open chat"
        aria-label="Open chat"
      >
        <svg
          className="w-6 h-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 w-[420px] h-[560px] bg-surface-900 border border-surface-700 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-700 bg-surface-800">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm text-white">
            DB Analyzer Chat
          </span>
          {contextSummary && contextSummary.reports_loaded.length > 0 && (
            <span className="badge-yellow text-[10px]">
              {contextSummary.reports_loaded.length} report
              {contextSummary.reports_loaded.length > 1 ? "s" : ""}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-surface-200/50 hover:text-white transition-colors"
          aria-label="Close chat"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-surface-200/30 text-center">
            <p className="text-sm">Ask anything or upload a report</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={msg.id ?? `msg-${i}`}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "user" ? (
              <div className="max-w-[85%] rounded-xl px-3 py-2 text-xs whitespace-pre-wrap bg-primary-600 text-white">
                {msg.content}
              </div>
            ) : msg.role === "system" ? (
              <div className="max-w-[90%] rounded-lg px-3 py-2 bg-surface-800/70 border border-surface-700/60">
                <ChatMessageRenderer
                  content={msg.content}
                  compact
                  onRunInSandbox={handleRunInSandbox}
                  onAnalyzeQuery={handleAnalyzeQuery}
                  onBlastImpact={handleBlastImpact}
                  sandboxResults={sandboxResults}
                />
              </div>
            ) : (
              <div className="max-w-[90%] rounded-xl px-3 py-2.5 bg-surface-800 border border-surface-700">
                <ChatMessageRenderer
                  content={msg.content}
                  compact
                  onRunInSandbox={handleRunInSandbox}
                  onAnalyzeQuery={handleAnalyzeQuery}
                  onBlastImpact={handleBlastImpact}
                  sandboxResults={sandboxResults}
                />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-surface-800 border border-surface-700 rounded-xl px-3 py-2 flex items-center gap-1.5">
              <div className="w-3 h-3 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-xs text-surface-200/50">Thinking...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="text-xs text-red-400 bg-red-900/20 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* File chips */}
      {files.length > 0 && (
        <div className="px-3 pb-1 flex flex-wrap gap-2">
          {files.map((f, i) => (
            <div key={i} className="inline-flex items-center gap-1.5 bg-surface-800 border border-surface-700 rounded px-2 py-1 text-xs">
              <span className="text-surface-200 truncate max-w-[200px]">{f.name}</span>
              <button type="button" className="text-surface-200/50 hover:text-red-400" onClick={() => setFiles((prev) => prev.filter((_, j) => j !== i))}>
                &times;
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="px-3 py-2 border-t border-surface-700">
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="flex-shrink-0 p-1.5 rounded bg-surface-800 hover:bg-surface-700 text-surface-200 transition-colors"
            onClick={() => fileRef.current?.click()}
            title="Upload report"
            aria-label="Upload report"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
              />
            </svg>
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".html,.htm"
            multiple
            className="hidden"
            aria-label="Upload HTML report files"
            onChange={(e) => {
              const newFiles = e.target.files;
              if (newFiles && newFiles.length > 0) {
                setFiles((prev) => [...prev, ...Array.from(newFiles)]);
              }
            }}
          />
          <input
            type="text"
            className="input-field flex-1 text-sm py-1.5"
            placeholder="Ask something..."
            aria-label="Chat message input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            type="button"
            className="btn-primary text-sm py-1.5 px-3"
            onClick={send}
            disabled={loading || (!input.trim() && files.length === 0)}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
