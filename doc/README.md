# 项目文档索引（v2.2）

本目录为 AI4S 科研辅助 Agent 的中文技术文档。

| 文档 | 说明 |
|------|------|
| [系统架构图](SYSTEM_ARCHITECTURE.md) | 分层架构、数据流、记忆与 CoT 全景图 |
| [架构说明](ARCHITECTURE.md) | 分层、多 Agent / MCP / RAG / Campaign |
| [环境变量](ENV.md) | `conf/.env` 全量配置（代码默认 vs 演示配置） |
| [API 参考](API.md) | 端点说明、SSE、ChatRequest |
| [API 覆盖清单](API-COVERAGE.md) | **67** 端点 · UI/Test 矩阵（权威清单） |
| [数据目录](DATA.md) | 种子 vs 运行时；开发期清理建议 |
| [已知问题](KNOWN_ISSUES.md) | 审查遗留项（Docker 种子、鉴权、版本号等） |
| [部署指南](DEPLOY.md) | 本地、Docker、云服务器 |
| [Docker 部署](docker.md) | 镜像构建与 compose |
| [MCP 配置](mcp-config.md) | 内置 Server、白名单、扩展 |
| [前端开发](web.md) | Vite + React、工作台、E2E |
| [Cursor IDE 清单](cursor-ide-tooling-checklist.md) | 编辑器侧 MCP / Skills / Rules |
| [代码注释规范](CODE_STYLE.md) | Python/TS 中文 docstring |

其他：根目录 [`../README.md`](../README.md) 总览与快速启动。

## 阅读建议

1. 新用户：根 `README.md` → `ENV.md` → 启动后端与 Web  
2. 对接 API：`API-COVERAGE.md` → `API.md` → `app/shared/schemas.py`  
3. 部署：`DEPLOY.md` → `docker.md`；注意 `DATA.md` 与 `KNOWN_ISSUES.md`  
4. 扩展工具：`mcp-config.md` · 前端：`web.md`
