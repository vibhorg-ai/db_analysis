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
  /\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|DROP\s+(TABLE|INDEX|VIEW|FUNCTION|TRIGGER|DATABASE|SCHEMA|SEQUENCE)|ALTER\s+(TABLE|INDEX|VIEW|FUNCTION|DATABASE)|TRUNCATE|VACUUM|REINDEX|CLUSTER|pg_cancel_backend|pg_terminate_backend)\b/i;

function isDestructiveSQL(sql: string): boolean {
  return DESTRUCTIVE_PATTERN.test(sql);
}

/** Detect placeholder patterns like <table_name> or <pid_of_blocking_query> that the user should replace. */
function hasPlaceholders(sql: string): boolean {
  return /<[a-zA-Z_][a-zA-Z0-9_]*>/.test(sql);
}

function isSQLCode(language: string | undefined, code: string): boolean {
  if (language && /^(sql|pgsql|plpgsql|postgresql|n1ql|couchbase)$/i.test(language)) return true;
  const hits = (
    code.match(
      /\b(SELECT|FROM|WHERE|JOIN|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TABLE|INDEX|VACUUM|ANALYZE|EXPLAIN|pg_locks|pg_stat_activity|pg_stat_user_tables|pg_class|pg_database|pg_cancel_backend|pg_terminate_backend)\b/gi,
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
    /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|CROSS|FULL|NATURAL|ON|AND|OR|NOT|IN|AS|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET|UNION|ALL|DISTINCT|CASE|WHEN|THEN|ELSE|END|EXISTS|BETWEEN|LIKE|ILIKE|IS|NULL|TRUE|FALSE|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|DROP|ALTER|TRUNCATE|TABLE|INDEX|VIEW|FUNCTION|TRIGGER|CONSTRAINT|PRIMARY|FOREIGN|KEY|REFERENCES|CASCADE|DEFAULT|CHECK|UNIQUE|GRANT|REVOKE|WITH|RECURSIVE|LATERAL|EXPLAIN|ANALYZE|VACUUM|VERBOSE|BEGIN|COMMIT|ROLLBACK|RETURNING|COALESCE|NULLS|LAST|FIRST|ASC|DESC|OVER|PARTITION|USING|NOW|COUNT|SUM|AVG|MIN|MAX|ROUND|CEIL|FLOOR|ABS|UPPER|LOWER|TRIM|SUBSTRING|CAST|EXTRACT|TO_CHAR|TO_DATE|STRING_AGG|ARRAY_AGG|ROW_NUMBER|RANK|DENSE_RANK|INTERVAL)\b/gi,
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
  language,
  compact,
  onRunInSandbox,
  onAnalyzeQuery,
  onBlastImpact,
  sandboxResult,
}: {
  code: string;
  language?: string;
  compact: boolean;
  onRunInSandbox?: (sql: string) => void;
  onAnalyzeQuery?: (sql: string) => void;
  onBlastImpact?: (sql: string) => void;
  sandboxResult?: SandboxResult;
}) {
  const FENCE_LINE = /^\s{0,3}[`~]{3,}\s*\w*\s*$/;
  const cleanCode = useMemo(
    () =>
      code
        .split("\n")
        .filter((line) => !FENCE_LINE.test(line.trimEnd()))
        .join("\n")
        .trim(),
    [code],
  );
  const destructive = isDestructiveSQL(cleanCode);
  const withPlaceholders = hasPlaceholders(cleanCode);
  const highlighted = useMemo(() => highlightSQL(cleanCode), [cleanCode]);
  const [copied, setCopied] = React.useState(false);

  function copy() {
    navigator.clipboard.writeText(cleanCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const showRunInSandbox = onRunInSandbox && !destructive;
  const showActions = showRunInSandbox || onAnalyzeQuery || (destructive && onBlastImpact);

  return (
    <div className="my-3 rounded-lg overflow-hidden border border-surface-700/80 bg-[#0c1222]">
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface-800/90 border-b border-surface-700/60">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-primary-400/70 uppercase tracking-widest font-semibold">
            {language && /n1ql|couchbase/i.test(language) ? "N1QL" : "SQL"}
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

      {withPlaceholders && (
        <p className="text-[10px] text-amber-400/90 px-3 py-1 bg-amber-500/5 border-t border-surface-700/50">
          Replace placeholders (e.g. &lt;table_name&gt;, &lt;pid&gt;) with real values before running.
        </p>
      )}

      {showActions && (
        <div className="flex items-center gap-2 px-3 py-2 bg-surface-800/40 border-t border-surface-700/50">
          {showRunInSandbox && (
            <button
              type="button"
              className="chat-action-btn text-blue-400 bg-blue-500/10 border-blue-500/25 hover:bg-blue-500/20"
              onClick={() => onRunInSandbox(cleanCode)}
              title={withPlaceholders ? "Replace placeholders first" : "Execute read-only in sandbox"}
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
              onClick={() => onAnalyzeQuery(cleanCode)}
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
              onClick={() => onBlastImpact(cleanCode)}
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

/* ─── Segment-based content preprocessor ─────────────────────────────────────
 *
 * Phase 1: Parse raw LLM output into typed segments (text | code block).
 * Phase 2: Scan text segments for unfenced SQL and wrap them.
 * Phase 3: Merge adjacent SQL code-block segments that belong together.
 * Phase 4: Reconstruct markdown.
 *
 * This replaces the previous line-by-line approach which was brittle when
 * LLMs split a single SQL statement across multiple fenced blocks.
 * ──────────────────────────────────────────────────────────────────────────── */

interface Segment {
  kind: "text" | "code";
  content: string;
  lang: string;
}

const SQL_LANG_RE = /^(sql|pgsql|plpgsql|postgresql|n1ql|couchbase)$/i;

function isSegmentSQL(seg: Segment): boolean {
  if (seg.kind !== "code") return false;
  if (SQL_LANG_RE.test(seg.lang)) return true;
  return isSQLCode(seg.lang || undefined, seg.content);
}

function parseSegments(raw: string): Segment[] {
  const lines = raw.split("\n");
  const segments: Segment[] = [];
  let textBuf: string[] = [];
  let codeBuf: string[] = [];
  let codeLang = "";
  let inCode = false;
  let openFence = "";

  function flushText() {
    if (textBuf.length) {
      segments.push({ kind: "text", content: textBuf.join("\n"), lang: "" });
      textBuf = [];
    }
  }
  function flushCode() {
    segments.push({ kind: "code", content: codeBuf.join("\n"), lang: codeLang });
    codeBuf = [];
    codeLang = "";
    inCode = false;
    openFence = "";
  }

  for (const line of lines) {
    const trimmed = line.trimEnd();

    if (inCode) {
      if (isClosingFence(trimmed, openFence)) {
        flushCode();
      } else {
        // Handle closing fence appended to a code line (e.g., "DESC;```")
        const inlineFence = line.match(/^(.+?)(`{3,}|~{3,})\s*$/);
        if (inlineFence && inlineFence[2][0] === openFence[0] && inlineFence[2].length >= openFence.length) {
          codeBuf.push(inlineFence[1]);
          flushCode();
        } else {
          codeBuf.push(line);
        }
      }
      continue;
    }

    const fenceMatch = trimmed.match(/^\s{0,3}(`{3,}|~{3,})\s*(\S*)\s*$/);
    if (fenceMatch) {
      flushText();
      openFence = fenceMatch[1];
      codeLang = fenceMatch[2] || "";
      inCode = true;
      continue;
    }

    textBuf.push(line);
  }

  if (inCode) flushCode();
  flushText();
  return segments;
}

