/**
 * OpenAPI 3 文档解析：拉取 /openapi.json → 按 tag 分组的可测接口列表。
 */

export type HttpMethod = "get" | "post" | "put" | "patch" | "delete" | "head" | "options";

export interface OpenApiParameter {
  name: string;
  in: "path" | "query" | "header" | "cookie";
  required?: boolean;
  description?: string;
  schema?: Record<string, unknown>;
}

export interface ApiOperation {
  id: string;
  method: HttpMethod;
  path: string;
  summary: string;
  description: string;
  tags: string[];
  parameters: OpenApiParameter[];
  /** 请求体 JSON schema（已尽量 resolve $ref） */
  requestBodySchema: Record<string, unknown> | null;
  /** 是否声明 application/json 请求体 */
  hasJsonBody: boolean;
  /** 是否可能返回 SSE（由 path / 描述启发式） */
  likelySse: boolean;
}

export interface OpenApiCatalog {
  title: string;
  version: string;
  operations: ApiOperation[];
  /** tag → operations */
  byTag: Record<string, ApiOperation[]>;
}

const METHODS: HttpMethod[] = ["get", "post", "put", "patch", "delete", "head", "options"];

function resolveRef(
  root: Record<string, unknown>,
  node: unknown,
  depth = 0,
): unknown {
  if (!node || typeof node !== "object" || depth > 8) return node;
  const obj = node as Record<string, unknown>;
  if (typeof obj.$ref === "string") {
    const ref = obj.$ref as string;
    const m = /^#\/components\/schemas\/(.+)$/.exec(ref);
    if (!m) return node;
    const schemas = (root.components as Record<string, unknown> | undefined)?.schemas as
      | Record<string, unknown>
      | undefined;
    const target = schemas?.[m[1]];
    if (!target) return node;
    return resolveRef(root, target, depth + 1);
  }
  if (Array.isArray(node)) {
    return node.map((item) => resolveRef(root, item, depth + 1));
  }
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(obj)) {
    out[k] = resolveRef(root, v, depth + 1);
  }
  return out;
}

/** 从 JSON Schema 生成最小示例值 */
export function schemaToExample(schema: Record<string, unknown> | null | undefined): unknown {
  if (!schema) return {};
  const t = schema.type;
  if (schema.example !== undefined) return schema.example;
  if (schema.default !== undefined) return schema.default;
  if (Array.isArray(schema.enum) && schema.enum.length > 0) return schema.enum[0];

  if (t === "string") return "";
  if (t === "integer" || t === "number") return 0;
  if (t === "boolean") return false;
  if (t === "array") {
    const items = schema.items as Record<string, unknown> | undefined;
    return items ? [schemaToExample(items)] : [];
  }
  if (t === "object" || schema.properties) {
    const props = (schema.properties || {}) as Record<string, Record<string, unknown>>;
    const required = new Set((schema.required as string[]) || []);
    const obj: Record<string, unknown> = {};
    for (const [key, prop] of Object.entries(props)) {
      if (required.has(key) || Object.keys(props).length <= 8) {
        obj[key] = schemaToExample(prop);
      }
    }
    return obj;
  }
  if (Array.isArray(schema.anyOf) && schema.anyOf[0]) {
    return schemaToExample(schema.anyOf[0] as Record<string, unknown>);
  }
  if (Array.isArray(schema.oneOf) && schema.oneOf[0]) {
    return schemaToExample(schema.oneOf[0] as Record<string, unknown>);
  }
  return {};
}

function paramExample(p: OpenApiParameter): string {
  const s = p.schema || {};
  if (s.example !== undefined) return String(s.example);
  if (s.default !== undefined) return String(s.default);
  if (p.name.includes("session")) return "demo-session";
  if (p.name.includes("project")) return "default";
  if (p.name === "purge") return "false";
  return "";
}

