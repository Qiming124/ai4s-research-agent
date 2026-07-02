import type { WorkspaceFile } from "../hooks/useWorkspaceFiles";

interface WorkspacePanelProps {
  files: WorkspaceFile[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function WorkspacePanel({
  files,
  loading,
  error,
  onRefresh,
}: WorkspacePanelProps) {
  return (
    <div className="workspace-panel">
      <div className="panel-header">
        <h4>理论工作区</h4>
        <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
          刷新
        </button>
      </div>
      {error && <p className="panel-error">{error}</p>}
      {loading && <p className="panel-muted">加载中…</p>}
      <ul className="workspace-file-list">
        {files.map((f) => (
          <li key={f.path}>{f.path}</li>
        ))}
      </ul>
    </div>
  );
}
