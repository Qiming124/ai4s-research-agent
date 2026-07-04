import { useState } from "react";
import type { ProjectTask } from "../hooks/useProjectTasks";

const STATUS_LABELS: Record<string, string> = {
  todo: "待办",
  in_progress: "进行中",
  blocked: "阻塞",
  done: "完成",
};

const ROLE_LABELS: Record<string, string> = {
  pi: "PI",
  theorist: "理论",
  experimenter: "实验",
  reviewer: "审稿",
  literature: "文献",
};

const ROLE_OPTIONS = ["theorist", "experimenter", "literature", "reviewer", "pi"] as const;

interface TaskBoardProps {
  tasks: ProjectTask[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onUpdateStatus: (taskId: number, status: string) => void;
  onCreateTask?: (title: string, assigneeRole: string) => Promise<void>;
}

export function TaskBoard({
  tasks,
  loading,
  error,
  onRefresh,
  onUpdateStatus,
  onCreateTask,
}: TaskBoardProps) {
  const columns = ["todo", "in_progress", "blocked", "done"] as const;
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [role, setRole] = useState<string>("theorist");
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!onCreateTask || !title.trim()) return;
    setCreating(true);
    setFormError(null);
    try {
      await onCreateTask(title, role);
      setTitle("");
      setRole("theorist");
      setShowForm(false);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "创建失败");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="task-board">
      <div className="panel-header">
        <h4>任务看板</h4>
        <div className="panel-header-actions">
          {onCreateTask && (
            <button
              type="button"
              className="btn-small"
              disabled={loading || creating}
              onClick={() => {
                setShowForm((v) => !v);
                setFormError(null);
              }}
            >
              {showForm ? "取消" : "+ 任务"}
            </button>
          )}
          <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
            刷新
          </button>
        </div>
      </div>

      {showForm && onCreateTask && (
        <div className="inline-form">
          <input
            className="inline-form-input"
            placeholder="任务标题（必填）"
            value={title}
            disabled={creating}
            onChange={(e) => setTitle(e.target.value)}
          />
          <select
            className="inline-form-input"
            value={role}
            disabled={creating}
            onChange={(e) => setRole(e.target.value)}
          >
            {ROLE_OPTIONS.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
          {formError && <p className="panel-error">{formError}</p>}
          <button
            type="button"
            className="btn-small btn-primary"
            disabled={creating || !title.trim()}
            onClick={handleCreate}
          >
            {creating ? "添加中…" : "添加任务"}
          </button>
        </div>
      )}

      {error && (
        <p className="panel-error" title={error}>
          {error.includes("404") ? "任务看板不可用：请重启后端服务" : error}
        </p>
      )}
      {loading && <p className="panel-muted">加载中…</p>}
      {!loading && !error && tasks.length === 0 && (
        <p className="panel-muted">暂无任务，点击「+ 任务」添加。</p>
      )}
      <div className="kanban-columns">
        {columns.map((col) => (
          <div key={col} className="kanban-col">
            <h5>{STATUS_LABELS[col]}</h5>
            {tasks
              .filter((t) => t.status === col)
              .map((t) => (
                <div key={t.id} className="kanban-card">
                  <strong>{t.title}</strong>
                  <span className="role-tag">{ROLE_LABELS[t.assignee_role] ?? t.assignee_role}</span>
                  {col !== "done" && (
                    <select
                      className="task-status-select"
                      value={col}
                      onChange={(e) => onUpdateStatus(t.id, e.target.value)}
                    >
                      <option value="todo">待办</option>
                      <option value="in_progress">进行中</option>
                      <option value="blocked">阻塞</option>
                      <option value="done">完成</option>
                    </select>
                  )}
                </div>
              ))}
          </div>
        ))}
      </div>
    </div>
  );
}
