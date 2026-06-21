# Task 08 — Web UX (three-column layout, tool timeline, RAG management)

Verify the upgraded Web UI: three-column layout, streaming tool timeline with agent handoffs, session history tool_calls restore, RAG document management, and top-bar status.

## Prerequisites

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
cd web && npm install
```

Ensure `.env` has `DEEPSEEK_API_KEY`, `ENABLE_MCP=true`, `ENABLE_RAG=true`, and `ORCHESTRATION_BACKEND=langgraph`.

## Automated tests

```bash
cd /home/agent/web && npm run build
cd /home/agent && pytest tests/ -q
```

Expected: **build PASS**, **84 passed** (backend unchanged).

## New / updated Web components (Task 8)

| Component | Path |
|-----------|------|
| Three-column layout | `web/src/components/ChatPage.tsx` |
| Session list (localStorage) | `web/src/components/SessionListSidebar.tsx`, `web/src/utils/session.ts` |
| Tool timeline | `web/src/components/ToolTimeline.tsx` |
| Top status bar | `web/src/components/TopStatusBar.tsx` |
| RAG document panel | `web/src/components/DocumentPanel.tsx` |
| Settings panel (persistent) | `web/src/components/AgentSettingsSidebar.tsx` |
| SSE + history hooks | `web/src/hooks/useChatStream.ts` |
| Token stats hook | `web/src/hooks/useTokenStats.ts` |
| Documents hook | `web/src/hooks/useDocuments.ts` |
| Root ErrorBoundary | `web/src/App.tsx` |

## Manual verification checklist

Start backend + dev server:

```bash
cd /home/agent
uvicorn server.main:app --reload --port 8000
# another terminal:
cd web && npm run dev
```

Open http://localhost:5173 (or Docker http://localhost:8000 after rebuild).

### Layout

- [ ] Left: session list with **+ 新建**; switching sessions loads history
- [ ] Center: message stream + input footer
- [ ] Right: persistent settings panel (mode, L1, MCP, RAG)
- [ ] Top bar: connection status, session id, active agent, token count

### Streaming & timeline

- [ ] Send a question that triggers MCP tools — tool timeline shows running → done
- [ ] With auto-route, `agent_handoff` appears in timeline (supervisor → sub-agent)
- [ ] Agent tag visible on assistant messages during/after routing
- [ ] Refresh page — tool calls restored from `GET /v1/sessions/{id}` (no loss)

### RAG documents

- [ ] Right panel: paste markdown → **上传索引**
- [ ] Document appears in list with chunk count
- [ ] **删除** removes document
- [ ] `GET /v1/documents` matches UI list

### Token stats

- [ ] Top bar shows session token total from `/v1/stats/tokens?session_id=...`
- [ ] Count updates after a completed chat turn

### Stability

- [ ] Stream a reply — history reload does not overwrite in-flight message
- [ ] ErrorBoundary: malformed message content shows retry UI, not white screen

## Playwright E2E

Not added in Task 8 — use manual checklist above. Optional follow-up.

## Task 8 run results

| Check | Result |
|-------|--------|
| `npm run build` | **PASS** |
| `pytest tests/ -q` | **PASS** — 84 passed |

## All 8 tasks complete

Phases 3–7 (LangChain, MCP, multi-agent, RAG, Docker, Web UX) are delivered on `dev`.
