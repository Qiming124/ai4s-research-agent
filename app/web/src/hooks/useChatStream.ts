/**
 * SSE 流式对话 Hook：管理消息列表、会话 ID、流式状态与 MCP/历史偏好。
 */
import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import type {
  ChatMode,
  CotMode,
  HistoryPreference,
  McpPreference,
  AgentPreference,
  ReasoningPreference,
} from "../utils/preferences";
import {
  buildHistoryRequestFields,
  buildMcpRequestFields,
  buildAgentRequestFields,
  buildReasoningRequestFields,
  buildCotModeRequestField,
} from "../utils/preferences";
import { parseCotSections } from "../utils/cotParse";
import { formatBackendError, waitForBackend } from "../utils/backend";
import {
  getSessionId,
  setSessionId,
  readSessionList,
  updateSessionMeta,
} from "../utils/session";
import { randomUUID } from "../utils/id";

export interface ToolCallEvent {
  id: string;
  toolName: string;
  status: "running" | "done" | "error";
  arguments?: string;
  result?: string;
}

export interface AgentHandoffEvent {
  id: string;
  fromAgent: string;
  toAgent: string;
  reason?: string;
}

export interface WorkflowStepEvent {
  id: string;
  stepKind: "plan" | "tool" | "verify" | "synthesize";
  status: "running" | "done" | "pass" | "fail" | "skipped" | "error";
  title: string;
  detail?: string;
  toolName?: string;
  toolCallId?: string;
}

export interface CotStepData {
  step: number;
  title: string;
  body: string;
}

export type TimelineEntry =
  | { kind: "tool"; event: ToolCallEvent }
  | { kind: "handoff"; event: AgentHandoffEvent }
  | { kind: "workflow"; event: WorkflowStepEvent }
  | { kind: "verify"; event: WorkflowStepEvent };

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  reasoning?: string;
  usage?: Record<string, unknown>;
  streaming?: boolean;
  error?: string;
  toolCalls?: ToolCallEvent[];
  handoffs?: AgentHandoffEvent[];
  timeline?: TimelineEntry[];
  cotSteps?: CotStepData[];
  agentName?: string;
  vizData?: import("../components/LossLandscapeViz").VizData;
  memoryWarnings?: string[];
  pipelineStages?: string[];
  pipelineGates?: string[];
}

interface SseEvent {
  type: string;
  content?: string;
  session_id?: string;
  agent_name?: string;
  tool_name?: string;
  tool_call_id?: string;
  a2a_task_id?: string;
  usage?: Record<string, unknown>;
  from_agent?: string;
  to_agent?: string;
  route_reason?: string;
  step_kind?: "plan" | "tool" | "verify" | "synthesize";
  status?: "running" | "done" | "pass" | "fail" | "skipped" | "error";
  title?: string;
  detail?: string;
}

interface ServerWorkflowStep {
  step_kind: string;
  status: string;
  title: string;
  detail?: string;
  tool_name?: string;
  tool_call_id?: string;
}

interface ServerToolCall {
  id: string;
  name: string;
  arguments?: string;
  result?: string | null;
  status: "success" | "error";
  error?: string | null;
}

interface ServerMessage {
  role: string;
  content: string;
  reasoning_content?: string | null;
  tool_calls?: ServerToolCall[] | null;
  workflow_steps?: ServerWorkflowStep[] | null;
}

function mapWorkflowSteps(
  raw: ServerWorkflowStep[] | null | undefined,
): TimelineEntry[] {
  if (!raw?.length) return [];
  const byKey = new Map<string, TimelineEntry>();
  raw.forEach((step, idx) => {
    const stepKind = step.step_kind as WorkflowStepEvent["stepKind"];
    const stableId =
      step.tool_call_id ||
      (stepKind === "plan" || stepKind === "synthesize"
        ? `wf-${stepKind}`
        : `${stepKind}-${step.title ?? idx}`);
    const event: WorkflowStepEvent = {
      id: stableId,
      stepKind,
      status: (step.status ?? "done") as WorkflowStepEvent["status"],
      title: step.title,
      detail: step.detail,
      toolName: step.tool_name,
      toolCallId: step.tool_call_id,
    };
    const kind = stepKind === "verify" ? ("verify" as const) : ("workflow" as const);
    byKey.set(stableId, { kind, event });
  });
  return Array.from(byKey.values());
}

