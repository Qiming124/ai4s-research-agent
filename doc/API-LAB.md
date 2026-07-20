# API 测试实验室（自研，非 Swagger）

独立于主聊天页的接口测试前端。从后端 `GET /openapi.json` 动态加载全部路由，填参执行后查看真实响应（JSON / SSE / 文件下载）。

## 与 `/docs` 的区别

| | `/docs`（FastAPI Swagger） | `#/api-lab`（本实验室） |
|--|---------------------------|-------------------------|
| 来源 | 官方 Swagger UI | 项目自研 React 页面 |
| 目的 | 契约浏览 + 简易试调（**中文 summary / 字段说明 / 样例值**） | **接口测试**：耗时、历史、SSE 时间线、blob 下载 |
| 入口 | `http://127.0.0.1:8000/docs` | 主站顶栏「API 测试」或 `http://localhost:5173/#/api-lab` |

两者可并存；实验室不嵌入 swagger-ui 包。OpenAPI 中文注解写在后端路由 `summary` / docstring 与 [`app/shared/schemas.py`](../app/shared/schemas.py) 的 `Field(description/examples)`，经 `/openapi.json` 同时供给 Swagger 与本实验室。

## 启动

1. 后端：`uvicorn server.main:app --app-dir app --port 8000`
2. 前端：`cd app/web && npm run dev` → 打开 Vite 地址
3. 点顶栏 **API 测试**，或访问 `#/api-lab`

开发态 Vite 已代理 `/v1`、`/health`、`/openapi.json`、`/docs`。

## 界面

- **左**：按 OpenAPI tag 分组的接口目录（可搜索）
- **中**：path/query 参数与 JSON body；可勾选「按 SSE 解析」
- **右**：状态码、耗时、Headers、JSON / SSE 事件 / 下载；下方为 localStorage 历史
- **滚动 / 拖拽**：三栏各自可上下滚动；栏间竖条可左右拖拽调宽（宽度记在 `localStorage` 键 `ai4s_api_lab_layout`）。窄屏自动堆叠并隐藏拖拽条。

顶部快捷场景：健康检查、列课题、列会话、MCP 状态、导出预览、流式对话 SSE。

## 测 SSE

1. 点预设「流式对话 SSE」，或选 `POST /v1/chat/stream`
2. 勾选「按 SSE 解析响应」
3. 执行：右侧会出现事件时间线（`meta` / `content` / `done` 等）
4. 可随时点「停止」中断

注意：会真实调用 LLM，消耗 token。

## 源码位置

| 路径 | 说明 |
|------|------|
| `app/web/src/apiLab/` | 框架：openapi / executor / sseRunner / history / presets / layout |
| `app/web/src/components/ApiLabPage.tsx` | 三栏 UI（滚动 + ResizeHandle） |
| `app/web/src/App.tsx` | hash 路由 `#/` / `#/api-lab` |

## 非目标

不替代 `tests/` pytest；无鉴权面板；不做 CI 录制回放。
