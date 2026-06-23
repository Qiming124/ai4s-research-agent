# Web 前端

Vite + React + TypeScript 聊天界面，支持 SSE 流式、MCP 状态、RAG 文档管理、多会话。

## 环境要求

- Node.js 18+
- 后端已启动在 `http://127.0.0.1:8000`

## 开发

```bash
cd web
npm install
npm run dev
```

打开 http://localhost:5173。Vite 将 `/v1` 等 API 代理到 8000。

## 生产构建

```bash
npm run build
```

产物在 `web/dist`。由 FastAPI `server/main.py` 在 8000 端口托管，**不要**在生产环境单独跑 `npm run dev`。

Docker 镜像在 build 阶段自动执行 `npm run build`。

## 主要目录

| 路径 | 说明 |
|------|------|
| `src/components/ChatPage.tsx` | 三栏主页面 |
| `src/hooks/useChatStream.ts` | SSE 流式与消息状态 |
| `src/components/MarkdownContent.tsx` | Markdown + KaTeX 数学公式 |
| `src/utils/preferences.ts` | 本地偏好（模式、MCP、历史策略） |
| `src/utils/session.ts` | 会话列表 localStorage |

## 功能

- 左侧会话列表（新建/切换/删除）
- 中间对话区（流式、停止、思考过程开关）
- 右侧设置（Chat/Math、L1、MCP、RAG 文档）
- 顶栏连接状态与 Token 统计

## 数学公式

依赖 `remark-math` + `rehype-katex`，KaTeX CSS 在 `index.html` CDN 引入。流式阶段为纯文本，结束后渲染公式。