function mergeTimelineFromWorkflow(
  timeline: TimelineEntry[],
  step: WorkflowStepEvent,
  kind: "workflow" | "verify",
): TimelineEntry[] {
  const idx = timeline.findIndex((e) => {
    if (e.kind !== "workflow" && e.kind !== "verify") return false;
    if (e.event.id === step.id) return true;
    // plan / synthesize 用稳定 id；兼容旧事件仅按 stepKind 合并
    if (step.stepKind !== "plan" && step.stepKind !== "synthesize") return false;
    return e.event.stepKind === step.stepKind;
  });
  if (idx === -1) {
    return [...timeline, { kind, event: step }];
  }
  const next = [...timeline];
  const prev = next[idx];
  if (prev.kind !== "workflow" && prev.kind !== "verify") {
    return [...timeline, { kind, event: step }];
  }
  next[idx] = {
    kind,
    event: {
      ...prev.event,
      ...step,
      id: step.id || prev.event.id,
      title: step.title || prev.event.title,
    },
  };
  return next;
}

/** 流结束时兜底：把仍为 running 的工作流/工具步骤标为 done，避免 UI 永久「进行中」 */
function finalizeRunningTimeline(timeline: TimelineEntry[] | undefined): TimelineEntry[] | undefined {
  if (!timeline?.length) return timeline;
  let changed = false;
  const next = timeline.map((entry) => {
    if (
      (entry.kind === "workflow" || entry.kind === "verify") &&
      entry.event.status === "running"
    ) {
      changed = true;
      return { ...entry, event: { ...entry.event, status: "done" as const } };
    }
    if (entry.kind === "tool" && entry.event.status === "running") {
      changed = true;
      return { ...entry, event: { ...entry.event, status: "done" as const } };
    }
    return entry;
  });
  return changed ? next : timeline;
}

function mapPersistedToolCalls(raw: ServerToolCall[] | null | undefined): ToolCallEvent[] | undefined {
  if (!raw || raw.length === 0) return undefined;
  return raw.map((tc) => ({
    id: tc.id,
    toolName: tc.name,
    status: tc.status === "error" ? ("error" as const) : ("done" as const),
    arguments: tc.arguments,
    result: tc.status === "error" ? (tc.error ?? tc.result ?? undefined) : (tc.result ?? undefined),
  }));
}

function mapServerMessages(raw: ServerMessage[]): ChatMessage[] {
  return raw
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => {
      const toolCalls = mapPersistedToolCalls(m.tool_calls);
      const workflowTimeline = mapWorkflowSteps(m.workflow_steps);
      const toolTimeline: TimelineEntry[] =
        toolCalls?.map((event) => ({ kind: "tool" as const, event })) ?? [];
      // 历史消息里可能残留 running（旧 bug）；加载时一律收尾，避免永久「进行中」
      const timeline = finalizeRunningTimeline([...workflowTimeline, ...toolTimeline]);
      return {
        id: randomUUID(),
        role: m.role as "user" | "assistant",
        content: m.content,
        reasoning: m.reasoning_content ?? undefined,
        toolCalls,
        timeline: timeline?.length ? timeline : undefined,
        cotSteps: parseCotSections(m.content),
      };
    });
}

