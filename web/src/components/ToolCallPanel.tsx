import type { ToolCallEvent } from "../hooks/useChatStream";

interface ToolCallPanelProps {
  events: ToolCallEvent[];
}

function safeToolText(value: unknown, maxLen = 800): string {
  if (value == null) return "";
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return text.length > maxLen ? `${text.slice(0, maxLen)}…` : text;
}

export function ToolCallPanel({ events }: ToolCallPanelProps) {
  if (events.length === 0) return null;

  return (
    <div className="tool-call-panel">
      <div className="tool-call-title">工具调用</div>
      {events.map((ev) => (
        <div key={ev.id} className={`tool-call-item tool-call-${ev.status}`}>
          <div className="tool-call-header">
            <span className="tool-call-name">{ev.toolName}</span>
            <span className="tool-call-status">
              {ev.status === "running" ? "执行中…" : ev.status === "error" ? "失败" : "完成"}
            </span>
          </div>
          {ev.arguments != null && ev.arguments !== "" && (
            <pre className="tool-call-args">{safeToolText(ev.arguments, 400)}</pre>
          )}
          {ev.result != null && ev.result !== "" && (
            <pre className="tool-call-result">{safeToolText(ev.result)}</pre>
          )}
        </div>
      ))}
    </div>
  );
}
