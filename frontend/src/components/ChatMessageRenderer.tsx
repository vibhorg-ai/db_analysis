import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

export interface SandboxResult {
  loading: boolean;
  rows?: Record<string, unknown>[];
  rowCount?: number;
  error?: string;
}

interface Props {
  content: string;
  compact?: boolean;
  onRunInSandbox?: (sql: string) => void;
  onAnalyzeQuery?: (sql: string) => void;
  onBlastImpact?: (sql: string) => void;
  sandboxResults?: Map<string, SandboxResult>;
}

const DESTRUCTIVE_PATTERN =
  /\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|DROP\s+(TABLE|INDEX|VIEW|FUNCTION|TRIGGER|DATABASE|SCHEMA|SEQUENCE)|ALTER\s+(TABLE|INDEX|VIEW|FUNCTION|DATABASE)|TRUNCATE|pg_cancel_backend|pg_terminate_backend)\b/i;

function isDestructiveSQL(sql: string): boolean {
  return DESTRUCTIVE_PATTERN.test(sql);
}

function isSQLCode(language: string | undefined, code: string): boolean {
  if (language && /^(sql|pgsql|plpgsql|postgresql)$/i.test(language)) return true;
  const hits = (
    code.match(
      /\b(SELECT|FROM|WHERE|JOIN|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TABLE|INDEX|pg_locks|pg_stat_activity|pg_class|pg_database|pg_cancel_backend|pg_terminate_backend)\b/gi,
    ) || []
  ).length;
  return hits >= 2;
}

function highlightSQL(code: string): string {
  let html = code
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  const strings: string[] = [];
  html = html.replace(/'([^']*)'/g, (m) => {
    strings.push(m);
    return `__S${strings.length - 1}__`;
  });

  const comments: string[] = [];
  html = html.replace(/--(.*?)$/gm, (m) => {
    comments.push(m);
    return `__C${comments.length - 1}__`;
  });

  html = html.replace(
    /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|CROSS|FULL|NATURAL|ON|AND|OR|NOT|IN|AS|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET|UNION|ALL|DISTINCT|CASE|WHEN|THEN|ELSE|END|EXISTS|BETWEEN|LIKE|ILIKE|IS|NULL|TRUE|FALSE|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|DROP|ALTER|TRUNCATE|TABLE|INDEX|VIEW|FUNCTION|TRIGGER|CONSTRAINT|PRIMARY|FOREIGN|KEY|REFERENCES|CASCADE|DEFAULT|CHECK|UNIQUE|GRANT|REVOKE|WITH|RECURSIVE|LATERAL|EXPLAIN|ANALYZE|BEGIN|COMMIT|ROLLBACK|RETURNING|COALESCE|NULLS|LAST|FIRST|ASC|DESC|OVER|PARTITION|USING|NOW|COUNT|SUM|AVG|MIN|MAX)\b/gi,
    '<span class="sql-kw">$&</span>',
  );

  html = html.replace(
    /\b(\d+(?:\.\d+)?)\b/g,
    '<span class="sql-num">$1</span>',
  );

  comments.forEach((c, i) => {
    const escaped = c
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    html = html.replace(`__C${i}__`, `<span class="sql-cmt">${escaped}</span>`);
  });

  strings.forEach((s, i) => {
    const escaped = s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    html = html.replace(`__S${i}__`, `<span class="sql-str">${escaped}</span>`);
  });

  return html;
}