/** 从 buffer 中解析完整的 SSE data 事件，返回未完成的尾部 */
function parseSseBuffer(buffer: string): { events: SseEvent[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: SseEvent[] = [];

  for (const part of parts) {
    for (const line of part.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const payload = trimmed.slice(5).trim();
      if (!payload) continue;
      try {
        const parsed = JSON.parse(payload);
        if (parsed && typeof parsed === "object" && parsed.type) {
          events.push(parsed as SseEvent);
        }
      } catch {
        /* 忽略 malformed chunk */
      }
    }
  }
  return { events, rest };
}

function applyStreamEvent(
  ev: SseEvent,
  assistantId: string,
  ctx: {
    setSessionIdState: (id: string) => void;
    setActiveAgentName: (name: string | null) => void;
    setActiveToolName: (name: string | null) => void;
    sessionId: string;
    deferSessionSync: boolean;
    pendingSessionIdRef: { current: string | null };
  },
): ((prev: ChatMessage[]) => ChatMessage[]) | null {
  if (ev.type === "meta") {
    if (ev.session_id && ev.session_id !== ctx.sessionId) {
      setSessionId(ev.session_id);
      ctx.sessionId = ev.session_id;
      if (ctx.deferSessionSync) {
        ctx.pendingSessionIdRef.current = ev.session_id;
      } else {
        ctx.setSessionIdState(ev.session_id);
      }
    } else if (ev.session_id) {
      setSessionId(ev.session_id);
    }
    if (ev.agent_name) {
      ctx.setActiveAgentName(ev.agent_name);
      return (prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, agentName: ev.agent_name } : m,
        );
    }
    return null;
  }

  if (ev.type === "agent_handoff") {
    const handoffId = ev.a2a_task_id ?? randomUUID();
    if (ev.to_agent) {
      ctx.setActiveAgentName(ev.to_agent);
    }
    const handoff: AgentHandoffEvent = {
      id: handoffId,
      fromAgent: ev.from_agent ?? "?",
      toAgent: ev.to_agent ?? "?",
      reason: ev.route_reason ?? ev.content,
    };
    return (prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? {
              ...m,
              agentName: ev.to_agent ?? m.agentName,
              handoffs: [...(m.handoffs ?? []), handoff],
              timeline: [
                ...(m.timeline ?? []),
                { kind: "handoff", event: handoff },
              ],
            }
          : m,
      );
  }

  if (ev.type === "tool_call_start") {
    const toolId = ev.tool_call_id ?? randomUUID();
    ctx.setActiveToolName(ev.tool_name ?? "tool");
    const toolEvent: ToolCallEvent = {
      id: toolId,
      toolName: ev.tool_name ?? "tool",
      status: "running",
      arguments: ev.content,
    };
    return (prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? {
              ...m,
              toolCalls: [...(m.toolCalls ?? []), toolEvent],
              timeline: [...(m.timeline ?? []), { kind: "tool", event: toolEvent }],
            }
          : m,
      );
  }

  if (ev.type === "tool_call_result" || ev.type === "tool_call_error") {
    ctx.setActiveToolName(null);
    const status = ev.type === "tool_call_result" ? ("done" as const) : ("error" as const);
    const safeContent = typeof ev.content === "string" ? ev.content : (ev.content == null ? "" : JSON.stringify(ev.content));
    return (prev) =>
      prev.map((m) => {
        if (m.id !== assistantId) return m;
        const toolCalls = m.toolCalls ?? [];
        const idx = ev.tool_call_id
          ? toolCalls.findIndex((tc) => tc.id === ev.tool_call_id)
          : toolCalls.findIndex(
              (tc) => tc.toolName === ev.tool_name && tc.status === "running",
            );
        if (idx === -1) {
          const toolId = ev.tool_call_id ?? randomUUID();
          const toolEvent: ToolCallEvent = {
            id: toolId,
            toolName: ev.tool_name ?? "tool",
            status,
            result: safeContent,
          };
          return {
            ...m,
            toolCalls: [...toolCalls, toolEvent],
            timeline: [...(m.timeline ?? []), { kind: "tool", event: toolEvent }],
          };
        }
        const updated = [...toolCalls];
        updated[idx] = {
          ...updated[idx],
          status,
          result: safeContent,
        };
        const timeline = (m.timeline ?? []).map((entry) =>
          entry.kind === "tool" && entry.event.id === updated[idx].id
            ? { kind: "tool" as const, event: updated[idx] }
            : entry,
        );
        let vizData = m.vizData;
        if (ev.tool_name?.includes("loss_landscape_2d") || ev.tool_name?.includes("sgd_trajectory")) {
          try {
            const parsed = JSON.parse(safeContent) as { viz_type?: string };
            if (parsed.viz_type) {
              vizData = parsed as import("../components/LossLandscapeViz").VizData;
            }
          } catch {
            /* ignore */
          }
        }
        return { ...m, toolCalls: updated, timeline, vizData };
      });
  }

  if (ev.type === "workflow_step") {
    const stepKind = (ev.step_kind ?? "plan") as WorkflowStepEvent["stepKind"];
    const stableId =
      ev.tool_call_id ||
      (stepKind === "plan" || stepKind === "synthesize"
        ? `wf-${stepKind}`
        : `${stepKind}-${ev.title ?? stepKind}`);
    const step: WorkflowStepEvent = {
      id: stableId,
      stepKind,
      status: (ev.status ?? "running") as WorkflowStepEvent["status"],
      title: ev.title ?? stepKind,
      detail: ev.detail ?? ev.content,
      toolName: ev.tool_name,
      toolCallId: ev.tool_call_id,
    };
    const kind = stepKind === "verify" ? ("verify" as const) : ("workflow" as const);
    return (prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? {
              ...m,
              timeline: mergeTimelineFromWorkflow(m.timeline ?? [], step, kind),
            }
          : m,
      );
  }

  if (ev.type === "verification_result") {
    let detail = ev.content ?? "";
    let status: WorkflowStepEvent["status"] = "done";
    try {
      const parsed = JSON.parse(detail) as { status?: string; reason?: string };
      if (parsed.status === "pass") status = "pass";
      else if (parsed.status === "fail") status = "fail";
      else if (parsed.status === "skipped") status = "skipped";
      if (parsed.reason) detail = parsed.reason;
    } catch {
      /* 保留原始 JSON 文本 */
    }
    const step: WorkflowStepEvent = {
      id: "verify-sympy",
      stepKind: "verify",
      status,
      title: "SymPy 符号验证",
      detail,
    };
    return (prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? {
              ...m,
              timeline: mergeTimelineFromWorkflow(m.timeline ?? [], step, "verify"),
            }
          : m,
      );
  }

  if (ev.type === "numerical_verification_result") {
    let detail = ev.content ?? "";
    let status: WorkflowStepEvent["status"] = "done";
    try {
      const parsed = JSON.parse(detail) as { status?: string; reason?: string };
      if (parsed.status === "pass") status = "pass";
      else if (parsed.status === "fail") status = "fail";
      else if (parsed.status === "skipped") status = "skipped";
      if (parsed.reason) detail = parsed.reason;
    } catch {
      /* keep raw */
    }
    const step: WorkflowStepEvent = {
      id: "verify-numerical",
      stepKind: "verify",
      status,
      title: "数值验证",
      detail,
    };
    return (prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? {
              ...m,
              timeline: mergeTimelineFromWorkflow(m.timeline ?? [], step, "verify"),
            }
          : m,
      );
  }

  if (ev.type === "pipeline_stage") {
    const stage = ev.content ?? ev.title ?? "stage";
    return (prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? { ...m, pipelineStages: [...(m.pipelineStages ?? []), stage] }
          : m,
      );
  }

  if (ev.type === "pipeline_gate") {
    const gate = ev.content ?? "";
    return (prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? { ...m, pipelineGates: [...(m.pipelineGates ?? []), gate] }
          : m,
      );
  }

  if (ev.type === "memory_warning") {
    const warning = ev.content ?? "";
    return (prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? { ...m, memoryWarnings: [...(m.memoryWarnings ?? []), warning] }
          : m,
      );
  }

  if (ev.type === "cot_step") {
    let stepData: CotStepData | null = null;
    try {
      stepData = JSON.parse(ev.content ?? "{}") as CotStepData;
    } catch {
      return null;
    }
    if (!stepData?.title) return null;
    return (prev) =>
      prev.map((m) => {
        if (m.id !== assistantId) return m;
        const existing = m.cotSteps ?? [];
        const filtered = existing.filter((s) => s.step !== stepData!.step);
        return {
          ...m,
          cotSteps: [...filtered, stepData!].sort((a, b) => a.step - b.step),
        };
      });
  }

  if (ev.type === "reasoning") {
    return (prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? { ...m, reasoning: (m.reasoning ?? "") + (ev.content ?? "") }
          : m,
      );
  }

  if (ev.type === "content") {
    return (prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? { ...m, content: m.content + (ev.content ?? "") }
          : m,
      );
  }

  if (ev.type === "error") {
    return (prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? {
              ...m,
              error: ev.content ?? "未知错误",
              streaming: false,
              timeline: finalizeRunningTimeline(m.timeline),
            }
          : m,
      );
  }

  if (ev.type === "done") {
    return (prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? {
              ...m,
              streaming: false,
              usage: ev.usage ?? undefined,
              timeline: finalizeRunningTimeline(m.timeline),
              toolCalls: m.toolCalls?.map((tc) =>
                tc.status === "running" ? { ...tc, status: "done" as const } : tc,
              ),
            }
          : m,
      );
  }

  return null;
}

