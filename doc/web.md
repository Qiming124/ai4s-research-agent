# Web 前端（v2.2）

Vite + React + TypeScript。源码在 **`app/web/`**；生产产物 `app/web/dist` 由 `app/server/main.py` 托管。

产品定位：言晖科研助手工作台（文献 · 推导 · 实验建议/数据解读 · 产出），见 [`PRODUCT-VISION.md`](PRODUCT-VISION.md)。

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
| 左栏 | `ProjectSessionTree` | 课题文件夹树（含会话） |
| 中栏 | `ChatPage` + `MessageBubble` + 时间线 | SSE 对话、CoT、工具轨迹 |
| 右栏 | `ResearchWorkbench` | Tabs：文献（读与入库）/ 理论（推导资产）/ 产出（实验建议相关记录 + 导出） |
| 顶栏 | `TopStatusBar` / `HelpPanel` / `ObservabilityPanel` | Agent、MCP、Token、帮助、质量 |

## 界面版本

仅前端展示层（`localStorage` 键 `ai4s_ui_edition`），**不**做后端鉴权。默认 **`research`（科研版）**。在「设置 → 界面版本」切换。实现见 `app/web/src/utils/uiEdition.ts`。历史 `full`（完整版）已移除，读到时自动迁移为 `research`。

| 版本 id | 名称 | 左栏 | 右栏工作台 | 其它 |
|---------|------|------|------------|------|
| `chat` | 对话版 | 会话树 | 整栏隐藏（双栏布局） | 仍显示「AI润色提示词」；切到此版时 Agent 置为 `auto` |
| `research` | 科研版（默认） | 会话树（课题文件夹） | 文献 / 理论 / 产出 | 产出含用户结果回传与导出；侧重建议与解读，非代跑实验 |

嵌套面板（图谱、实验日志等）仍挂在对应 Tab 内。

### 附属材料挂靠

| 材料 | 范围 |
|------|------|
| RAG 文献语料、课题实验产物 | **课题**（`data/projects/{id}/`） |
| 聊天消息、RAG 引用轨迹 | **会话**（发消息时带 `project_id` 会自动挂靠课题） |
| `data/theory/` | 历史参考种子；**不再**复制进新课题，**不再**注入 prompt |

## 工作台与关键组件

| 组件 | 说明 |
|------|------|
| `DocumentPanel` / `RagRefsPanel` | 文献入库、RAG 引用 |
| `TheoremLibraryPanel` / `ArtifactsPanel` | 定理库 CRUD、推导迹 / 实验计划工件；方法卡、假设 DAG、关系图谱、工作区文件编辑 UI 已下线 |
| `VerificationDashboard` | 验证账本（遗留/可选） |
| `ExperimentLogPanel` | 用户提交的实验/Notebook 结果记录（供顾问解读） |
| `ExportPanel` | preview / polish / md / latex / docx / pdf |
| `OnboardingWizard` | 首次引导（文献→推导→实验建议/数据→产出） |
| `ErrorBoundary` | 渲染错误隔离 |

主要 Hooks：`useChatStream`、`useDocuments`、`useStructuredMemory`、`useArtifacts`、`useExperimentLogs` 等。

## Agent 与 SSE

支持 Agent：`general` / `theory` / `experiment`（实验顾问）/ `literature` / `review` / `counterexample`。  
主路径 SSE：`workflow_step`、`tool_call_*`、`reasoning`、`content`、`artifact_saved`、`done`。验证类事件可选。详见 [`API.md`](API.md)。

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
