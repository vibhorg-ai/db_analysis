import { useEffect, useState, useMemo } from "react";
import { useAppContext } from "../context/AppContext.tsx";
import type { TableMeta } from "../context/AppContext.tsx";

const NODE_WIDTH = 160;
const NODE_HEIGHT = 52;
const GRID_GAP = 24;
const ARROW_SIZE = 6;

function getNodeColor(relCount: number, maxRel: number): string {
  if (maxRel === 0) return "fill-surface-700";
  const intensity = relCount / maxRel;
  if (intensity > 0.7) return "fill-primary-500";
  if (intensity > 0.4) return "fill-primary-600";
  if (intensity > 0.2) return "fill-primary-700";
  return "fill-surface-700";
}

function computeLayout(tables: TableMeta[]): Map<string, { x: number; y: number }> {
  const cols = Math.ceil(Math.sqrt(tables.length));
  const layout = new Map<string, { x: number; y: number }>();
  tables.forEach((t, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    layout.set(t.table_name, {
      x: col * (NODE_WIDTH + GRID_GAP) + GRID_GAP,
      y: row * (NODE_HEIGHT + GRID_GAP) + GRID_GAP,
    });
  });
  return layout;
}

function getRelCount(tables: TableMeta[], tableName: string): number {
  const table = tables.find((t) => t.table_name === tableName);
  if (!table) return 0;
  let count = table.foreign_keys?.length ?? 0;
  tables.forEach((t) => {
    const incoming = t.foreign_keys?.filter((fk) => fk.references_table === tableName) ?? [];
    count += incoming.length;
  });
  return count;
}