function processStreamEvents(
  events: SseEvent[],
  assistantId: string,
  ctx: Parameters<typeof applyStreamEvent>[2],
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
  callbacks?: {
    onPipelineStage?: (stage: string) => void;
    onPipelineGate?: (payload: string) => void;
  },
) {
  const updaters: Array<(prev: ChatMessage[]) => ChatMessage[]> = [];

  for (const ev of events) {
    if (ev.type === "pipeline_stage" && callbacks?.onPipelineStage) {
      callbacks.onPipelineStage(ev.content ?? ev.title ?? "stage");
    }
    if (ev.type === "pipeline_gate" && callbacks?.onPipelineGate) {
      callbacks.onPipelineGate(ev.content ?? "{}");
    }
    try {
      const updater = applyStreamEvent(ev, assistantId, ctx);
      if (updater) updaters.push(updater);
    } catch {
      /* 忽略单条事件解析/应用失败，不中断整个批次 */
    }
  }

  if (updaters.length === 0) return;

  try {
    setMessages((prev) => {
      let next = prev;
      for (const updater of updaters) {
        next = updater(next);
      }
      return next;
    });
  } catch {
    /* 状态更新失败，已在 ErrorBoundary 层兜底 */
  }
}

/**
 * 聊天流式 Hook：SSE 消费、会话历史、MCP 事件与多会话切换。
 *
 * @param chatMode - 对话模式 chat 或 math
 * @param historyPref - L1 历史策略（是否用服务端默认等）
 * @param mcpPref - MCP 是否启用及是否用服务端默认
 * @returns 消息列表、sessionId、流式状态及 sendMessage 等操作方法
 */
