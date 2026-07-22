import { useEffect, useState } from "react";
import type { ProjectInfo } from "../hooks/useProjects";
import type { ProjectTask } from "../hooks/useProjectTasks";
import type { SessionMeta } from "../utils/session";
import type { LeftSidebarTab } from "../utils/uiEdition";
import { ProjectSessionTree } from "./ProjectSessionTree";
import { SidebarEdgeToggle } from "./SidebarEdgeToggle";
import { TaskBoard } from "./TaskBoard";

interface LeftSidebarProps {
  projects: ProjectInfo[];
  currentProjectId: string;
  currentProject: ProjectInfo;
  onSelectProject: (id: string) => void;
  onCreateProject: (name: string, description?: string) => Promise<void>;
  onUpdateProject: (projectId: string, patch: { name?: string; description?: string }) => Promise<void>;
  onDeleteProject: (projectId: string) => Promise<void>;
  projectsError: string | null;
  linkStatus: string | null;
  projectMembers: { user_id: string; role: string }[];
  tasks: ProjectTask[];
  tasksLoading: boolean;
  tasksError: string | null;
  onRefreshTasks: () => void;
  onUpdateTaskStatus: (taskId: number, status: string) => void;
  onCreateTask: (title: string, assigneeRole?: string) => Promise<void>;
  sessions: SessionMeta[];
  currentSessionId: string;
  disabled?: boolean;
  onSelectSession: (id: string, projectId?: string) => void;
  onNewSession: (projectId?: string) => void;
  onRemoveSession: (id: string) => void;
  onMoveSession: (sessionId: string, projectId: string) => Promise<void>;
  onUpdateSessionTitle: (sessionId: string, title: string) => void;
  /** 界面版本允许的左栏 Tab；默认全开 */
  allowedTabs?: LeftSidebarTab[];
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

const ALL_TABS: { id: LeftSidebarTab; label: string }[] = [
  { id: "sessions", label: "会话" },
  { id: "tasks", label: "任务" },
];

const DEFAULT_ALLOWED: LeftSidebarTab[] = ["sessions", "tasks"];

export function LeftSidebar(props: LeftSidebarProps) {
  const allowed =
    props.allowedTabs?.length ? props.allowedTabs : DEFAULT_ALLOWED;
  const visibleTabs = ALL_TABS.filter((t) => allowed.includes(t.id));
  const collapsed = Boolean(props.collapsed);

  const [tab, setTab] = useState<LeftSidebarTab>(
    () => allowed[0] ?? "sessions",
  );

  useEffect(() => {
    if (!allowed.includes(tab)) {
      setTab(allowed[0] ?? "sessions");
    }
  }, [allowed, tab]);

  return (
    <aside
      className={collapsed ? "left-sidebar left-sidebar--collapsed" : "left-sidebar"}
      aria-label="项目导航"
    >
      {!collapsed && (
        <div className="left-sidebar-main">
          {visibleTabs.length > 1 && (
            <nav className="left-sidebar-tabs" role="tablist">
              {visibleTabs.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.id}
                  className={tab === t.id ? "left-sidebar-tab active" : "left-sidebar-tab"}
                  onClick={() => setTab(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </nav>
          )}
          <div className="left-sidebar-body">
            {props.projectsError && <p className="panel-error">{props.projectsError}</p>}
            {props.linkStatus && (
              <p className="panel-muted project-link-status">{props.linkStatus}</p>
            )}
            {tab === "tasks" && allowed.includes("tasks") && (
              <TaskBoard
                tasks={props.tasks}
                loading={props.tasksLoading}
                error={props.tasksError}
                onRefresh={props.onRefreshTasks}
                onUpdateStatus={props.onUpdateTaskStatus}
                onCreateTask={props.onCreateTask}
              />
            )}
            {tab === "sessions" && allowed.includes("sessions") && (
              <ProjectSessionTree
                projects={props.projects.length ? props.projects : [props.currentProject]}
                sessions={props.sessions}
                currentProjectId={props.currentProjectId}
                currentSessionId={props.currentSessionId}
                disabled={props.disabled}
                onSelectSession={(sid, pid) => {
                  props.onSelectProject(pid);
                  props.onSelectSession(sid, pid);
                }}
                onNewSession={(pid) => props.onNewSession(pid)}
                onRemoveSession={props.onRemoveSession}
                onCreateProject={props.onCreateProject}
                onUpdateProject={props.onUpdateProject}
                onDeleteProject={props.onDeleteProject}
                onMoveSession={props.onMoveSession}
                onUpdateSessionTitle={props.onUpdateSessionTitle}
              />
            )}
          </div>
        </div>
      )}
      {props.onToggleCollapse && (
        <SidebarEdgeToggle
          side="left"
          collapsed={collapsed}
          onToggle={props.onToggleCollapse}
        />
      )}
    </aside>
  );
}
