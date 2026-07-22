import { useState } from "react";
import type { ProjectInfo } from "../hooks/useProjects";

interface ProjectHubProps {
  projects: ProjectInfo[];
  currentProjectId: string;
  onSelect: (id: string) => void;
  onCreate?: (name: string, description: string) => Promise<void>;
  disabled?: boolean;
  error?: string | null;
  linkStatus?: string | null;
  members?: { user_id: string; role: string }[];
}

export function ProjectHub({
  projects,
  currentProjectId,
  onSelect,
  onCreate,
  disabled,
  error,
  linkStatus,
  members = [],
}: ProjectHubProps) {
  const current = projects.find((p) => p.id === currentProjectId);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!onCreate || !name.trim()) return;
    setCreating(true);
    setFormError(null);
    try {
      await onCreate(name, description);
      setName("");
      setDescription("");
      setShowForm(false);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "创建失败");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="project-hub">
      <div className="panel-header">
        <h3 className="sidebar-title">课题</h3>
        {onCreate && (
          <button
            type="button"
            className="btn-small"
            disabled={disabled || creating}
            onClick={() => {
              setShowForm((v) => !v);
              setFormError(null);
            }}
          >
            {showForm ? "取消" : "+ 新建"}
          </button>
        )}
      </div>

      {error && <p className="panel-error">{error}</p>}
      {linkStatus && <p className="panel-muted project-link-status">{linkStatus}</p>}

      {showForm && onCreate && (
        <div className="inline-form">
          <input
            className="inline-form-input"
            placeholder="课题名称（必填）"
            value={name}
            disabled={creating}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            className="inline-form-input"
            placeholder="简介（可选）"
            value={description}
            disabled={creating}
            onChange={(e) => setDescription(e.target.value)}
          />
          {formError && <p className="panel-error">{formError}</p>}
          <button
            type="button"
            className="btn-small btn-primary"
            disabled={creating || !name.trim()}
            onClick={handleCreate}
          >
            {creating ? "创建中…" : "创建课题"}
          </button>
        </div>
      )}

      <select
        className="project-select"
        value={currentProjectId}
        disabled={disabled}
        onChange={(e) => onSelect(e.target.value)}
        aria-label="选择课题"
      >
        {projects.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
        {projects.length === 0 && <option value="default">默认课题</option>}
      </select>
      {current?.description && (
        <p className="project-desc">{current.description}</p>
      )}
      <div className="project-roles-hint">
        {(members.length ? members : [
          { user_id: "owner", role: "pi" },
          { user_id: "theorist", role: "theorist" },
        ]).map((m) => (
          <span key={`${m.user_id}-${m.role}`} className="role-tag">
            {m.role}
          </span>
        ))}
      </div>
    </div>
  );
}
