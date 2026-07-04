import { useState } from "react";
import type { ProjectInfo } from "../hooks/useProjects";
import type { ProjectTask } from "../hooks/useProjectTasks";
import type { SessionMeta } from "../utils/session";
import { ProjectHub } from "./ProjectHub";
import { SessionListSidebar } from "./SessionListSidebar";
import { TaskBoard } from "./TaskBoard";

type LeftSidebarTab = "project" | "tasks" | "sessions";

interface LeftSidebarProps {
  projects: ProjectInfo[];
  currentProjectId: string;
  currentProject: ProjectInfo;
  onSelectProject: (id: string) => void;
  onCreateProject: (name: string, description?: string) => Promise<void>;
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
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onRemoveSession: (id: string) => void;
}

const TABS: { id: LeftSidebarTab; label: string }[] = [
  { id: "sessions", label: "会话" },
  { id: "project", label: "课题" },
  { id: "tasks", label: "任务" },
];

export function LeftSidebar(props: LeftSidebarProps) {
  const [tab, setTab] = useState<LeftSidebarTab>("sessions");

  return (
    <aside className="left-sidebar" aria-label="项目导航">
      <nav className="left-sidebar-tabs" role="tablist">
        {TABS.map((t) => (
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
      <div className="left-sidebar-body">
        {tab === "project" && (
          <ProjectHub
            projects={props.projects.length ? props.projects : [props.currentProject]}
            currentProjectId={props.currentProjectId}
            onSelect={props.onSelectProject}
            onCreate={props.onCreateProject}
            disabled={props.disabled}
            error={props.projectsError}
            linkStatus={props.linkStatus}
            members={props.projectMembers}
          />
        )}
        {tab === "tasks" && (
          <TaskBoard
            tasks={props.tasks}
            loading={props.tasksLoading}
            error={props.tasksError}
            onRefresh={props.onRefreshTasks}
            onUpdateStatus={props.onUpdateTaskStatus}
            onCreateTask={props.onCreateTask}
          />
        )}
        {tab === "sessions" && (
          <SessionListSidebar
            sessions={props.sessions}
            currentSessionId={props.currentSessionId}
            disabled={props.disabled}
            onSelect={props.onSelectSession}
            onNewSession={props.onNewSession}
            onRemove={props.onRemoveSession}
          />
        )}
      </div>
    </aside>
  );
}
