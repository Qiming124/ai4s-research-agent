---
name: Task 08 — Web UX
overview: ""
todos: []
isProject: false
---

# Task 08：Web 三栏布局、工具时间线、RAG 管理、流式稳定性

## 目标

升级 Web UI 为三栏布局：会话列表、消息流（Agent 标签 + 工具时间线）、含 RAG 文档管理的持久设置面板、顶栏状态（连接、Agent、token 用量）。保留 `useChatStream` 流式稳定性；从会话历史恢复 `tool_calls`。

## 前置条件

- [ ] Task 1–7 在 `dev`：SSE 事件（`agent_handoff`、`tool_call_*`、`agent_name`）、会话 `tool_calls` 持久化、`/v1/documents`、`/v1/stats/tokens`
- [x] 仅在 `dev` 工作，不 push 远程

## 步骤

### Step 1 — Hooks 与数据层

1. `web/src/utils/session.ts` — 多会话 localStorage 列表（创建/切换/删除）
2. `web/src/hooks/useChatStream.ts` — `mapServerMessages` 含 `tool_calls`；处理 `agent_handoff` SSE；消息上设置 `agentName`
3. `web/src/hooks/useTokenStats.ts` — `GET /v1/stats/tokens`（按 session）
4. `web/src/hooks/useDocuments.ts` — 列表/上传/删除文档

### Step 2 — UI 组件

1. `web/src/components/ToolTimeline.tsx` — 工具调用 + Agent handoff 垂直时间线
2. `web/src/components/SessionListSidebar.tsx` — 左栏：新建会话 + 列表
3. `web/src/components/DocumentPanel.tsx` — RAG 上传/列表/删除
4. `web/src/components/TopStatusBar.tsx` — 连接、Agent、tokens
5. 增强 `AgentSettingsSidebar` — 持久右栏 + DocumentPanel 区块
6. `MessageBubble` — Agent 标签 + ToolTimeline

### Step 3 — 布局与稳定性

1. `ChatPage.tsx` — 三栏 grid 布局
2. `App.tsx` — 根 ErrorBoundary
3. `index.css` — 布局样式（跳过暗色模式）
4. 保留 `useChatStream` deferSessionSync / history epoch 守卫

### Step 4 — 测试 + benchmark + 计划更新

1. `cd web && npm run build`
2. `pytest tests/ -q`（后端未变）
3. `benchmarks/task-08-web-ux.md`，含手动测试清单（无 Playwright）
4. 在 `dev` 上逻辑提交
5. 标记 `p7-web` completed；若 8 项全部完成则更新主计划 overview

## 不在范围内

- 暗色模式
- Playwright E2E（在 benchmark 中记录手动测试）
- 后端变更

## 状态日志


| 步骤             | 状态   | 备注                                                         |
| -------------- | ---- | ---------------------------------------------------------- |
| 计划文件           | done | 本文件                                                        |
| Hooks          | done | useChatStream、useTokenStats、useDocuments、session 多列表       |
| 组件             | done | ToolTimeline、SessionListSidebar、DocumentPanel、TopStatusBar |
| 布局             | done | 三栏 ChatPage、ErrorBoundary 覆盖                               |
| 测试 + benchmark | done | build PASS，84 pytest PASS，benchmarks/task-08-web-ux.md     |