export default function GraphPage() {
  const { connections, schemaMap, fetchSchemaIfNeeded, activeConnectionId, setActiveConnectionId } = useAppContext();
  const [selectedConnId, setSelectedConnId] = useState<string | null>(activeConnectionId);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTable, setSelectedTable] = useState<TableMeta | null>(null);

  const effectiveConnId = selectedConnId || activeConnectionId || (connections.length > 0 ? connections[0].id : null);
  const tables: TableMeta[] = effectiveConnId ? (schemaMap[effectiveConnId] ?? []) : [];

  useEffect(() => {
    if (!effectiveConnId) return;
    setLoading(true);
    setError(null);
    fetchSchemaIfNeeded(effectiveConnId)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load schema"))
      .finally(() => setLoading(false));
  }, [effectiveConnId, fetchSchemaIfNeeded]);

  const handleConnChange = (connId: string) => {
    setSelectedConnId(connId);
    setActiveConnectionId(connId);
    setSelectedTable(null);
  };

  const layout = useMemo(() => computeLayout(tables), [tables]);
  const maxRel = useMemo(() => Math.max(...tables.map((t) => getRelCount(tables, t.table_name)), 1), [tables]);

  const selectedConn = connections.find((c) => c.id === effectiveConnId);

  if (loading) {
    return (
      <div className="p-8">
        <h1 className="text-2xl font-bold text-white tracking-tight mb-6">Knowledge Graph</h1>
        <div className="card flex items-center justify-center min-h-[300px]">
          <p className="text-surface-400">Loading schema...</p>
        </div>
      </div>
    );
  }

  if (tables.length === 0 && !error) {
    return (
      <div className="p-8">
        <h1 className="text-2xl font-bold text-white tracking-tight mb-6">Knowledge Graph</h1>
        {connections.length > 1 && (
          <div className="mb-4">
            <select
              value={effectiveConnId ?? ""}
              onChange={(e) => handleConnChange(e.target.value)}
              className="input-field max-w-xs"
            >
              {connections.map((c) => (
                <option key={c.id} value={c.id}>{c.name} ({c.engine})</option>
              ))}
            </select>
          </div>
        )}
        <div className="card flex items-center justify-center min-h-[300px]">
          <p className="text-surface-400">
            Connect to a database and load schema to view the knowledge graph.
          </p>
        </div>
      </div>
    );
  }

  const svgWidth = Math.max(400, ...Array.from(layout.values()).map((p) => p.x + NODE_WIDTH + GRID_GAP));
  const svgHeight = Math.max(300, ...Array.from(layout.values()).map((p) => p.y + NODE_HEIGHT + GRID_GAP));

  return (
    <div className="p-8 flex gap-6 h-[calc(100vh-4rem)]">
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex items-center gap-4 mb-4">
          <h1 className="text-2xl font-bold text-white tracking-tight">Knowledge Graph</h1>
          {connections.length > 1 && (
            <select
              value={effectiveConnId ?? ""}
              onChange={(e) => handleConnChange(e.target.value)}
              className="input-field max-w-[220px] text-sm py-1.5"
            >
              {connections.map((c) => (
                <option key={c.id} value={c.id}>{c.name} ({c.engine})</option>
              ))}
            </select>
          )}
          {selectedConn && (
            <span className="text-xs text-surface-400">{tables.length} tables</span>
          )}
        </div>
        <div className="card flex-1 overflow-auto p-4">
          <svg width="100%" height="100%" viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="min-h-[400px]">
            {tables.flatMap((table) =>
              (table.foreign_keys ?? []).map((fk) => {
                const fromPos = layout.get(table.table_name);
                const toPos = layout.get(fk.references_table);
                if (!fromPos || !toPos) return null;
                const fromX = fromPos.x + NODE_WIDTH / 2;
                const fromY = fromPos.y + NODE_HEIGHT;
                const toX = toPos.x + NODE_WIDTH / 2;
                const toY = toPos.y;
                const midY = (fromY + toY) / 2;
                const path = `M ${fromX} ${fromY} L ${fromX} ${midY} L ${toX} ${midY} L ${toX} ${toY}`;
                return (
                  <g key={`${table.table_name}-${fk.column}-${fk.references_table}`}>
                    <path d={path} fill="none" stroke="currentColor" strokeWidth={1.5} className="text-surface-500" />
                    <polygon points={`${toX},${toY} ${toX - ARROW_SIZE},${toY + ARROW_SIZE * 2} ${toX + ARROW_SIZE},${toY + ARROW_SIZE * 2}`} className="fill-surface-500" />
                  </g>
                );
              })
            )}
            {tables.map((table) => {
              const pos = layout.get(table.table_name);
              if (!pos) return null;
              const relCount = getRelCount(tables, table.table_name);
              const isSelected = selectedTable?.table_name === table.table_name;
              return (
                <g key={table.table_name} onClick={() => setSelectedTable(table)} className="cursor-pointer">
                  <rect x={pos.x} y={pos.y} width={NODE_WIDTH} height={NODE_HEIGHT} rx={8} className={`${getNodeColor(relCount, maxRel)} ${isSelected ? "stroke-primary-400 stroke-2" : "stroke-surface-600"}`} />
                  <text x={pos.x + NODE_WIDTH / 2} y={pos.y + 20} textAnchor="middle" className="fill-white text-sm font-medium">{table.table_name}</text>
                  <text x={pos.x + NODE_WIDTH / 2} y={pos.y + 38} textAnchor="middle" className="fill-surface-400 text-xs">{table.columns?.length ?? 0} columns</text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      <div className="w-80 shrink-0">
        <h2 className="text-sm font-medium text-surface-400 uppercase tracking-wider mb-4">Table Details</h2>
        <div className="card min-h-[200px] overflow-y-auto max-h-[calc(100vh-12rem)]">
          {selectedTable ? (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-semibold text-white">{selectedTable.table_name}</h3>
                <p className="text-surface-400 text-sm mt-1">{selectedTable.columns?.length ?? 0} columns, {selectedTable.foreign_keys?.length ?? 0} foreign keys</p>
              </div>
              {selectedTable.primary_keys && selectedTable.primary_keys.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-surface-500 uppercase mb-2">Primary Keys</h4>
                  <ul className="space-y-1">{selectedTable.primary_keys.map((pk) => (<li key={pk} className="text-sm text-white font-mono">{pk}</li>))}</ul>
                </div>
              )}
              {selectedTable.columns && selectedTable.columns.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-surface-500 uppercase mb-2">Columns</h4>
                  <ul className="space-y-1.5">
                    {selectedTable.columns.map((col) => (
                      <li key={col.column_name} className="text-sm">
                        <span className="font-mono text-white">{col.column_name}</span>
                        <span className="text-surface-500 ml-2">{col.data_type}</span>
                        {col.is_nullable === "NO" && <span className="badge-yellow ml-2">NOT NULL</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {selectedTable.foreign_keys && selectedTable.foreign_keys.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-surface-500 uppercase mb-2">Foreign Keys</h4>
                  <ul className="space-y-1.5">
                    {selectedTable.foreign_keys.map((fk, i) => (
                      <li key={i} className="text-sm text-surface-300">
                        <span className="font-mono text-white">{fk.column}</span>{" "}
                        <span className="text-surface-500">references</span>{" "}
                        <span className="font-mono text-primary-400">{fk.references_table}.{fk.references_column}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <p className="text-surface-500 text-sm">Click a table node to view details.</p>
          )}
        </div>
      </div>
    </div>
  );
}
