# 已知问题清单（v2.2）

> 审查日期：2026-07-16 · 基线分支 `v2.2`  
> 修复后请把状态改为 `fixed` / `wontfix` / `deferred`。  
> **产品说明（2026-07-22）**：定位为「用深度学习解决科学问题」的理论侧多智能体（见 [`PRODUCT-VISION.md`](PRODUCT-VISION.md)）。Campaign / 书目 HTTP / 云同步 metadata 已移除；下文技术债仍有效。

## 严重

| ID | 状态 | 问题 | 位置 |
|----|------|------|------|
| C1 | fixed | `.dockerignore` 曾排除全部 `*.md`；已放行 `data/theory/**/*.md` 与 `doc/**/*.md` | `.dockerignore` |
| C2 | open | API 无鉴权 + CORS `allow_origins=["*"]`，不宜公网裸奔 | `app/server/main.py` |
| C3 | fixed | 版本号已统一为文档/包/OpenAPI **2.2.0**（web 前端 `package.json` 可另跟） | `pyproject.toml` / `main.py` / README |

## 高

| ID | 状态 | 问题 | 位置 |
|----|------|------|------|
| H1 | open | CI 仅触发 `main`/`master`，日常 `v2.2`/`dev` 推送不一定跑 | `.github/workflows/ci.yml` |
| H2 | open | 理论工作区路径校验用 `startswith`，弱于 `relative_to` | `api/theory.py` |
| H3 | open | 数值表达式使用受限 `eval` | `verification_executor.py`、`numerical.py` |
| H4 | fixed | 已在 `ENV.md` / README 标明「代码默认 vs 演示 `.env.example`」 | `doc/ENV.md` |

## 中低

| ID | 状态 | 问题 |
|----|------|------|
| M1 | open | `main.py` 启动注释缺 `--app-dir app` |
| M2 | open | `data/theory/lemmas/` 为空，全局引理同步收益有限 |
| L1 | open | LangGraph / Starlette / Chroma 弃用警告较多 |
| M3 | fixed | `POST /v1/mcp/reload` 跨 task `aclose` 曾 500；`MCPClient.close` 已容忍并重建（量化 Batch-1 / `mcp/client.py`） |

## 建议修复顺序

1. ~~修 `.dockerignore`~~（已放行理论种子 md）
2. CI 增加 `v2.2`/`dev` 或统一主干分支
3. 路径校验与 `eval` 加固；部署鉴权
4. 充实 `data/theory/lemmas/` 种子
