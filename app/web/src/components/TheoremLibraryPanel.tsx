import type { StructuredMemoryEntry } from "../hooks/useStructuredMemory";
import { getEntryStatus, StatusBadge } from "./TheoremDetailDrawer";

interface TheoremLibraryPanelProps {
  entries: StructuredMemoryEntry[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onSelect?: (entry: StructuredMemoryEntry) => void;
}

export function TheoremLibraryPanel({
  entries,
  loading,
  error,
  onRefresh,
  onSelect,
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
        <p className="panel-muted">暂无定理/引理。请使用 Math 模式或 Theory Agent，回答需含 <code>## 引理 1</code> / <code>## 定理 1</code> 标题。</p>
      )}
      <ul className="theorem-list">
        {entries.map((e) => (
          <li
            key={e.id}
            className="theorem-item clickable"
            onClick={() => onSelect?.(e)}
            onKeyDown={(ev) => ev.key === "Enter" && onSelect?.(e)}
            role="button"
            tabIndex={0}
          >
            <div className="theorem-item-head">
              <span className="theorem-kind">{e.kind}</span>
              <StatusBadge status={getEntryStatus(e)} />
            </div>
            <strong>{e.title || `条目 #${e.id}`}</strong>
            <p className="theorem-body">
              {e.body.slice(0, 200)}
              {e.body.length > 200 ? "…" : ""}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
