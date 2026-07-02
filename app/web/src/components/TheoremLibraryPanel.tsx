import type { StructuredMemoryEntry } from "../hooks/useStructuredMemory";

interface TheoremLibraryPanelProps {
  entries: StructuredMemoryEntry[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function TheoremLibraryPanel({
  entries,
  loading,
  error,
  onRefresh,
}: TheoremLibraryPanelProps) {
  return (
    <div className="theorem-library-panel">
      <div className="panel-header">
        <h4>定理库 (L4)</h4>
        <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
          刷新
        </button>
      </div>
      {error && <p className="panel-error">{error}</p>}
      {loading && <p className="panel-muted">加载中…</p>}
      {!loading && entries.length === 0 && (
        <p className="panel-muted">暂无定理/引理；Theory 推导后会自动抽取。</p>
      )}
      <ul className="theorem-list">
        {entries.map((e) => (
          <li key={e.id} className="theorem-item">
            <span className="theorem-kind">{e.kind}</span>
            <strong>{e.title || `条目 #${e.id}`}</strong>
            <p className="theorem-body">{e.body.slice(0, 200)}{e.body.length > 200 ? "…" : ""}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
