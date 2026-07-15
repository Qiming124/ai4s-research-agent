import type { StructuredMemoryEntry } from "../hooks/useStructuredMemory";
import { getEntryStatus, StatusBadge } from "./TheoremDetailDrawer";
import { MarkdownContent } from "./MarkdownContent";

/** 预览截断：避免在 $ / $$ / \( \) / \[ \] 未闭合处截断 */
function truncateTheoremPreview(body: string, max = 480): string {
  if (body.length <= max) return body;

  // 优先在段落或句号附近截断，减少切开公式的概率
  let cutEnd = max;
  const window = body.slice(0, max);
  const para = window.lastIndexOf("\n\n");
  if (para >= Math.floor(max * 0.55)) cutEnd = para;
  else {
    const sentence = Math.max(
      window.lastIndexOf("。"),
      window.lastIndexOf(". "),
      window.lastIndexOf("；"),
    );
    if (sentence >= Math.floor(max * 0.55)) cutEnd = sentence + 1;
  }

  let cut = body.slice(0, cutEnd);

  const ddCount = (cut.match(/\$\$/g) || []).length;
  if (ddCount % 2 !== 0) {
    const last = cut.lastIndexOf("$$");
    if (last >= 0) cut = cut.slice(0, last);
  }

  const dCount = (cut.match(/(?<!\$)\$(?!\$)/g) || []).length;
  if (dCount % 2 !== 0) {
    const last = cut.lastIndexOf("$");
    if (last >= 0) cut = cut.slice(0, last);
  }

  // \( ... \) / \[ ... \]（模型定理正文常见）
  const parenOpen = (cut.match(/\\\(/g) || []).length;
  const parenClose = (cut.match(/\\\)/g) || []).length;
  if (parenOpen > parenClose) {
    const last = cut.lastIndexOf("\\(");
    if (last >= 0) cut = cut.slice(0, last);
  }

  const bracketOpen = (cut.match(/\\\[/g) || []).length;
  const bracketClose = (cut.match(/\\\]/g) || []).length;
  if (bracketOpen > bracketClose) {
    const last = cut.lastIndexOf("\\[");
    if (last >= 0) cut = cut.slice(0, last);
  }

  cut = cut.trimEnd();
  return cut ? `${cut}\n\n…` : "…";
}

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
            <div className="theorem-body theorem-body-preview">
              <MarkdownContent
                content={truncateTheoremPreview(e.body)}
                className="panel-markdown theorem-preview-md"
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