function isClosingFence(line: string, openFence: string): boolean {
  const ch = openFence[0];
  const minLen = openFence.length;
  // Allow 0-3 leading spaces (CommonMark spec) and optional trailing language tag (LLM quirk)
  const re = ch === "`" ? /^\s{0,3}`{3,}\s*\w*\s*$/ : /^\s{0,3}~{3,}\s*\w*\s*$/;
  if (!re.test(line)) return false;
  const stripped = line.replace(/^\s+/, "");
  const count = stripped.match(ch === "`" ? /^`+/ : /^~+/)![0].length;
  return count >= minLen;
}

function wrapUnfencedSQL(text: string): Segment[] {
  const lines = text.split("\n");
  const out: Segment[] = [];
  let textBuf: string[] = [];
  let sqlBuf: string[] = [];

  const SQL_START =
    /^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|EXPLAIN|WITH|BEGIN|COMMIT|ROLLBACK|GRANT|REVOKE|VACUUM|ANALYZE)\b/i;

  function isContinuation(line: string): boolean {
    const t = line.trim();
    if (!t) return false;
    if (/^\s*(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|CROSS|FULL|NATURAL|ON|AND|OR|NOT|IN|AS|GROUP|ORDER|HAVING|LIMIT|OFFSET|UNION|ALL|DISTINCT|SET|INTO|VALUES|RETURNING|USING|LATERAL|CASE|WHEN|THEN|ELSE|END|EXISTS|BETWEEN|LIKE|ILIKE|IS|NULL|TRUE|FALSE|TABLE|INDEX|VIEW|FUNCTION|CONSTRAINT|PRIMARY|FOREIGN|KEY|REFERENCES|CASCADE|DEFAULT|CHECK|UNIQUE|OVER|PARTITION|FILTER|FETCH|WINDOW|VACUUM|ANALYZE|VERBOSE|REINDEX|CLUSTER|REFRESH|MATERIALIZED|RECURSIVE|RAISE|PERFORM|DECLARE|IF|ELSIF|LOOP|FOR|WHILE|RETURN|RETURNS|LANGUAGE|DO|EXECUTE|COMMENT|COPY|CALL|MERGE)\b/i.test(t)) return true;
    if (/^\s*(--|pg_|[),;])/.test(t)) return true;
    if (/^(\s{2,}|\s*[A-Z_][A-Z0-9_]*\s*\(|\s*\(|\s*\)|\s*,|\s*\|\||\s*::|.*;\s*$)/i.test(line)) return true;
    if (/^\s*[a-z_][a-z0-9_.]*\s*,?\s*$/i.test(t)) return true;
    return false;
  }

  function flushText() {
    if (textBuf.length) {
      out.push({ kind: "text", content: textBuf.join("\n"), lang: "" });
      textBuf = [];
    }
  }
  function flushSQL() {
    if (sqlBuf.length) {
      const block = sqlBuf.join("\n").trimEnd();
      if (block.trim()) {
        out.push({ kind: "code", content: block, lang: "sql" });
      }
      sqlBuf = [];
    }
  }

  for (const line of lines) {
    const trimmed = line.trim();

    if (sqlBuf.length > 0) {
      if (trimmed === "") {
        const lastLine = sqlBuf[sqlBuf.length - 1].trim();
        if (lastLine.endsWith(";")) { flushSQL(); textBuf.push(line); }
        else { sqlBuf.push(line); }
        continue;
      }
      if (isContinuation(line) || trimmed.endsWith(";") || trimmed.endsWith(",")) {
        sqlBuf.push(line);
        continue;
      }
      flushSQL();
      textBuf.push(line);
      continue;
    }

    if (SQL_START.test(trimmed) && !trimmed.startsWith("-")) {
      flushText();
      sqlBuf.push(line);
      continue;
    }

    textBuf.push(line);
  }

  flushSQL();
  flushText();
  return out;
}

