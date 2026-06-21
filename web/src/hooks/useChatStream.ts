import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import type { ChatMode, HistoryPreference, McpPreference } from "../utils/preferences";
import { buildHistoryRequestFields, buildMcpRequestFields } from "../utils/preferences";
import { formatBackendError, waitForBackend } from "../utils/backend";
import { getSessionId, setSessionId } from "../utils/session";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  reasoning?: string;
  usage?: Record<string, unknown>;
  streaming?: boolean;
  error?: string;
  toolCalls?: ToolCallEvent[];
  agentName?: string;
}

export interface ToolCallEvent {
  id: string;
  toolName: string;
  status: "running" | "done" | "error";
  arguments?: string;
  result?: string;
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
}

interface ServerMessage {
  role: string;
  content: string;
  reasoning_content?: string | null;
}

function mapServerMessages(raw: ServerMessage[]): ChatMessage[] {
  return raw
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({
      id: crypto.randomUUID(),
      role: m.role as "user" | "assistant",
      content: m.content,
      reasoning: m.reasoning_content ?? undefined,
    }));
}

/** 从 buffer 中解析完整的 SSE data 事件，返回未完成的尾部 */
function parseSseBuffer(buffer: string): { events: SseEvent[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: SseEvent[] = [];

  for (const part of parts) {
    for (const line of part.split("\n")) {
      if (line.startsWith("data: ")) {
        try {
          events.push(JSON.parse(line.slice(6)) as SseEvent);
        } catch {
          /* 忽略 malformed chunk */
        }
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
    }
    return null;
  }

  if (ev.type === "tool_call_start") {
    const toolId = ev.tool_call_id ?? crypto.randomUUID();
    ctx.setActiveToolName(ev.tool_name ?? "tool");
    return (prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? {
              ...m,
              toolCalls: [
                ...(m.toolCalls ?? []),
                {
                  id: toolId,
                  toolName: ev.tool_name ?? "tool",
                  status: "running" as const,
                  arguments: ev.content,
                },
              ],
            }
          : m,
      );
  }

  if (ev.type === "tool_call_result" || ev.type === "tool_call_error") {
    ctx.setActiveToolName(null);
    const status = ev.type === "tool_call_result" ? ("done" as const) : ("error" as const);
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
          const toolId = ev.tool_call_id ?? crypto.randomUUID();
          return {
            ...m,
            toolCalls: [
              ...toolCalls,
              {
                id: toolId,
                toolName: ev.tool_name ?? "tool",
                status,
                result: ev.content,
              },
            ],
          };
        }
        const updated = [...toolCalls];
        updated[idx] = {
          ...updated[idx],
          status,
          result: ev.content,
        };
        return { ...m, toolCalls: updated };
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
          ? { ...m, error: ev.content ?? "未知错误", streaming: false }
          : m,
      );
  }

  if (ev.type === "done") {
    return (prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? { ...m, streaming: false, usage: ev.usage ?? undefined }
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
) {
  let composed: ((prev: ChatMessage[]) => ChatMessage[]) | null = null;

  for (const ev of events) {
    const updater = applyStreamEvent(ev, assistantId, ctx);
    if (!updater) continue;
    composed = composed
      ? (prev) => updater(composed!(prev))
      : updater;
  }

  if (composed) {
    setMessages(composed);
  }
}

export function useChatStream(
  chatMode: ChatMode,
  historyPref: HistoryPreference,
  mcpPref: McpPreference,
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

  const finishStreaming = useCallback(() => {
    setIsStreaming(false);
    setMessages((prev) =>
      prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
    );
  }, []);

  const loadHistory = useCallback(async (opts?: { force?: boolean }) => {
    if (!opts?.force && isStreamingRef.current) return;

    historyAbortRef.current?.abort();
    const controller = new AbortController();
    historyAbortRef.current = controller;
    const epoch = historyEpochRef.current;

    setIsLoadingHistory(true);
    setHistoryError(null);
    setBackendOffline(false);

    try {
      const sid = getSessionId();
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

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
    };
    const assistantId = crypto.randomUUID();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      reasoning: "",
      streaming: true,
      toolCalls: [],
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);
    isStreamingRef.current = true;
    historyEpochRef.current += 1;
    historyAbortRef.current?.abort();
    pendingSessionIdRef.current = null;

    const controller = new AbortController();
    abortRef.current = controller;

    const streamCtx = {
      setSessionIdState,
      setActiveAgentName,
      setActiveToolName,
      sessionId,
      deferSessionSync: true,
      pendingSessionIdRef,
    };

    try {
      const res = await fetch("/v1/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          session_id: sessionId,
          mode: chatMode,
          ...buildHistoryRequestFields(historyPref),
          ...buildMcpRequestFields(mcpPref),
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
        processStreamEvents(events, assistantId, streamCtx, setMessages);
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const { events, rest } = parseSseBuffer(buffer);
        buffer = rest;
        handleParsedEvents(events);
      }

      // 处理流结束时 buffer 中未以 \n\n 结尾的最后一条事件
      buffer += decoder.decode();
      if (buffer.trim()) {
        const { events } = parseSseBuffer(`${buffer}\n\n`);
        handleParsedEvents(events);
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId && m.streaming ? { ...m, streaming: false } : m,
        ),
      );
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        finishStreaming();
        return;
      }
      const msg = formatBackendError(err);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, error: msg, streaming: false } : m,
        ),
      );
    } finally {
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
  }, [isStreaming, sessionId, chatMode, historyPref, mcpPref, finishStreaming]);

  const clearSession = useCallback(async () => {
    historyEpochRef.current += 1;
    await fetch(`/v1/sessions/${sessionId}`, { method: "DELETE" });
    setMessages([]);
    setHistoryError(null);
    setBackendOffline(false);
  }, [sessionId]);

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
  };
}
