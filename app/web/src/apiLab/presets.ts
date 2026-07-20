/**
 * 内置测试场景：一键填入常用请求。
 */

export interface ApiLabPreset {
  id: string;
  label: string;
  hint: string;
  /** 匹配 operation id 前缀或 path */
  match: { method: string; path: string };
  paramValues?: Record<string, string>;
  bodyText?: string;
  forceSse?: boolean;
}

export const API_LAB_PRESETS: ApiLabPreset[] = [
  {
    id: "health",
    label: "健康检查",
    hint: "GET /health",
    match: { method: "get", path: "/health" },
  },
  {
    id: "list-projects",
    label: "列课题",
    hint: "GET /v1/projects",
    match: { method: "get", path: "/v1/projects" },
  },
  {
    id: "list-sessions",
    label: "列会话",
    hint: "GET /v1/sessions",
    match: { method: "get", path: "/v1/sessions" },
  },
  {
    id: "mcp-status",
    label: "MCP 状态",
    hint: "GET /v1/mcp/status",
    match: { method: "get", path: "/v1/mcp/status" },
  },
  {
    id: "export-preview",
    label: "导出预览",
    hint: "GET /v1/export/preview",
    match: { method: "get", path: "/v1/export/preview" },
    paramValues: {
      "query:session_id": "demo-session",
      "query:include_global": "true",
      "query:include_chat": "true",
    },
  },
  {
    id: "chat-stream",
    label: "流式对话 SSE",
    hint: "短问题，观察 SSE 事件",
    match: { method: "post", path: "/v1/chat/stream" },
    forceSse: true,
    bodyText: JSON.stringify(
      {
        message: "用一句话介绍损失函数局部极小值",
        session_id: "api-lab-demo",
        mode: "chat",
        agent: "auto",
        enable_thinking: false,
        max_history_messages: 0,
      },
      null,
      2,
    ),
  },
];
