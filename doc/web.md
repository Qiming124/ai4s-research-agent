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
| 左栏 | `ProjectSessionTree` / `TaskBoard` | 课题文件夹树（含会话）+ 完整版任务看板 |
| 中栏 | `ChatPage` + `MessageBubble` + 时间线 | SSE 对话、CoT、工具、验证、Loss Landscape |
| 右栏 | `ResearchWorkbench` | Tabs：文献 / 理论 / 验证 / 图谱 / 实验 / 导出 |
| 顶栏 | `TopStatusBar` / `HelpPanel` / `ObservabilityPanel` | Agent、MCP、Token、帮助、质量 |

流水线 SSE `pipeline_stage` 可自动切换工作台 Tab（`workbenchTabs` 相关逻辑）；切换时会按当前**界面版本**钳制到可见 Tab（例如科研版不会切到「验证」）。

## 界面版本

仅前端展示层（`localStorage` 键 `ai4s_ui_edition`），**不**做后端鉴权。默认 **`research`（科研版）**。在「设置 → 界面版本」切换。实现见 `app/web/src/utils/uiEdition.ts`。

| 版本 id | 名称 | 左栏 | 右栏工作台 | 其它 |
|---------|------|------|------------|------|
| `chat` | 对话版 | 会话树 | 整栏隐藏（双栏布局） | 隐藏「AI润色提示词」；切到此版时 Agent 置为 `auto` |
| `research` | 科研版（默认） | 会话树（课题文件夹） | 文献 / 理论 / 产出 | 无任务 Tab、无验证 Tab；文件夹头可看 Campaign 简要进度 |
| `full` | 完整版 | 会话树 + 任务 | 文献 / 理论 / 验证 / 产出 | 与原先全能力一致 |

嵌套面板（图谱、可观测、实验日志等）仍挂在对应 Tab 内，不随版本再拆子开关。

### 附属材料挂靠

| 材料 | 范围 |
|------|------|
| RAG 文献语料、理论工作区、书目 | **课题**（`data/projects/{id}/`） |
| 聊天消息、RAG 引用轨迹 | **会话** |
| `data/theory/` | 只读种子模板，新建课题时复制进课题工作区 |

## 工作台与关键组件

| 组件 | 说明 |
|------|------|
| `DocumentPanel` / `RagRefsPanel` | 文献入库、RAG 引用 |
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
- 生成后：`remark-gfm` → `remark-math` → `rehype-katex`；[`preprocessMath.ts`](../app/web/src/utils/preprocessMath.ts) 做常见修复  
- 推荐：行内 `$...$` 同一行；复杂式用独立 `$$...$$`  
- 已覆盖的乱码场景：`pmatrix`/`bmatrix` 后粘中文标点、`$$` 粘「其中/故」、GFM 表内 `L_0`、代码围栏内裸 LaTeX（不注入 `$`）  
- 回归：`cd app/web && npm run test:math`  
- 详情见应用内「帮助 → 公式显示」

## E2E

```bash
cd app/web && npx playwright test
```

三场景：课题、文献、导出（见 `app/web/e2e/`）。
