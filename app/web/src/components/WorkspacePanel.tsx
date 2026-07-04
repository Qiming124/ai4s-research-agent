import { useState } from "react";
import type { WorkspaceFile } from "../hooks/useWorkspaceFiles";
import { MarkdownContent } from "./MarkdownContent";

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
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [fileLoading, setFileLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  const loadFile = async (path: string) => {
    setSelectedPath(path);
    setFileLoading(true);
    setEditing(false);
    setSaveMsg(null);
    try {
      const res = await fetch(`/v1/theory/workspace/${path}`);
      if (res.ok) {
        setContent(await res.text());
      } else {
        setContent(`加载失败: HTTP ${res.status}`);
      }
    } catch (err) {
      setContent(err instanceof Error ? err.message : "加载失败");
    } finally {
      setFileLoading(false);
    }
  };

  const saveFile = async () => {
    if (!selectedPath) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      const res = await fetch(`/v1/theory/workspace/${selectedPath}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSaveMsg("已保存");
      setEditing(false);
      onRefresh();
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

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
          <li key={f.path}>
            <button type="button" className="btn-link" onClick={() => loadFile(f.path)}>
              {f.path}
            </button>
          </li>
        ))}
      </ul>
      {selectedPath && (
        <div className="workspace-preview">
          <div className="panel-header">
            <h5>{selectedPath}</h5>
            <div className="panel-header-actions">
              <button
                type="button"
                className="btn-small"
                onClick={() => setEditing((v) => !v)}
                disabled={fileLoading}
              >
                {editing ? "预览" : "编辑"}
              </button>
              {editing && (
                <button
                  type="button"
                  className="btn-small btn-primary"
                  onClick={() => void saveFile()}
                  disabled={saving}
                >
                  {saving ? "保存中…" : "保存"}
                </button>
              )}
            </div>
          </div>
          {saveMsg && <p className="panel-muted">{saveMsg}</p>}
          {fileLoading ? (
            <p className="panel-muted">加载文件…</p>
          ) : editing ? (
            <textarea
              className="doc-content-input"
              rows={8}
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
          ) : (
            <MarkdownContent content={content} className="panel-markdown workspace-content" />
          )}
        </div>
      )}
    </div>
  );
}
