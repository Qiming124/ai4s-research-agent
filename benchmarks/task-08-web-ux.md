# Task 08 — Web UX（三栏布局、工具时间线、RAG 管理）

验证升级后的 Web UI：三栏布局、流式工具时间线与 Agent handoff、会话历史 tool_calls 恢复、RAG 文档管理、顶栏状态。

## 前置条件

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
cd web && npm install
```

确保 `.env` 含 `DEEPSEEK_API_KEY`、`ENABLE_MCP=true`、`ENABLE_RAG=true`、`ORCHESTRATION_BACKEND=langgraph`。

## 自动化测试

```bash
cd /home/agent/web && npm run build
cd /home/agent && pytest tests/ -q
```

预期：**build PASS**，**84 passed**（后端未变）。

## 新增 / 更新的 Web 组件（Task 8）

| 组件 | 路径 |
|------|------|
| 三栏布局 | `web/src/components/ChatPage.tsx` |
| 会话列表（localStorage） | `web/src/components/SessionListSidebar.tsx`、`web/src/utils/session.ts` |
| 工具时间线 | `web/src/components/ToolTimeline.tsx` |
| 顶栏状态 | `web/src/components/TopStatusBar.tsx` |
| RAG 文档面板 | `web/src/components/DocumentPanel.tsx` |
| 设置面板（持久） | `web/src/components/AgentSettingsSidebar.tsx` |
| SSE + 历史 hooks | `web/src/hooks/useChatStream.ts` |
| Token 统计 hook | `web/src/hooks/useTokenStats.ts` |
| 文档 hook | `web/src/hooks/useDocuments.ts` |
| 根 ErrorBoundary | `web/src/App.tsx` |

## 手动验证清单

启动后端 + 开发服务器：

```bash
cd /home/agent
uvicorn server.main:app --reload --port 8000
# 另一终端:
cd web && npm run dev
```

打开 http://localhost:5173（或 Docker 重建后 http://localhost:8000）。

### 布局

- [ ] 左侧：会话列表含 **+ 新建**；切换会话加载历史
- [ ] 中间：消息流 + 输入区
- [ ] 右侧：持久设置面板（模式、L1、MCP、RAG）
- [ ] 顶栏：连接状态、session id、当前 Agent、token 计数

### 流式与时间线

- [ ] 发送触发 MCP 工具的问题 — 时间线显示 running → done
- [ ] 自动路由时，时间线出现 `agent_handoff`（supervisor → 子 Agent）
- [ ] 路由过程中/后 assistant 消息可见 Agent 标签
- [ ] 刷新页面 — 从 `GET /v1/sessions/{id}` 恢复 tool calls（不丢失）

### RAG 文档

- [ ] 右侧面板：粘贴 markdown → **上传索引**
- [ ] 列表显示文档及 chunk 数
- [ ] **删除** 移除文档
- [ ] `GET /v1/documents` 与 UI 列表一致

### Token 统计

- [ ] 顶栏显示来自 `/v1/stats/tokens?session_id=...` 的会话 token 合计
- [ ] 完成一轮对话后计数更新

### 稳定性

- [ ] 流式回复时 — 历史重载不覆盖进行中的消息
- [ ] ErrorBoundary：畸形消息内容显示重试 UI，非白屏

## Playwright E2E

Task 8 未添加 — 使用上述手动清单。可选后续跟进。

## Task 8 执行结果

| 检查项 | 结果 |
|--------|------|
| `npm run build` | **PASS** |
| `pytest tests/ -q` | **PASS** — 84 passed |

## 全部 8 个 Task 已完成

Phase 3–7（LangChain、MCP、多 Agent、RAG、Docker、Web UX）已在 `dev` 分支交付。
