# 项目文档索引（v2.2）

本目录为 **AI4S 理论侧科研助手** 的中文技术文档。

**产品定位**：面向「用深度学习解决科学问题」的 **理论侧多智能体**——文献检索与方法提炼、理论推导、实验建议与数据解读；**不**以全流程科研复现或代跑训练为核心。损失函数局部极小等为示范子集。蓝图见 [`PRODUCT-VISION.md`](PRODUCT-VISION.md)。

| 文档 | 说明 |
|------|------|
| [产品愿景](PRODUCT-VISION.md) | 理论侧定位、能力边界、下期 Agent/工件设计 |
| [架构说明](ARCHITECTURE.md) | 产品边界、全景图、分层、多 Agent / MCP / 场景工作流 |
| [环境变量](ENV.md) | `conf/.env` 全量配置（代码默认 vs 演示配置） |
| [API 参考](API.md) | 端点速查、SSE、ChatRequest |
| [API 覆盖清单](API-COVERAGE.md) | **71** 端点 · UI/Test 矩阵（权威清单） |
| [API 全路径链路](API-ROUTES.md) | 分域契约 + HTTP→实现调用链 |
| [API 量化测试计划](API-QUANT-TEST-PLAN.md) | MUT 定义、指标阈值、分批清单 |
| [API 量化测试结果](API-QUANT-TEST-RESULTS.md) | Batch 1–4 实测延迟与判定（分批闭环） |
| [功能验收方案](acceptance/ACCEPTANCE-TEST-PLAN.md) | L1–L3 功能/隔离/黄金路径验收设计 |
| [功能验收报告](acceptance/ACCEPTANCE-REPORT.md) | 2026-07-22 实跑结论（核心通过） |
| [数据目录](DATA.md) | 种子 vs 运行时；开发期清理建议 |
| [已知问题](KNOWN_ISSUES.md) | 审查遗留项（Docker 种子、鉴权、版本号等） |
| [部署指南](DEPLOY.md) | 本地、Docker、云服务器 |
| [Docker 部署](docker.md) | 镜像构建与 compose |
| [MCP 配置](mcp-config.md) | 内置 Server、白名单、扩展 |
| [前端开发](web.md) | Vite + React、工作台、E2E |
| [Cursor IDE 清单](cursor-ide-tooling-checklist.md) | 编辑器侧 MCP / Skills / Rules |
| [代码注释规范](CODE_STYLE.md) | Python/TS 中文 docstring |
| [后端代码阅读顺序](CODE_READING_ORDER.md) | **源码通读路线图**（先主路径再分域；暂不含前端） |
| [API 测试实验室](API-LAB.md) | 自研接口测试页（`#/api-lab`，非 Swagger） |

其他：根目录 [`../README.md`](../README.md) 总览与快速启动。

## 阅读建议

1. 新用户：根 `README.md` → [`PRODUCT-VISION.md`](PRODUCT-VISION.md) → `ENV.md` → 启动后端与 Web  
2. **通读后端源码**：[`CODE_READING_ORDER.md`](CODE_READING_ORDER.md)（推荐按日历推进）  
3. **测接口**：主站 `#/api-lab` 或 [`API-LAB.md`](API-LAB.md)；契约对照仍可用 `GET /docs`  
4. 对接 API：`API-COVERAGE.md` → `API-ROUTES.md`（全链路）→ `API.md` → `app/shared/schemas.py` / `GET /docs`  
5. 部署：`DEPLOY.md` → `docker.md`；注意 `DATA.md` 与 `KNOWN_ISSUES.md`  
6. 扩展工具：`mcp-config.md` · 前端：`web.md`