export function useChatStream(
  chatMode: ChatMode,
  historyPref: HistoryPreference,
  mcpPref: McpPreference,
  agentPref: AgentPreference,
  reasoningPref: ReasoningPreference,
  cotMode: CotMode,
  callbacks?: {
    onPipelineStage?: (stage: string) => void;
    onPipelineGate?: (payload: string) => void;
  },
  projectId?: string,
) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionIdState] = useState(getSessionId);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [backendOffline, setBackendOffline] = useState(false);
  const [activeAgentName, setActiveAgentName] = useState<string | null>(null);
  const [activeToolName, setActiveToolName] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const historyAbortRef = useRef<AbortController | null>(null);
  const isStreamingRef = useRef(false);
  const pendingSessionIdRef = useRef<string | null>(null);
  const historyEpochRef = useRef(0);
  const sessionIdRef = useRef(sessionId);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const finishStreaming = useCallback(() => {
    setIsStreaming(false);
    setMessages((prev) =>
      prev.map((m) =>
        m.streaming
          ? {
              ...m,
              streaming: false,
              timeline: finalizeRunningTimeline(m.timeline),
              toolCalls: m.toolCalls?.map((tc) =>
                tc.status === "running" ? { ...tc, status: "done" as const } : tc,
              ),
            }
          : m,
      ),
    );
  }, []);

  const loadHistory = useCallback(async (opts?: { force?: boolean; sid?: string }) => {
    if (!opts?.force && isStreamingRef.current) return;

    historyAbortRef.current?.abort();
    const controller = new AbortController();
    historyAbortRef.current = controller;
    const epoch = historyEpochRef.current;
    const sid = opts?.sid ?? sessionIdRef.current;

    setIsLoadingHistory(true);
    setHistoryError(null);
    setBackendOffline(false);

    try {
      const res = await fetch(`/v1/sessions/${sid}`, { signal: controller.signal });
      if (controller.signal.aborted || epoch !== historyEpochRef.current || isStreamingRef.current) {
        return;
      }
      if (res.status === 404) {
        setMessages([]);
        return;
      }
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      const data = (await res.json()) as { messages: ServerMessage[] };
      if (epoch !== historyEpochRef.current || isStreamingRef.current) return;
      setMessages(mapServerMessages(data.messages));
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      if (isStreamingRef.current) return;
      const msg = formatBackendError(err);
      if (msg.includes("127.0.0.1:8000")) {
        setBackendOffline(true);
      }
      setHistoryError(msg);
    } finally {
      if (epoch === historyEpochRef.current) {
        setIsLoadingHistory(false);
      }
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      const ready = await waitForBackend(6, 1000);
      if (cancelled || isStreamingRef.current) return;
      if (!ready) {
        setBackendOffline(true);
        setHistoryError(formatBackendError(new Error("Failed to fetch")));
        setIsLoadingHistory(false);
        return;
      }
      await loadHistory({ force: true });
    }

    init();
    return () => {
      cancelled = true;
      historyAbortRef.current?.abort();
    };
  }, [loadHistory]);

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    finishStreaming();
  }, [finishStreaming]);

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;

    const sid = sessionIdRef.current;
    const meta = readSessionList().find((s) => s.id === sid);
    const defaultTitle =
      !meta?.title ||
      meta.title.startsWith("会话 ") ||
      meta.title.startsWith("新会话 ");
    if (defaultTitle) {
      updateSessionMeta(sid, {
        title: trimmed.slice(0, 40) + (trimmed.length > 40 ? "…" : ""),
        updatedAt: Date.now(),
      });
    } else {
      updateSessionMeta(sid, { updatedAt: Date.now() });
    }

    const userMsg: ChatMessage = {
      id: randomUUID(),
      role: "user",
      content: trimmed,
    };
    const assistantId = randomUUID();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      reasoning: "",
      streaming: true,
      toolCalls: [],
      handoffs: [],
      cotSteps: [],
      timeline: [],
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);
    isStreamingRef.current = true;
    historyEpochRef.current += 1;
    historyAbortRef.current?.abort();
    pendingSessionIdRef.current = null;

    const controller = new AbortController();
    abortRef.current = controller;
    // 不用固定「整段生成超时」：长工具链可能超过数分钟仍在正常推进。
    // 改为空闲检测——持续一段时间收不到任何 SSE 字节才判定卡死。
    const idleTimeoutMs = 300_000;
    let abortedByIdle = false;
    let idleTimerId = 0;
    const bumpIdleWatchdog = () => {
      window.clearTimeout(idleTimerId);
      idleTimerId = window.setTimeout(() => {
        if (!controller.signal.aborted) {
          abortedByIdle = true;
          controller.abort();
        }
      }, idleTimeoutMs);
    };
    bumpIdleWatchdog();

    const streamCtx = {
      setSessionIdState,
      setActiveAgentName,
      setActiveToolName,
      sessionId: sid,
      deferSessionSync: true,
      pendingSessionIdRef,
    };

    try {
      const res = await fetch("/v1/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          session_id: sid,
          mode: chatMode,
          ...buildHistoryRequestFields(historyPref),
          ...buildMcpRequestFields(mcpPref),
          ...buildAgentRequestFields(agentPref),
          ...buildReasoningRequestFields(reasoningPref),
          ...buildCotModeRequestField(cotMode, chatMode),
          project_id: projectId ?? undefined,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("响应体不可读");

      const decoder = new TextDecoder();
      let buffer = "";

      const handleParsedEvents = (events: SseEvent[]) => {
        processStreamEvents(events, assistantId, streamCtx, setMessages, callbacks);
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        bumpIdleWatchdog();

        buffer += decoder.decode(value, { stream: true });
        const { events, rest } = parseSseBuffer(buffer);
        buffer = rest;
        handleParsedEvents(events);
      }

      buffer += decoder.decode();
      if (buffer.trim()) {
        const { events } = parseSseBuffer(`${buffer}\n\n`);
        handleParsedEvents(events);
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId && m.streaming
            ? {
                ...m,
                streaming: false,
                timeline: finalizeRunningTimeline(m.timeline),
                toolCalls: m.toolCalls?.map((tc) =>
                  tc.status === "running" ? { ...tc, status: "done" as const } : tc,
                ),
              }
            : m,
        ),
      );
      updateSessionMeta(sessionIdRef.current, { updatedAt: Date.now() });
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  error: abortedByIdle
                    ? "长时间未收到服务器数据（可能已中断），已自动停止。可点顶栏「停止」旁重试，或直接再发一条消息。"
                    : m.error,
                  streaming: false,
                  timeline: finalizeRunningTimeline(m.timeline),
                }
              : m,
          ),
        );
        finishStreaming();
        return;
      }
      const msg = formatBackendError(err);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                error: msg,
                streaming: false,
                timeline: finalizeRunningTimeline(m.timeline),
                toolCalls: m.toolCalls?.map((tc) =>
                  tc.status === "running" ? { ...tc, status: "error" as const } : tc,
                ),
              }
            : m,
        ),
      );
    } finally {
      window.clearTimeout(idleTimerId);
      isStreamingRef.current = false;
      setIsStreaming(false);
      setActiveAgentName(null);
      setActiveToolName(null);
      abortRef.current = null;
      if (pendingSessionIdRef.current) {
        setSessionIdState(pendingSessionIdRef.current);
        pendingSessionIdRef.current = null;
      }
    }
  }, [isStreaming, chatMode, historyPref, mcpPref, agentPref, reasoningPref, cotMode, finishStreaming, callbacks, projectId]);

  const clearSession = useCallback(async () => {
    historyEpochRef.current += 1;
    const sid = sessionIdRef.current;
    await fetch(`/v1/sessions/${sid}`, { method: "DELETE" });
    setMessages([]);
    setHistoryError(null);
    setBackendOffline(false);
    updateSessionMeta(sid, { updatedAt: Date.now() });
  }, []);

  const switchSession = useCallback(
    async (newId: string) => {
      if (isStreamingRef.current) return;
      setSessionId(newId);
      setSessionIdState(newId);
      sessionIdRef.current = newId;
      historyEpochRef.current += 1;
      setMessages([]);
      setHistoryError(null);
      setBackendOffline(false);
      await loadHistory({ force: true, sid: newId });
    },
    [loadHistory],
  );

  const createSession = useCallback(
    async (newId: string) => {
      if (isStreamingRef.current) return;
      setSessionId(newId);
      setSessionIdState(newId);
      sessionIdRef.current = newId;
      historyEpochRef.current += 1;
      setMessages([]);
      setHistoryError(null);
      setBackendOffline(false);
      setIsLoadingHistory(false);
    },
    [],
  );

  return {
    messages,
    sessionId,
    isStreaming,
    isLoadingHistory,
    historyError,
    backendOffline,
    activeAgentName,
    activeToolName,
    sendMessage,
    stopGeneration,
    clearSession,
    reloadHistory: loadHistory,
    switchSession,
    createSession,
  };
}
