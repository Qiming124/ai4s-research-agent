import { Component, type ReactNode } from "react";
import type { TimelineEntry } from "../hooks/useChatStream";

class WorkflowTimelineGuard extends Component<{ children: ReactNode }> {
  override state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  override render() {
    if (this.state.hasError) return null;
    return this.props.children;
  }
}

interface WorkflowTimelineProps {
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

function statusLabel(status: string): string {
  switch (status) {
    case "running":
      return "进行中…";
    case "pass":
      return "通过";
    case "fail":
      return "失败";
    case "skipped":
      return "跳过";
    case "error":
      return "错误";
    case "done":
      return "完成";
    default:
      return status;
  }
}

function statusColor(status: string): string {
  if (status === "fail" || status === "error") return "#dc2626";
  if (status === "pass" || status === "done") return "#22c55e";
  if (status === "skipped") return "#94a3b8";
  return "#f59e0b";
}

function workflowKindLabel(kind: string): string {
  switch (kind) {
    case "plan":
      return "规划";
    case "tool":
      return "工具";
    case "verify":
      return "验证";
    case "synthesize":
      return "综合";
    default:
      return kind;
  }
}

function WorkflowTimelineInner({ timeline = [] }: WorkflowTimelineProps) {
  if (!timeline || timeline.length === 0) return null;

  return (
    <div className="tool-timeline workflow-timeline">
      <div className="tool-timeline-title">工作流</div>
      <ol className="tool-timeline-list">
        {timeline.map((entry, idx) => {
          try {
            if (!entry?.event) return null;

            if (entry.kind === "handoff") {
              const h = entry.event;
              return (
                <li key={h.id ?? `h-${idx}`} className="timeline-item timeline-handoff">
                  <div className="timeline-content">
                    Agent: {h.fromAgent ?? "?"} → {h.toAgent ?? "?"}
                  </div>
                </li>
              );
            }

            if (entry.kind === "workflow" || entry.kind === "verify") {
              const w = entry.event;
              return (
                <li key={w.id ?? `w-${idx}`} className="timeline-item timeline-workflow">
                  <div className="timeline-content">
                    <span className="workflow-kind-badge">{workflowKindLabel(w.stepKind)}</span>{" "}
                    <strong>{w.title}</strong>{" "}
                    <span style={{ color: statusColor(w.status) }}>
                      {statusLabel(w.status)}
                    </span>
                    {w.detail && (
                      <pre className="tool-call-result">{safeText(w.detail)}</pre>
                    )}
                  </div>
                </li>
              );
            }

            const ev = entry.event;
            const status = ev.status ?? "running";
            return (
              <li key={ev.id ?? `t-${idx}`} className="timeline-item timeline-tool">
                <div className="timeline-content">
                  <span className="workflow-kind-badge">工具</span>{" "}
                  <strong>{ev.toolName ?? "tool"}</strong>{" "}
                  <span style={{ color: statusColor(status) }}>
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

export function WorkflowTimeline(props: WorkflowTimelineProps) {
  return (
    <WorkflowTimelineGuard>
      <WorkflowTimelineInner {...props} />
    </WorkflowTimelineGuard>
  );
}

/** @deprecated 使用 WorkflowTimeline */
export { WorkflowTimeline as ToolTimeline };
