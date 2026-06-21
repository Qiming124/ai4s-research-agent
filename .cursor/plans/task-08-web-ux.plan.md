---
name: Task 08 — Web UX
task_id: p7-web
status: completed
---

# Task 08: Web three-column layout, tool timeline, RAG management, streaming stability

## Goal

Upgrade the Web UI to a three-column layout with session list, message stream (agent tags + tool timeline), persistent settings panel with RAG document management, and top-bar status (connection, agent, token usage). Preserve `useChatStream` streaming stability; restore `tool_calls` from session history.

## Preconditions

- [x] Tasks 1–7 on `dev`: SSE events (`agent_handoff`, `tool_call_*`, `agent_name`), session `tool_calls` persistence, `/v1/documents`, `/v1/stats/tokens`
- [x] Work on `dev` only, no remote push

## Steps

### Step 1 — Hooks & data layer

1. `web/src/utils/session.ts` — multi-session localStorage list (create/switch/remove)
2. `web/src/hooks/useChatStream.ts` — `mapServerMessages` includes `tool_calls`; handle `agent_handoff` SSE; set `agentName` on messages
3. `web/src/hooks/useTokenStats.ts` — `GET /v1/stats/tokens` (session-scoped)
4. `web/src/hooks/useDocuments.ts` — list/upload/delete documents

### Step 2 — UI components

1. `web/src/components/ToolTimeline.tsx` — vertical timeline for tool calls + agent handoffs
2. `web/src/components/SessionListSidebar.tsx` — left column: new session + list
3. `web/src/components/DocumentPanel.tsx` — RAG upload/list/delete
4. `web/src/components/TopStatusBar.tsx` — connection, agent, tokens
5. Enhance `AgentSettingsSidebar` — persistent right panel + DocumentPanel section
6. `MessageBubble` — agent tag + ToolTimeline

### Step 3 — Layout & stability

1. `ChatPage.tsx` — three-column grid layout
2. `App.tsx` — root ErrorBoundary
3. `index.css` — layout styles (skip dark mode)
4. Preserve `useChatStream` deferSessionSync / history epoch guards

### Step 4 — Tests + benchmark + plan update

1. `cd web && npm run build`
2. `pytest tests/ -q` (backend unchanged)
3. `benchmarks/task-08-web-ux.md` with manual test checklist (no Playwright)
4. Logical commits on `dev`
5. Mark `p7-web` completed; update main plan overview if all 8 done

## Out of scope

- Dark mode
- Playwright E2E (document manual test in benchmark)
- Backend changes

## Status log

| Step | Status | Notes |
|------|--------|-------|
| Plan file | done | this file |
| Hooks | done | useChatStream, useTokenStats, useDocuments, session multi-list |
| Components | done | ToolTimeline, SessionListSidebar, DocumentPanel, TopStatusBar |
| Layout | done | three-column ChatPage, ErrorBoundary coverage |
| Tests + benchmark | done | build PASS, 84 pytest PASS, benchmarks/task-08-web-ux.md |
