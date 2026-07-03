# Web 前端

Vite + React + TypeScript 聊天界面，支持 SSE 流式、MCP 状态、RAG 文档管理、多会话。

> **路径**：前端源码在 **`app/web/`**（不是根目录 `web/`）。生产构建产物为 `app/web/dist`，由 `app/server/main.py` 托管。

## 环境要求

- Node.js 18+
- 后端已启动在 `http://127.0.0.1:8000`（`uvicorn server.main:app --app-dir app`）

## 开发

```bash
cd app/web
npm install
npm run dev
```

打开 http://localhost:5173。Vite 将 `/v1` 等 API 代理到 8000。

### SSE 流式（开发模式）

`POST /v1/chat/stream` 使用 `text/event-stream`。开发代理已在 [`vite.config.ts`](../app/web/vite.config.ts) 中对 SSE 响应设置 `X-Accel-Buffering: no`，避免 http-proxy 缓冲导致前端「整轮结束才收到事件」。若流式仍异常，可对比：

- 直连后端：`curl -N -X POST http://127.0.0.1:8000/v1/chat/stream ...`
- 经 Vite：`curl -N -X POST http://127.0.0.1:5173/v1/chat/stream ...`

生产环境由 FastAPI 直接托管静态资源，或 Nginx 反代时需 `proxy_buffering off`（见 [`DEPLOY.md`](DEPLOY.md)）。

## 生产构建

```bash
cd app/web
npm run build
```

产物在 **`app/web/dist`**。由 FastAPI `app/server/main.py` 在 8000 端口托管，**不要**在生产环境单独跑 `npm run dev`。

Docker 镜像在 build 阶段自动执行 `npm run build`（工作目录 `app/web`）。

## 主要目录

| 路径 | 说明 |
|------|------|
| `app/web/src/components/ChatPage.tsx` | 三栏主页面 |
| `app/web/src/hooks/useChatStream.ts` | SSE 流式与消息状态 |
| `app/web/src/components/MarkdownContent.tsx` | Markdown + KaTeX 数学公式 |
| `app/web/src/utils/preprocessMath.ts` | LaTeX 渲染前自动修复 |
| `app/web/src/utils/preferences.ts` | 本地偏好（模式、MCP、历史策略） |
| `app/web/src/utils/session.ts` | 会话列表 localStorage |

## 功能

- 左侧会话列表（新建/切换/删除）
- 中间对话区（流式、停止、思考过程开关、工作流时间线、Loss Landscape 内嵌图）
- 右侧设置与科研工作台（定理库、知识图谱、实验日志、理论工作区、RAG 文档）
- 顶栏连接状态、Token 统计、当前 Agent 指示、**帮助**面板（v0.4 全量说明）
- 多 Agent 路由（general / theory / experiment / literature / review）
- SSE 新事件：`pipeline_stage`、`numerical_verification_result`、`memory_warning`

## 科研工作台面板（v0.4）

| 组件 | 路径 | 说明 |
|------|------|------|
| `TheoremLibraryPanel` | `components/TheoremLibraryPanel.tsx` | L4 结构化记忆（引理/定理/假设） |
| `KnowledgeGraphPanel` | `components/KnowledgeGraphPanel.tsx` | L4 节点与 `depends_on` / `cites` 边 |
| `ExperimentLogPanel` | `components/ExperimentLogPanel.tsx` | `data/experiments/logs/` JSON 运行记录 |
| `WorkspacePanel` | `components/WorkspacePanel.tsx` | `data/theory/` 种子文件浏览 |
| `LossLandscapeViz` | `components/LossLandscapeViz.tsx` | 2D loss 等高线 / SGD 轨迹摘要 |

对应 Hooks：`useStructuredMemory`、`useMemoryGraph`、`useExperimentLogs`、`useWorkspaceFiles`。

## 主要目录（补充）

| 路径 | 说明 |
|------|------|
| `app/web/src/components/HelpPanel.tsx` | 顶栏「帮助」弹层（Agent、记忆、验证、工作台） |
| `app/web/src/components/WorkflowTimeline.tsx` | 规划 → 工具 → SymPy/数值验证 → 综合 |
| `app/web/src/components/MessageBubble.tsx` | 消息气泡 + Loss Landscape 嵌入 |
| `app/web/src/hooks/useChatStream.ts` | SSE 流式与 `pipeline_stage` 等事件 |

依赖 `remark-math`（须在 `remark-gfm` **之前**）+ `rehype-katex`，KaTeX CSS 在 `index.html` CDN 引入。

| 阶段 | 行为 |
|------|------|
| 流式生成中 | 纯文本，不跑 KaTeX |
| 生成完成后 | 经 `preprocessMath.ts` 修复后渲染 |

**自动修复**（`preprocessMath.ts`）：裸 `\begin{cases}...`、缺开头 `$$`、跨行 `$...$`、未闭合 `$` / `\end{cases}`、模型误用 `\sum{m}` / `\lambda{\max}` / `\hat{y}k` 等下标写法、重复「代入得：」、标题与公式粘连等。

**推荐写法**：

- 行内：`$y$`、`$L_{\text{MSE}}$`（同一行，勿换行拆开）
- 块级：独立成行的 `$$...$$`；`cases`、矩阵、多行推导必须用 `$$`

**Math 模式**（Web 侧栏或 `mode=math`）会引导模型输出更规范的 LaTeX。若仍显示琥珀色原文，说明 LaTeX 不完整，可要求模型用完整 `$$...$$` 重写。

详见根目录 `README.md`「Web 数学公式」与 Web 内「帮助 → 公式显示」。

## 数学公式