function mergeAdjacentSQL(segments: Segment[]): Segment[] {
  const result: Segment[] = [];

  for (const seg of segments) {
    if (!isSegmentSQL(seg)) {
      result.push(seg);
      continue;
    }

    let mergeTarget = -1;
    for (let k = result.length - 1; k >= 0; k--) {
      const prev = result[k];
      if (prev.kind === "code" && isSegmentSQL(prev)) {
        mergeTarget = k;
        break;
      }
      if (prev.kind === "text") {
        const t = prev.content.trim();
        if (t === "" || t === "..." || t === "---" || t === "***") continue;
        break;
      }
      break;
    }

    if (mergeTarget >= 0) {
      const prevSQL = result[mergeTarget];
      const prevTrimmed = prevSQL.content.trimEnd();
      const lastLine = prevTrimmed.split("\n").pop()?.trim() ?? "";

      const onlyComments = prevTrimmed
        .split("\n")
        .every((l) => { const s = l.trim(); return s === "" || s.startsWith("--") || s.startsWith("/*"); });

      const firstNextLine = seg.content.trimStart().split("\n")[0]?.trim() ?? "";
      const nextStartsContinuation =
        /^(SELECT|FROM|WHERE|JOIN|AND|OR|ORDER|GROUP|HAVING|LIMIT|UNION|SET|RETURNING|EXPLAIN|WITH|INTO|VALUES|ON|LEFT|RIGHT|INNER|OUTER|CROSS|FULL|NATURAL|USING|LATERAL|CASE|WHEN)\b/i.test(firstNextLine);

      const shouldMerge =
        !lastLine.endsWith(";") ||
        onlyComments ||
        nextStartsContinuation;

      if (shouldMerge) {
        prevSQL.content = prevSQL.content + "\n" + seg.content;
        // remove any trivial separator text between them
        while (result.length > mergeTarget + 1) result.pop();
        continue;
      }
    }

    result.push(seg);
  }

  return result;
}

function preprocessContent(raw: string): string {
  if (!raw) return raw;

  const parsed = parseSegments(raw);

  const expanded = parsed.flatMap((seg) =>
    seg.kind === "text" ? wrapUnfencedSQL(seg.content) : [seg],
  );

  const merged = mergeAdjacentSQL(expanded);

  return merged
    .map((seg) => {
      if (seg.kind === "code") return "```" + seg.lang + "\n" + seg.content + "\n```";
      return seg.content;
    })
    .join("\n");
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
        const FENCE_LINE = /^\s{0,3}[`~]{3,}\s*\w*\s*$/;
        const codeStr = String(children ?? "")
          .replace(/\n$/, "")
          .split("\n")
          .filter((line) => !FENCE_LINE.test(line.trimEnd()))
          .join("\n")
          .trim();
        if (!codeStr) return null;

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
              language={language}
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
