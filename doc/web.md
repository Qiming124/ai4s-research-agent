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
- 中间对话区（流式、停止、思考过程开关）
- 右侧设置（Chat/Math、L1、MCP、RAG 文档）
- 顶栏连接状态与 Token 统计

## 数学公式

依赖 `remark-math`（须在 `remark-gfm` **之前**）+ `rehype-katex`，KaTeX CSS 在 `index.html` CDN 引入。

| 阶段 | 行为 |
|------|------|
| 流式生成中 | 纯文本，不跑 KaTeX |
| 生成完成后 | 经 `preprocessMath.ts` 修复后渲染 |

**自动修复**（`preprocessMath.ts`）：裸 `\begin{cases}...`、缺开头 `$$`、跨行 `$...$`、未闭合 `$` / `\end{cases}` 等。

**推荐写法**：

- 行内：`$y$`、`$L_{\text{MSE}}$`（同一行，勿换行拆开）
- 块级：独立成行的 `$$...$$`；`cases`、矩阵、多行推导必须用 `$$`

**Math 模式**（Web 侧栏或 `mode=math`）会引导模型输出更规范的 LaTeX。若仍显示琥珀色原文，说明 LaTeX 不完整，可要求模型用完整 `$$...$$` 重写。

详见根目录 `README.md`「Web 数学公式」与 Web 内「帮助 → 公式显示」。
