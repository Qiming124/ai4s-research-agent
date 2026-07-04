import { MarkdownContent } from "./MarkdownContent";

interface TheoryAssetsPanelProps {
  symbols: string;
  assumptions: string;
  matrix: string;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function TheoryAssetsPanel({
  symbols,
  assumptions,
  matrix,
  loading,
  error,
  onRefresh,
}: TheoryAssetsPanelProps) {
  return (
    <div className="theory-assets-panel">
      <div className="panel-header">
        <h4>符号与假设</h4>
        <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
          刷新
        </button>
      </div>
      {error && <p className="panel-error">{error}</p>}
      {loading && <p className="panel-muted">加载中…</p>}
      {symbols && (
        <details open>
          <summary>符号表</summary>
          <MarkdownContent content={symbols} className="panel-markdown workspace-content" />
        </details>
      )}
      {assumptions && (
        <details>
          <summary>假设列表</summary>
          <MarkdownContent content={assumptions} className="panel-markdown workspace-content" />
        </details>
      )}
      {matrix && (
        <details>
          <summary>假设矩阵</summary>
          <MarkdownContent content={matrix} className="panel-markdown workspace-content" />
        </details>
      )}
    </div>
  );
}
