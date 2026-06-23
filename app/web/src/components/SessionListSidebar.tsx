import type { SessionMeta } from "../utils/session";
import { shortSessionId } from "../utils/session";

interface SessionListSidebarProps {
  sessions: SessionMeta[];
  currentSessionId: string;
  disabled?: boolean;
  onSelect: (id: string) => void;
  onNewSession: () => void;
  onRemove?: (id: string) => void;
}

export function SessionListSidebar({
  sessions,
  currentSessionId,
  disabled = false,
  onSelect,
  onNewSession,
  onRemove,
}: SessionListSidebarProps) {
  return (
    <aside className="session-sidebar" aria-label="会话列表">
      <div className="session-sidebar-head">
        <h2>会话</h2>
        <button
          type="button"
          className="btn-new-session"
          onClick={onNewSession}
          disabled={disabled}
          title="新建会话"
        >
          + 新建
        </button>
      </div>
      <ul className="session-list">
        {sessions.length === 0 && (
          <li className="session-empty">暂无会话</li>
        )}
        {sessions.map((session) => {
          const active = session.id === currentSessionId;
          return (
            <li key={session.id} className={active ? "session-item active" : "session-item"}>
              <button
                type="button"
                className="session-item-btn"
                onClick={() => onSelect(session.id)}
                disabled={disabled || active}
              >
                <span className="session-item-title">{session.title}</span>
                <span className="session-item-id">{shortSessionId(session.id)}</span>
              </button>
              {onRemove && (
                <button
                  type="button"
                  className="session-remove-btn"
                  onClick={() => onRemove(session.id)}
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
    </aside>
  );
}
