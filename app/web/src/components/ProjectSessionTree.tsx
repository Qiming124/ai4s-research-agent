import { useMemo, useState } from "react";
import type { ProjectInfo } from "../hooks/useProjects";
import type { SessionMeta } from "../utils/session";
import { shortSessionId } from "../utils/session";

interface ProjectSessionTreeProps {
  projects: ProjectInfo[];
  sessions: SessionMeta[];
  currentProjectId: string;
  currentSessionId: string;
  disabled?: boolean;
  onSelectSession: (sessionId: string, projectId: string) => void;
  onNewSession: (projectId: string) => void;
  onRemoveSession?: (sessionId: string) => void;
  onCreateProject: (name: string, description?: string) => Promise<void>;
  onUpdateProject: (projectId: string, patch: { name?: string; description?: string }) => Promise<void>;
  onDeleteProject: (projectId: string) => Promise<void>;
  onMoveSession: (sessionId: string, projectId: string) => Promise<void>;
  onUpdateSessionTitle: (sessionId: string, title: string) => void;
}

export function ProjectSessionTree({
  projects,
  sessions,
  currentProjectId,
  currentSessionId,
  disabled = false,
  onSelectSession,
  onNewSession,
  onRemoveSession,
  onCreateProject,
  onUpdateProject,
  onDeleteProject,
  onMoveSession,
  onUpdateSessionTitle,
}: ProjectSessionTreeProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => ({
    [currentProjectId]: true,
  }));
  const [focusProjectId, setFocusProjectId] = useState(currentProjectId);
  const [showNewProject, setShowNewProject] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [editProjectId, setEditProjectId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editSessionId, setEditSessionId] = useState<string | null>(null);
  const [editSessionTitle, setEditSessionTitle] = useState("");
  const [editSessionProject, setEditSessionProject] = useState("default");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const grouped = useMemo(() => {
    const map = new Map<string, SessionMeta[]>();
    for (const p of projects) map.set(p.id, []);
    for (const s of sessions) {
      const pid = s.projectId || "default";
      if (!map.has(pid)) map.set(pid, []);
      map.get(pid)!.push(s);
    }
    for (const list of map.values()) {
      list.sort((a, b) => b.updatedAt - a.updatedAt);
    }
    return map;
  }, [projects, sessions]);

  const toggle = (pid: string) => {
    setExpanded((prev) => ({ ...prev, [pid]: !prev[pid] }));
    setFocusProjectId(pid);
  };

  const startEditProject = (p: ProjectInfo) => {
    setEditProjectId(p.id);
    setEditName(p.name);
    setEditDesc(p.description || "");
    setFormError(null);
  };

  const startEditSession = (s: SessionMeta) => {
    setEditSessionId(s.id);
    setEditSessionTitle(s.title);
    setEditSessionProject(s.projectId || "default");
    setFormError(null);
  };

  return (
    <div className="project-session-tree" aria-label="课题与会话">
      <div className="session-sidebar-head">
        <h2>会话</h2>
        <div className="tree-head-actions">
          <button
            type="button"
            className="btn-small"
            disabled={disabled || busy}
            onClick={() => {
              setShowNewProject((v) => !v);
              setFormError(null);
            }}
          >
            {showNewProject ? "取消" : "+ 课题"}
          </button>
          <button
            type="button"
            className="btn-new-session"
            disabled={disabled || busy}
            onClick={() => onNewSession(focusProjectId || currentProjectId)}
            title="在当前课题下新建会话"
          >
            + 会话
          </button>
        </div>
      </div>

      {showNewProject && (
        <div className="inline-form">
          <input
            className="inline-form-input"
            placeholder="课题名称"
            value={newName}
            disabled={busy}
            onChange={(e) => setNewName(e.target.value)}
          />
          <input
            className="inline-form-input"
            placeholder="简介（可选）"
            value={newDesc}
            disabled={busy}
            onChange={(e) => setNewDesc(e.target.value)}
          />
          {formError && <p className="panel-error">{formError}</p>}
          <button
            type="button"
            className="btn-small btn-primary"
            disabled={busy || !newName.trim()}
            onClick={async () => {
              setBusy(true);
              setFormError(null);
              try {
                await onCreateProject(newName, newDesc);
                setNewName("");
                setNewDesc("");
                setShowNewProject(false);
              } catch (err) {
                setFormError(err instanceof Error ? err.message : "创建失败");
              } finally {
                setBusy(false);
              }
            }}
          >
            创建课题
          </button>
        </div>
      )}

      <ul className="project-tree-list">
        {projects.map((project) => {
          const open = expanded[project.id] ?? project.id === currentProjectId;
          const kids = grouped.get(project.id) ?? [];
          return (
            <li key={project.id} className="project-tree-folder">
              <div
                className={
                  project.id === currentProjectId
                    ? "project-tree-row active"
                    : "project-tree-row"
                }
              >
                <button
                  type="button"
                  className="project-tree-toggle"
                  onClick={() => toggle(project.id)}
                  aria-expanded={open}
                >
                  {open ? "▾" : "▸"}
                </button>
                <button
                  type="button"
                  className="project-tree-name"
                  onClick={() => {
                    setFocusProjectId(project.id);
                    setExpanded((prev) => ({ ...prev, [project.id]: true }));
                  }}
                >
                  <span className="project-folder-label">{project.name}</span>
                  <span className="project-folder-count">{kids.length}</span>
                </button>
                <button
                  type="button"
                  className="btn-small"
                  disabled={disabled}
                  onClick={() => startEditProject(project)}
                  title="课题属性"
                >
                  属性
                </button>
              </div>

              {open && editProjectId === project.id && (
                <div className="inline-form tree-edit-panel">
                  <input
                    className="inline-form-input"
                    value={editName}
                    disabled={busy}
                    onChange={(e) => setEditName(e.target.value)}
                  />
                  <input
                    className="inline-form-input"
                    value={editDesc}
                    disabled={busy}
                    onChange={(e) => setEditDesc(e.target.value)}
                    placeholder="简介"
                  />
                  {formError && <p className="panel-error">{formError}</p>}
                  <div className="tree-edit-actions">
                    <button
                      type="button"
                      className="btn-small btn-primary"
                      disabled={busy || !editName.trim()}
                      onClick={async () => {
                        setBusy(true);
                        setFormError(null);
                        try {
                          await onUpdateProject(project.id, {
                            name: editName.trim(),
                            description: editDesc,
                          });
                          setEditProjectId(null);
                        } catch (err) {
                          setFormError(err instanceof Error ? err.message : "保存失败");
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      保存
                    </button>
                    <button
                      type="button"
                      className="btn-small"
                      disabled={busy}
                      onClick={() => setEditProjectId(null)}
                    >
                      取消
                    </button>
                    {project.id !== "default" && (
                      <button
                        type="button"
                        className="btn-small btn-danger"
                        disabled={busy}
                        title="整包删除课题、会话与文件"
                        onClick={async () => {
                          const kids = grouped.get(project.id) ?? [];
                          const ok = window.confirm(
                            `确定删除课题「${project.name}」？\n\n将永久删除：\n· 课题下 ${kids.length} 个会话\n· 工作区文件\n\n此操作不可恢复。`,
                          );
                          if (!ok) return;
                          setBusy(true);
                          setFormError(null);
                          try {
                            await onDeleteProject(project.id);
                            setEditProjectId(null);
                          } catch (err) {
                            setFormError(err instanceof Error ? err.message : "删除失败");
                          } finally {
                            setBusy(false);
                          }
                        }}
                      >
                        删除课题
                      </button>
                    )}
                  </div>
                </div>
              )}

              {open && (
                <ul className="session-list session-list--nested">
                  {kids.length === 0 && (
                    <li className="session-empty">暂无会话</li>
                  )}
                  {kids.map((session) => {
                    const active = session.id === currentSessionId;
                    return (
                      <li
                        key={session.id}
                        className={active ? "session-item active" : "session-item"}
                      >
                        <button
                          type="button"
                          className="session-item-btn"
                          onClick={() =>
                            onSelectSession(session.id, session.projectId || project.id)
                          }
                          disabled={disabled || active}
                        >
                          <span className="session-item-title">{session.title}</span>
                          <span className="session-item-id">
                            {shortSessionId(session.id)}
                          </span>
                        </button>
                        <button
                          type="button"
                          className="btn-small"
                          disabled={disabled}
                          onClick={() => startEditSession(session)}
                          title="会话属性"
                        >
                          属性
                        </button>
                        {onRemoveSession && (
                          <button
                            type="button"
                            className="session-remove-btn"
                            onClick={() => onRemoveSession(session.id)}
                            disabled={disabled}
                            aria-label={`删除会话 ${session.title}`}
                            title="删除"
                          >
                            ×
                          </button>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}

              {open && editSessionId && kids.some((s) => s.id === editSessionId) && (
                <div className="inline-form tree-edit-panel">
                  <input
                    className="inline-form-input"
                    value={editSessionTitle}
                    disabled={busy}
                    onChange={(e) => setEditSessionTitle(e.target.value)}
                    placeholder="会话标题"
                  />
                  <select
                    className="project-select"
                    value={editSessionProject}
                    disabled={busy}
                    onChange={(e) => setEditSessionProject(e.target.value)}
                    aria-label="所属课题"
                  >
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                  {formError && <p className="panel-error">{formError}</p>}
                  <div className="tree-edit-actions">
                    <button
                      type="button"
                      className="btn-small btn-primary"
                      disabled={busy || !editSessionTitle.trim()}
                      onClick={async () => {
                        if (!editSessionId) return;
                        setBusy(true);
                        setFormError(null);
                        try {
                          onUpdateSessionTitle(editSessionId, editSessionTitle.trim());
                          const currentPid =
                            kids.find((s) => s.id === editSessionId)?.projectId || project.id;
                          if (editSessionProject !== currentPid) {
                            await onMoveSession(editSessionId, editSessionProject);
                          }
                          setEditSessionId(null);
                        } catch (err) {
                          setFormError(err instanceof Error ? err.message : "保存失败");
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      保存
                    </button>
                    <button
                      type="button"
                      className="btn-small"
                      disabled={busy}
                      onClick={() => setEditSessionId(null)}
                    >
                      取消
                    </button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
