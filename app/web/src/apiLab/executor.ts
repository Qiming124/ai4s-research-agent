/**
 * HTTP 请求执行器：拼 URL、发 fetch、区分 JSON / 文本 / blob / SSE。
 */

import type { ApiOperation, HttpMethod } from "./openapi";
import { runSseResponse, type SseLabEvent } from "./sseRunner";

export interface ExecuteInput {
  method: HttpMethod;
  pathTemplate: string;
  /** key = `${in}:${name}` */
  paramValues: Record<string, string>;
  bodyText: string;
  signal?: AbortSignal;
  onSseEvent?: (ev: SseLabEvent) => void;
  /** 强制按 SSE 解析（即使 Content-Type 未声明） */
  forceSse?: boolean;
}

export interface ExecuteResult {
  ok: boolean;
  status: number;
  statusText: string;
  durationMs: number;
  headers: Record<string, string>;
  contentType: string;
  kind: "json" | "text" | "sse" | "blob" | "empty" | "error";
  json?: unknown;
  text?: string;
  sseEvents?: SseLabEvent[];
  blob?: Blob;
  filename?: string;
  errorMessage?: string;
  requestUrl: string;
}

function fillPath(
  template: string,
  paramValues: Record<string, string>,
): { path: string; query: URLSearchParams; headers: Record<string, string> } {
  let path = template;
  const query = new URLSearchParams();
  const headers: Record<string, string> = {};

  for (const [key, raw] of Object.entries(paramValues)) {
    const idx = key.indexOf(":");
    if (idx < 0) continue;
    const loc = key.slice(0, idx);
    const name = key.slice(idx + 1);
    const value = raw ?? "";
    if (loc === "path") {
      path = path.replace(new RegExp(`\\{${name}\\}`, "g"), encodeURIComponent(value));
    } else if (loc === "query") {
      if (value !== "") query.set(name, value);
    } else if (loc === "header") {
      if (value !== "") headers[name] = value;
    }
  }
  return { path, query, headers };
}

function parseFilename(contentDisposition: string | null): string | undefined {
  if (!contentDisposition) return undefined;
  const m = /filename\*?=(?:UTF-8''|")?([^\";]+)"?/i.exec(contentDisposition);
  return m?.[1] ? decodeURIComponent(m[1]) : undefined;
}

export async function executeApiRequest(input: ExecuteInput): Promise<ExecuteResult> {
  const started = performance.now();
  const { path, query, headers } = fillPath(input.pathTemplate, input.paramValues);
  const qs = query.toString();
  const url = qs ? `${path}?${qs}` : path;

  const init: RequestInit = {
    method: input.method.toUpperCase(),
    headers: { ...headers },
    signal: input.signal,
  };

  const method = input.method.toLowerCase();
  if (input.bodyText.trim() && method !== "get" && method !== "head") {
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
    init.body = input.bodyText;
  }

  try {
    const res = await fetch(url, init);
    const durationMs = Math.round(performance.now() - started);
    const headerMap: Record<string, string> = {};
    res.headers.forEach((v, k) => {
      headerMap[k] = v;
    });
    const contentType = res.headers.get("content-type") || "";
    const base = {
      ok: res.ok,
      status: res.status,
      statusText: res.statusText,
      durationMs,
      headers: headerMap,
      contentType,
      requestUrl: url,
    };

    const isSse =
      input.forceSse ||
      contentType.includes("text/event-stream") ||
      url.includes("/stream");

    if (isSse && res.body) {
      const sse = await runSseResponse(res, {
        signal: input.signal,
        onEvent: input.onSseEvent,
      });
      return {
        ...base,
        kind: "sse",
        sseEvents: sse.events,
        text: sse.rawText,
      };
    }

    if (
      contentType.includes("application/json") ||
      contentType.includes("+json")
    ) {
      const json = await res.json();
      return { ...base, kind: "json", json };
    }

    if (
      contentType.includes("application/octet-stream") ||
      contentType.includes("application/pdf") ||
      contentType.includes(
        "application/vnd.openxmlformats-officedocument",
      ) ||
      contentType.includes("application/zip") ||
      Boolean(res.headers.get("content-disposition"))
    ) {
      const blob = await res.blob();
      return {
        ...base,
        kind: "blob",
        blob,
        filename: parseFilename(res.headers.get("content-disposition")),
      };
    }

    const text = await res.text();
    if (!text) return { ...base, kind: "empty", text: "" };
    try {
      const json = JSON.parse(text);
      return { ...base, kind: "json", json, text };
    } catch {
      return { ...base, kind: "text", text };
    }
  } catch (err) {
    const durationMs = Math.round(performance.now() - started);
    return {
      ok: false,
      status: 0,
      statusText: "",
      durationMs,
      headers: {},
      contentType: "",
      kind: "error",
      errorMessage: err instanceof Error ? err.message : String(err),
      requestUrl: url,
    };
  }
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "download";
  a.click();
  URL.revokeObjectURL(url);
}

export function operationToExecuteDefaults(op: ApiOperation): {
  method: HttpMethod;
  pathTemplate: string;
} {
  return { method: op.method, pathTemplate: op.path };
}
