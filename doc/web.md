# Web 前端（v2.2）

Vite + React + TypeScript。源码在 **`app/web/`**；生产产物 `app/web/dist` 由 `app/server/main.py` 托管。

## 环境与启动

- Node.js 18+
- 后端：`uvicorn server.main:app --app-dir app`（`:8000`）

```bash
cd app/web && npm install && npm run dev   # http://localhost:5173
cd app/web && npm run build                # → dist，与 API 同端口托管
```

Vite 将 `/v1`、`/health` 代理到 8000；SSE 已设 `X-Accel-Buffering: no`。生产 Nginx 须 `proxy_buffering off`（见 [`DEPLOY.md`](DEPLOY.md)）。

## 布局

| 区域 | 组件 | 说明 |
|------|------|------|
| 左栏 | `ProjectHub` / `SessionListSidebar` / `TaskBoard` | 课题、会话、任务看板 |
| 中栏 | `ChatPage` + `MessageBubble` + 时间线 | SSE 对话、CoT、工具、验证、Loss Landscape |
| 右栏 | `ResearchWorkbench` | Tabs：文献 / 理论 / 验证 / 图谱 / 实验 / 导出 |
| 顶栏 | `TopStatusBar` / `HelpPanel` / `ObservabilityPanel` | Agent、MCP、Token、帮助、质量 |

流水线 SSE `pipeline_stage` 可自动切换工作台 Tab（`workbenchTabs` 相关逻辑）。

## 工作台与关键组件

| 组件 | 说明 |
|------|------|
| `DocumentPanel` / `BibliographyPanel` / `RagRefsPanel` | 文献入库、书目、RAG 引用 |
| `TheoryAssetsPanel` / `WorkspacePanel` / `AssumptionDagPanel` | 符号假设、工作区编辑、假设 DAG |
| `VerificationDashboard` | 验证账本与手动重跑 |
| `TheoremLibraryPanel` / `KnowledgeGraphPanel` | L4 定理库与图谱 |
| `ExperimentLogPanel` / `LossLandscapeViz` | 实验日志与可视化 |
| `ExportPanel` | preview / polish / md / latex / docx / pdf |
| `OnboardingWizard` | 首次引导 |
| `ErrorBoundary` | 渲染错误隔离 |

主要 Hooks：`useChatStream`、`useCampaign`、`useVerification`、`useDocuments`、`useStructuredMemory`、`useAssumptionDag`、`useExperimentLogs` 等。

## Agent 与 SSE

支持 Agent：`general` / `theory` / `experiment` / `literature` / `review` / `counterexample`。  
重要 SSE：`pipeline_stage`、`campaign_update`、`artifact_saved`、`verification_result`、`numerical_verification_result`、`memory_warning`。详见 [`API.md`](API.md)。

## 数学公式（KaTeX）

- 生成中：纯文本，避免未闭合公式报错  
- 生成后：`remark-math` + `rehype-katex`；`preprocessMath.ts` 做常见修复  
- 推荐：行内 `$...$` 同一行；复杂式用独立 `$$...$$`  
- 详情见应用内「帮助 → 公式显示」

## E2E

```bash
cd app/web && npx playwright test
```

三场景：课题、文献、导出（见 `app/web/e2e/`）。
