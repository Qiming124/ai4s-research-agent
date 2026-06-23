import { Component, type ReactNode } from "react";
import type { TimelineEntry } from "../hooks/useChatStream";

/* 工具时间线：如果在 MCP 流式过程中渲染出错，回退为空白，不破坏整个页面 */
class ToolTimelineGuard extends Component<{ children: ReactNode }> {
  override state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  override render() {
    if (this.state.hasError) return null;
    return this.props.children;
  }
}

interface ToolTimelineProps {
  timeline?: TimelineEntry[];
}

function safeText(value: unknown, maxLen = 600): string {
  try {
    if (value == null) return "";
    const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
    return text.length > maxLen ? `${text.slice(0, maxLen)}…` : text;
  } catch {
    return "(无法显示)";
  }
}

function ToolTimelineInner({ timeline = [] }: ToolTimelineProps) {
  if (!timeline || timeline.length === 0) return null;

  return (
    <div className="tool-timeline">
      <div className="tool-timeline-title">执行时间线</div>
      <ol className="tool-timeline-list">
        {timeline.map((entry) => {
          try {
            if (!entry || !entry.event) return null;
            if (entry.kind === "handoff") {
              const h = entry.event as any;
              return (
                <li key={h.id ?? "h"} className="timeline-item timeline-handoff">
                  <div className="timeline-content">
                    Agent: {h.fromAgent ?? "?"} → {h.toAgent ?? "?"}
                  </div>
                </li>
              );
            }
            const ev = entry.event;
            const status = ev.status ?? "running";
            return (
              <li key={ev.id ?? "t"} className={`timeline-item timeline-tool`}>
                <div className="timeline-content">
                  <strong>{ev.toolName ?? "tool"}</strong>{" "}
                  <span style={{color: status === "error" ? "#dc2626" : status === "done" ? "#22c55e" : "#f59e0b"}}>
                    {status === "running" ? "执行中…" : status === "error" ? "失败" : "完成"}
                  </span>
                  {ev.result != null && ev.result !== "" && (
                    <pre className="tool-call-result">{safeText(ev.result)}</pre>
                  )}
                </div>
              </li>
            );
          } catch {
            return null;
          }
        })}
      </ol>
    </div>
  );
}

export function ToolTimeline(props: ToolTimelineProps) {
  return (
    <ToolTimelineGuard>
      <ToolTimelineInner {...props} />
    </ToolTimelineGuard>
  );
}
