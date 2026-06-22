# 项目文档索引

本目录为 AI4S 科研辅助 Agent 的中文技术文档。代码内注释与本文档保持一致风格。

| 文档 | 说明 |
|------|------|
| [架构说明](ARCHITECTURE.md) | 分层结构、数据流、多 Agent / MCP / RAG |
| [环境变量](ENV.md) | `.env` 全量配置说明 |
| [API 参考](API.md) | HTTP 端点、SSE 事件、请求/响应字段 |
| [部署指南](DEPLOY.md) | 本地开发、Docker、云服务器、镜像仓库 |
| [MCP 配置](mcp-config.md) | MCP Server 启用、扩展与白名单 |
| [代码注释规范](CODE_STYLE.md) | Python/TS 中文 docstring 约定 |

其他文档：

| 路径 | 说明 |
|------|------|
| [../README.md](../README.md) | 项目总览与快速启动 |
| [../docker/README.md](../docker/README.md) | Docker 构建与 compose |
| [../web/README.md](../web/README.md) | 前端开发与构建 |

## 阅读建议

1. 新用户：根目录 `README.md` → `ENV.md` → 启动后端与 Web
2. 部署运维：`DEPLOY.md` → `docker/README.md`
3. 工具扩展：`mcp-config.md`
4. 对接 API：`API.md` + `shared/schemas.py`
