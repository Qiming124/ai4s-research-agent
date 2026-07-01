# 项目文档索引

本目录为 AI4S 科研辅助 Agent 的中文技术文档。代码内注释与本文档保持一致风格。

| 文档 | 说明 |
|------|------|
| [架构说明](ARCHITECTURE.md) | 分层结构、数据流、多 Agent / MCP / RAG |
| [环境变量](ENV.md) | `conf/.env` 全量配置说明 |
| [API 参考](API.md) | HTTP 端点、SSE 事件、请求/响应字段 |
| [部署指南](DEPLOY.md) | 本地开发、Docker、云服务器、镜像仓库 |
| [MCP 配置](mcp-config.md) | MCP Server 启用、扩展与白名单 |
| [开发辅助工具清单](dev-tooling-checklist.md) | MCP / Skills / Rules 推荐与勾选清单（含项目侧） |
| [Cursor IDE 安装清单](cursor-ide-tooling-checklist.md) | **仅 Cursor 编辑器**：MCP / Skills / Rules / Hooks |
| [代码注释规范](CODE_STYLE.md) | Python/TS 中文 docstring 约定 |
| [Docker 部署](docker.md) | 镜像构建与 compose |
| [前端开发](web.md) | Vite + React 构建说明 |

其他：

| 路径 | 说明 |
|------|------|
| [../README.md](../README.md) | 项目总览与快速启动 |

## 目录布局

```
agent/
├── README.md          # 项目总览（保留在根目录）
├── app/               # 全部应用代码
│   ├── server/        # FastAPI 后端
│   ├── client/        # CLI
│   ├── shared/        # 共享 schema 与路径常量
│   └── web/           # React 前端
├── conf/              # 配置模板与 MCP JSON
├── doc/               # 技术文档（本目录）
├── log/               # 运行时日志（app.log）
├── data/              # 会话 DB、Chroma、MCP 文件
└── docker/            # Dockerfile 与 compose
```

## 阅读建议

1. 新用户：根目录 `README.md` → `ENV.md` → 启动后端与 Web
2. 部署运维：`DEPLOY.md` → `docker.md`
3. 工具扩展：`mcp-config.md`
4. 对接 API：`API.md` + `app/shared/schemas.py`