export function buildDefaultParamValues(op: ApiOperation): Record<string, string> {
  const values: Record<string, string> = {};
  for (const p of op.parameters) {
    values[`${p.in}:${p.name}`] = paramExample(p);
  }
  return values;
}

export function buildDefaultBody(op: ApiOperation): string {
  if (!op.hasJsonBody) return "";
  const example = schemaToExample(op.requestBodySchema);
  try {
    return JSON.stringify(example, null, 2);
  } catch {
    return "{}";
  }
}

export function parseOpenApiDocument(doc: Record<string, unknown>): OpenApiCatalog {
  const info = (doc.info || {}) as Record<string, unknown>;
  const paths = (doc.paths || {}) as Record<string, Record<string, unknown>>;
  const operations: ApiOperation[] = [];

  for (const [path, pathItem] of Object.entries(paths)) {
    if (!pathItem || typeof pathItem !== "object") continue;
    for (const method of METHODS) {
      const opRaw = pathItem[method] as Record<string, unknown> | undefined;
      if (!opRaw) continue;

      const tags = (Array.isArray(opRaw.tags) ? opRaw.tags : ["default"]) as string[];
      const parameters: OpenApiParameter[] = [];

      const collectParams = (list: unknown) => {
        if (!Array.isArray(list)) return;
        for (const item of list) {
          const resolved = resolveRef(doc, item) as OpenApiParameter;
          if (resolved?.name && resolved?.in) {
            parameters.push({
              name: resolved.name,
              in: resolved.in,
              required: Boolean(resolved.required),
              description: resolved.description,
              schema: (resolved.schema || {}) as Record<string, unknown>,
            });
          }
        }
      };
      collectParams(pathItem.parameters);
      collectParams(opRaw.parameters);

      let hasJsonBody = false;
      let requestBodySchema: Record<string, unknown> | null = null;
      const rb = opRaw.requestBody as Record<string, unknown> | undefined;
      if (rb) {
        const content = (rb.content || {}) as Record<string, Record<string, unknown>>;
        const json = content["application/json"];
        if (json?.schema) {
          hasJsonBody = true;
          requestBodySchema = resolveRef(doc, json.schema) as Record<string, unknown>;
        }
      }

      const summary = String(opRaw.summary || opRaw.operationId || `${method.toUpperCase()} ${path}`);
      const description = String(opRaw.description || "");
      const likelySse =
        path.includes("/stream") ||
        /sse|event-stream|流式/i.test(summary + description);

      operations.push({
        id: `${method}:${path}`,
        method,
        path,
        summary,
        description,
        tags,
        parameters,
        requestBodySchema,
        hasJsonBody,
        likelySse,
      });
    }
  }

  operations.sort((a, b) => a.path.localeCompare(b.path) || a.method.localeCompare(b.method));

  const byTag: Record<string, ApiOperation[]> = {};
  for (const op of operations) {
    const tag = op.tags[0] || "default";
    if (!byTag[tag]) byTag[tag] = [];
    byTag[tag].push(op);
  }

  return {
    title: String(info.title || "API"),
    version: String(info.version || ""),
    operations,
    byTag,
  };
}

export async function fetchOpenApiCatalog(
  url = "/openapi.json",
): Promise<OpenApiCatalog> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`加载 OpenAPI 失败：HTTP ${res.status}`);
  }
  const doc = (await res.json()) as Record<string, unknown>;
  return parseOpenApiDocument(doc);
}

/** OpenAPI tag → 中文标签 */
export const TAG_LABELS: Record<string, string> = {
  default: "默认",
  health: "健康检查",
  chat: "对话",
  sessions: "会话",
  agents: "Agent",
  mcp: "MCP",
  documents: "文献",
  stats: "统计",
  export: "导出",
  experiments: "实验",
  jupyter: "Jupyter",
  projects: "课题",
  theory: "理论",
  verification: "验证",
  observability: "可观测",
  sync: "同步",
  memory: "记忆",
};
