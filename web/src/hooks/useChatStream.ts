import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMode } from "../utils/preferences";
import { getSessionId, setSessionId } from "../utils/session";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  reasoning?: string;
  usage?: Record<string, unknown>;
  streaming?: boolean;
  error?: string;
}

interface SseEvent {
  type: string;
  content?: string;
  session_id?: string;
  usage?: Record<string, unknown>;
}

interface ServerMessage {
  role: string;
  content: string;
}

function mapServerMessages(raw: ServerMessage[]): ChatMessage[] {
  return raw
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({
      id: crypto.randomUUID(),
      role: m.role as "user" | "assistant",
      content: m.content,
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

export function useChatStream(chatMode: ChatMode) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionIdState] = useState(getSessionId);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const finishStreaming = useCallback(() => {
    setIsStreaming(false);
    setMessages((prev) =>
      prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
    );
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      setIsLoadingHistory(true);
      setHistoryError(null);
      try {
        const res = await fetch(`/v1/sessions/${sessionId}`);
        if (res.status === 404) {
          if (!cancelled) setMessages([]);
          return;
        }
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${await res.text()}`);
        }
        const data = (await res.json()) as { messages: ServerMessage[] };
        if (!cancelled) {
          setMessages(mapServerMessages(data.messages));
        }
      } catch (err) {
        if (!cancelled) {
          setHistoryError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) {
          setIsLoadingHistory(false);
        }
      }
    }

    loadHistory();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

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
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch("/v1/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          session_id: sessionId,
          mode: chatMode,
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

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const { events, rest } = parseSseBuffer(buffer);
        buffer = rest;

        for (const ev of events) {
          if (ev.type === "meta" && ev.session_id) {
            setSessionId(ev.session_id);
            setSessionIdState(ev.session_id);
          } else if (ev.type === "reasoning") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, reasoning: (m.reasoning ?? "") + (ev.content ?? "") }
                  : m,
              ),
            );
          } else if (ev.type === "content") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: m.content + (ev.content ?? "") }
                  : m,
              ),
            );
          } else if (ev.type === "error") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, error: ev.content ?? "未知错误", streaming: false }
                  : m,
              ),
            );
          } else if (ev.type === "done") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, streaming: false, usage: ev.usage ?? undefined }
                  : m,
              ),
            );
          }
        }
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
      const msg = err instanceof Error ? err.message : String(err);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, error: msg, streaming: false } : m,
        ),
      );
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [isStreaming, sessionId, chatMode, finishStreaming]);

  const clearSession = useCallback(async () => {
    await fetch(`/v1/sessions/${sessionId}`, { method: "DELETE" });
    setMessages([]);
    setHistoryError(null);
  }, [sessionId]);

  return {
    messages,
    sessionId,
    isStreaming,
    isLoadingHistory,
    historyError,
    sendMessage,
    stopGeneration,
    clearSession,
  };
}