function SQLCodeBlock({
  code,
  compact,
  onRunInSandbox,
  onAnalyzeQuery,
  onBlastImpact,
  sandboxResult,
}: {
  code: string;
  compact: boolean;
  onRunInSandbox?: (sql: string) => void;
  onAnalyzeQuery?: (sql: string) => void;
  onBlastImpact?: (sql: string) => void;
  sandboxResult?: SandboxResult;
}) {
  const destructive = isDestructiveSQL(code);
  const highlighted = useMemo(() => highlightSQL(code), [code]);
  const [copied, setCopied] = React.useState(false);

  function copy() {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const showActions = onRunInSandbox || onAnalyzeQuery || (destructive && onBlastImpact);

  return (
    <div className="my-3 rounded-lg overflow-hidden border border-surface-700/80 bg-[#0c1222]">
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface-800/90 border-b border-surface-700/60">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-primary-400/70 uppercase tracking-widest font-semibold">
            SQL
          </span>
          {destructive && (
            <span className="text-[9px] font-medium text-amber-400/80 bg-amber-500/10 border border-amber-500/20 rounded px-1.5 py-0.5 uppercase tracking-wider">
              Write
            </span>
          )}
        </div>
        <button
          type="button"
          className="text-[10px] text-surface-200/40 hover:text-surface-200/80 transition-colors font-medium"
          onClick={copy}
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>

      <pre
        className={`${compact ? "text-[10px]" : "text-[13px]"} px-4 py-3 overflow-x-auto font-mono leading-relaxed`}
      >
        <code dangerouslySetInnerHTML={{ __html: highlighted }} />
      </pre>

      {showActions && (
        <div className="flex items-center gap-2 px-3 py-2 bg-surface-800/40 border-t border-surface-700/50">
          {onRunInSandbox && (
            <button
              type="button"
              className="chat-action-btn text-blue-400 bg-blue-500/10 border-blue-500/25 hover:bg-blue-500/20"
              onClick={() => onRunInSandbox(code)}
            >
              <svg
                className="w-3 h-3"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"
                  clipRule="evenodd"
                />
              </svg>
              Run in Sandbox
            </button>
          )}
          {onAnalyzeQuery && (
            <button
              type="button"
              className="chat-action-btn text-emerald-400 bg-emerald-500/10 border-emerald-500/25 hover:bg-emerald-500/20"
              onClick={() => onAnalyzeQuery(code)}
            >
              <svg
                className="w-3 h-3"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              Analyze Query
            </button>
          )}
          {destructive && onBlastImpact && (
            <button
              type="button"
              className="chat-action-btn text-amber-400 bg-amber-500/10 border-amber-500/25 hover:bg-amber-500/20"
              onClick={() => onBlastImpact(code)}
            >
              <svg
                className="w-3 h-3"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
              Blast Impact
            </button>
          )}
        </div>
      )}
      {sandboxResult && (
        <div className="border-t border-surface-700/50 px-3 py-2">
          {sandboxResult.loading ? (
            <div className="flex items-center gap-2 text-xs text-surface-200/60">
              <div className="w-3 h-3 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
              Running...
            </div>
          ) : sandboxResult.error ? (
            <div className="text-xs text-red-400">
              <span className="font-medium">Error:</span> {sandboxResult.error}
            </div>
          ) : (
            <div>
              <p className="text-[11px] text-surface-200/60 mb-1">
                {sandboxResult.rowCount ?? 0} row{(sandboxResult.rowCount ?? 0) !== 1 ? "s" : ""} returned
              </p>
              {sandboxResult.rows && sandboxResult.rows.length > 0 && (
                <div className="overflow-x-auto max-h-[240px] overflow-y-auto rounded border border-surface-700/40">
                  <table className="w-full text-[11px]">
                    <thead className="bg-surface-800/60 sticky top-0">
                      <tr>
                        {Object.keys(sandboxResult.rows[0]).map((col) => (
                          <th key={col} className="px-2 py-1 text-left font-medium text-surface-300 whitespace-nowrap">{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sandboxResult.rows.slice(0, 50).map((row, ri) => (
                        <tr key={ri} className="border-t border-surface-700/30">
                          {Object.keys(sandboxResult.rows![0]).map((col) => (
                            <td key={col} className="px-2 py-1 text-surface-200 whitespace-nowrap max-w-[150px] truncate">
                              {row[col] == null ? "NULL" : String(row[col])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function GenericCodeBlock({
  code,
  language,
  compact,
}: {
  code: string;
  language?: string;
  compact: boolean;
}) {
  const [copied, setCopied] = React.useState(false);

  function copy() {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="my-3 rounded-lg overflow-hidden border border-surface-700/80 bg-[#0c1222]">
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface-800/90 border-b border-surface-700/60">
        <span className="text-[10px] font-mono text-surface-200/50 uppercase tracking-widest">
          {language || "code"}
        </span>
        <button
          type="button"
          className="text-[10px] text-surface-200/40 hover:text-surface-200/80 transition-colors font-medium"
          onClick={copy}
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      <pre
        className={`${compact ? "text-[10px]" : "text-[13px]"} px-4 py-3 overflow-x-auto font-mono leading-relaxed text-surface-200`}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}

/**
 * Pre-process LLM output to wrap unfenced SQL blocks in ```sql fences.
 * Handles cases where the LLM outputs raw SQL without markdown code blocks.
 */
function preprocessContent(raw: string): string {
  if (!raw) return raw;

  const lines = raw.split("\n");
  const result: string[] = [];
  let inCodeBlock = false;
  let sqlBuffer: string[] = [];

  const SQL_START =
    /^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|EXPLAIN|WITH|BEGIN|COMMIT|ROLLBACK|GRANT|REVOKE)\b/i;
  const SQL_CONTINUE =
    /^\s*(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|CROSS|FULL|NATURAL|ON|AND|OR|NOT|IN|AS|GROUP|ORDER|HAVING|LIMIT|OFFSET|UNION|SET|INTO|VALUES|RETURNING|USING|LATERAL|CASE|WHEN|THEN|ELSE|END|EXISTS|BETWEEN|LIKE|ILIKE|IS|NULL|TABLE|INDEX|VIEW|FUNCTION|CONSTRAINT|PRIMARY|FOREIGN|KEY|REFERENCES|CASCADE|DEFAULT|CHECK|UNIQUE|OVER|PARTITION|FILTER|FETCH|WINDOW|COALESCE|COUNT|SUM|AVG|MIN|MAX|NOW|--|l\.|a\.|c\.|d\.|blocked|blocking|pg_|[),;])/i;

  function flushSQL() {
    if (sqlBuffer.length > 0) {
      const block = sqlBuffer.join("\n").trimEnd();
      if (block.trim()) {
        result.push("```sql");
        result.push(block);
        result.push("```");
      }
      sqlBuffer = [];
    }
  }

  for (const line of lines) {
    if (line.startsWith("```")) {
      flushSQL();
      inCodeBlock = !inCodeBlock;
      result.push(line);
      continue;
    }

    if (inCodeBlock) {
      result.push(line);
      continue;
    }

    const trimmed = line.trim();

    if (sqlBuffer.length > 0) {
      if (
        trimmed === "" ||
        SQL_CONTINUE.test(trimmed) ||
        trimmed.endsWith(";") ||
        trimmed.endsWith(",")
      ) {
        if (trimmed === "" && sqlBuffer.length > 0) {
          const lastLine = sqlBuffer[sqlBuffer.length - 1].trim();
          if (lastLine.endsWith(";")) {
            flushSQL();
            result.push(line);
          } else {
            sqlBuffer.push(line);
          }
        } else {
          sqlBuffer.push(line);
        }
        continue;
      } else {
        flushSQL();
        result.push(line);
        continue;
      }
    }

    if (SQL_START.test(trimmed) && !trimmed.startsWith("-")) {
      sqlBuffer.push(line);
      continue;
    }

    result.push(line);
  }

  flushSQL();
  return result.join("\n");
}

export default function ChatMessageRenderer({
  content,
  compact = false,
  onRunInSandbox,
  onAnalyzeQuery,
  onBlastImpact,
  sandboxResults,
}: Props) {
  const components: Components = useMemo(
    () => ({
      h1: ({ children }) => (
        <h1
          className={`${compact ? "text-sm" : "text-lg"} font-bold text-white mt-5 mb-2 pb-1.5 border-b border-surface-600/40`}
        >
          {children}
        </h1>
      ),
      h2: ({ children }) => (
        <h2
          className={`${compact ? "text-xs" : "text-[15px]"} font-bold text-white mt-4 mb-1.5 flex items-center gap-2`}
        >
          <span className="w-1 h-4 bg-primary-500 rounded-full inline-block flex-shrink-0" />
          {children}
        </h2>
      ),
      h3: ({ children }) => (
        <h3
          className={`${compact ? "text-xs" : "text-sm"} font-semibold text-surface-100 mt-3 mb-1`}
        >
          {children}
        </h3>
      ),
      p: ({ children }) => (
        <p
          className={`${compact ? "text-xs" : "text-sm"} leading-relaxed mb-2 last:mb-0 text-surface-200`}
        >
          {children}
        </p>
      ),
      ul: ({ children }) => (
        <ul
          className={`${compact ? "text-xs" : "text-sm"} space-y-1.5 mb-3 ml-1`}
        >
          {children}
        </ul>
      ),
      ol: ({ children }) => {
        let idx = 0;
        const items = React.Children.map(children, (child) => {
          if (React.isValidElement(child)) {
            idx++;
            return (
              <div className="flex items-start gap-3 mb-3" key={idx}>
                <span className="bg-primary-600/20 text-primary-400 rounded-md w-6 h-6 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 border border-primary-500/20">
                  {idx}
                </span>
                <div className="flex-1 min-w-0">
                  {(child as React.ReactElement<{ children?: React.ReactNode }>).props.children}
                </div>
              </div>
            );
          }
          return child;
        });
        return (
          <div
            className={`${compact ? "text-xs" : "text-sm"} space-y-1 my-3`}
          >
            {items}
          </div>
        );
      },
      li: ({ children }) => (
        <li className="flex items-start gap-2">
          <span className="text-primary-400 mt-1 flex-shrink-0 text-xs">
            ▸
          </span>
          <span className="flex-1">{children}</span>
        </li>
      ),
      strong: ({ children }) => (
        <strong className="font-semibold text-white">{children}</strong>
      ),
      em: ({ children }) => (
        <em className="italic text-surface-200/80">{children}</em>
      ),
      pre: ({ children }) => <>{children}</>,
      code: ({ className, children }) => {
        const codeStr = String(children).replace(/\n$/, "");
        const langMatch = /language-(\w+)/.exec(className || "");
        const language = langMatch?.[1];

        const isBlock =
          !!className || codeStr.includes("\n") || codeStr.length > 80;

        if (!isBlock) {
          return (
            <code className="bg-surface-700/60 text-primary-300 px-1.5 py-0.5 rounded text-[0.85em] font-mono">
              {codeStr}
            </code>
          );
        }

        if (isSQLCode(language, codeStr)) {
          const result = sandboxResults?.get(codeStr.trim());
          return (
            <SQLCodeBlock
              code={codeStr}
              compact={compact}
              onRunInSandbox={onRunInSandbox}
              onAnalyzeQuery={onAnalyzeQuery}
              onBlastImpact={onBlastImpact}
              sandboxResult={result}
            />
          );
        }

        return (
          <GenericCodeBlock
            code={codeStr}
            language={language}
            compact={compact}
          />
        );
      },
      hr: () => <hr className="my-4 border-surface-600/40" />,
      a: ({ href, children }) => (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary-400 hover:text-primary-300 underline underline-offset-2"
        >
          {children}
        </a>
      ),
      table: ({ children }) => (
        <div className="my-3 overflow-x-auto rounded-lg border border-surface-700/80">
          <table className="w-full text-xs">{children}</table>
        </div>
      ),
      thead: ({ children }) => (
        <thead className="bg-surface-800/80">{children}</thead>
      ),
      th: ({ children }) => (
        <th className="px-3 py-2 text-left font-semibold text-surface-100 border-b border-surface-700/50">
          {children}
        </th>
      ),
      td: ({ children }) => (
        <td className="px-3 py-2 text-surface-200 border-b border-surface-700/30">
          {children}
        </td>
      ),
      blockquote: ({ children }) => (
        <blockquote className="border-l-2 border-primary-500/40 pl-3 my-3 text-surface-200/70 italic">
          {children}
        </blockquote>
      ),
    }),
    [compact, onRunInSandbox, onAnalyzeQuery, onBlastImpact, sandboxResults],
  );

  const processed = useMemo(() => preprocessContent(content), [content]);

  return (
    <div className="chat-msg-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {processed}
      </ReactMarkdown>
    </div>
  );
}
