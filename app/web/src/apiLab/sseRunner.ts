/**
 * SSE 流式响应解析：产出事件列表，供 API 实验室时间线展示。
 */

export interface SseLabEvent {
  seq: number;
  type: string;
  contentPreview: string;
  raw: unknown;
}

export interface SseRunResult {
  events: SseLabEvent[];
  rawText: string;
  aborted: boolean;
}

function previewOf(data: unknown): string {
  if (data == null) return "";
  if (typeof data === "string") return data.slice(0, 200);
  if (typeof data === "object") {
    const o = data as Record<string, unknown>;
    if (typeof o.content === "string") return o.content.slice(0, 200);
    if (typeof o.type === "string") {
      const extra = typeof o.content === "string" ? o.content.slice(0, 120) : "";
      return extra ? `${o.type}: ${extra}` : o.type;
    }
    try {
      return JSON.stringify(data).slice(0, 200);
    } catch {
      return String(data);
    }
  }
  return String(data).slice(0, 200);
}

function parseSseChunk(buffer: string): { events: unknown[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: unknown[] = [];
  for (const part of parts) {
    for (const line of part.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const payload = trimmed.slice(5).trim();
      if (!payload || payload === "[DONE]") continue;
      try {
        events.push(JSON.parse(payload));
      } catch {
        events.push({ type: "raw", content: payload });
      }
    }
  }
  return { events, rest };
}

/**
 * 消费 Response body 为 SSE 事件流。
 */
export async function runSseResponse(
  res: Response,
  options?: {
    signal?: AbortSignal;
    onEvent?: (ev: SseLabEvent) => void;
    maxEvents?: number;
  },
): Promise<SseRunResult> {
  const maxEvents = options?.maxEvents ?? 500;
  const events: SseLabEvent[] = [];
  let rawText = "";
  let aborted = false;

  if (!res.body) {
    const text = await res.text();
    return { events, rawText: text, aborted: false };
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let seq = 0;

  try {
    while (true) {
      if (options?.signal?.aborted) {
        aborted = true;
        break;
      }
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      rawText += chunk;
      buffer += chunk;
      const parsed = parseSseChunk(buffer);
      buffer = parsed.rest;
      for (const data of parsed.events) {
        const type =
          data && typeof data === "object" && "type" in data
            ? String((data as { type: unknown }).type)
            : "message";
        const ev: SseLabEvent = {
          seq: ++seq,
          type,
          contentPreview: previewOf(data),
          raw: data,
        };
        events.push(ev);
        options?.onEvent?.(ev);
        if (events.length >= maxEvents) {
          aborted = true;
          await reader.cancel();
          return { events, rawText, aborted };
        }
        if (type === "done" || type === "error") {
          return { events, rawText, aborted: false };
        }
      }
    }
    if (buffer.trim()) {
      const parsed = parseSseChunk(buffer + "\n\n");
      for (const data of parsed.events) {
        const type =
          data && typeof data === "object" && "type" in data
            ? String((data as { type: unknown }).type)
            : "message";
        const ev: SseLabEvent = {
          seq: ++seq,
          type,
          contentPreview: previewOf(data),
          raw: data,
        };
        events.push(ev);
        options?.onEvent?.(ev);
      }
    }
  } catch (err) {
    if (options?.signal?.aborted) aborted = true;
    else throw err;
  }

  return { events, rawText, aborted };
}
