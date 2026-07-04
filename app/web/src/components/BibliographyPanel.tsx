import type { BibEntry } from "../hooks/useBibliography";

interface BibliographyPanelProps {
  entries: BibEntry[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onExportBib: () => Promise<void>;
}

export function BibliographyPanel({
  entries,
  loading,
  error,
  onRefresh,
  onExportBib,
}: BibliographyPanelProps) {
  return (
    <div className="bibliography-panel">
      <div className="panel-header">
        <h4>书目库</h4>
        <div className="panel-header-actions">
          <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
            刷新
          </button>
          <button type="button" className="btn-small" onClick={() => void onExportBib()}>
            导出 .bib
          </button>
        </div>
      </div>
      {error && <p className="panel-error">{error}</p>}
      {loading && <p className="panel-muted">加载中…</p>}
      {entries.length === 0 && !loading && (
        <p className="panel-muted">暂无书目；文献入库后自动收录。</p>
      )}
      <ul className="bib-list">
        {entries.map((e) => (
          <li key={e.id} className="bib-item">
            <strong>{e.title || e.id}</strong>
            <span className="bib-meta">
              {e.authors} {e.year} {e.arxiv_id ? `arXiv:${e.arxiv_id}` : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
