# API 量化测试结果

> **计划**：[`API-QUANT-TEST-PLAN.md`](API-QUANT-TEST-PLAN.md)  
> **探针**：`python scripts/api_quant_probe.py --batch {1|2|3|4}`  
> **环境**：本地 uvicorn（非容器）`127.0.0.1:8000`  
> **N**=3（标志性延迟 = warm `L_med`，单位 ms；例外见各批备注）

**进度**：Batch-1 · Batch-2 · Batch-3 · **Batch-4 全部完成**（分批量化闭环）

---

# Batch-1

> `api_key_valid=True`

## 部署记录

| 时间 (UTC) | 动作 |
|------------|------|
| 部署前 | 清理残留 PID（原 `--reload` uvicorn） |
| 首轮 | 探针 `batch1_20260718T125404Z` → **4 FAIL** |
| 修复后 | 重启 → `batch1_20260718T125457Z` → **0 FAIL**（11 PASS + 1 WARN） |

原始：`data/quant_probe/batch1_20260718T125404Z*` · `batch1_20260718T125457Z*`

## 复测汇总（权威）

| ID | Method Path | Tier | S | L_min | **L_med** | L_max | H_rid | B_schema | 判定 | 备注 |
|----|-------------|------|---|-------|-----------|-------|-------|----------|------|------|
| B1-01 | GET `/health` | T0 | 200 | 0.66 | **1.85** | 2.32 | ✓ | ✓ | PASS | |
| B1-02 | GET `/v1/sessions` | T1 | 200 | 0.74 | **0.83** | 1.68 | ✓ | ✓ | PASS | |
| B1-03 | DELETE `…/quant-b1-sess?purge=false` | T2 | 200 | 0.80 | **0.95** | 2.89 | ✓ | ✓ | PASS | |
| B1-04 | GET `…/quant-b1-sess` | T1 | 200 | 0.70 | **0.74** | 0.90 | ✓ | ✓ | PASS | |
| B1-05 | DELETE `…/quant-b1-sess?purge=true` | T2 | 200 | 1.38 | **10.97** | 15.11 | ✓ | ✓ | PASS | FX→404 |
| B1-06 | GET `…/quant-b1-missing` | T1 | 404 | 0.70 | **0.73** | 0.85 | ✓ | ✓ | PASS | 负例 |
| B1-07 | POST `/v1/chat` | T4 | 200 | 1072 | **1126** | 1338 | ✓ | ✓ | PASS | |
| B1-08 | POST `/v1/chat/stream` | T4 | 200 | 1069 | **1178** | 1239 | ✓ | ✓ | PASS | 终态 done |
| B1-09 | GET `/v1/agents` | T1 | 200 | 0.76 | **0.82** | 1.14 | ✓ | ✓ | PASS | |
| B1-10 | GET `/v1/mcp/status` | T1 | 200 | 0.72 | **0.85** | 1.26 | ✓ | ✓ | PASS | |
| B1-11 | POST `/v1/mcp/reload` | T2 | 200 | 2164 | **2515** | 2702 | ✓ | ✓ | **WARN** | stdio 重连 |
| B1-12 | GET `/v1/stats/tokens` | T1 | 200 | 0.73 | **0.81** | 1.53 | ✓ | ✓ | PASS | |

**通过率**：11/12（含 WARN；无 FAIL）。

## 首轮 FAIL → 修复

| ID | 根因 | 修复 |
|----|------|------|
| B1-05 | N=3 重复 purge | `ensure_session` |
| B1-07/08 | `mode:general` 非法 | `mode:chat` |
| B1-11 | MCP aclose 跨 task | `close()` 容忍 RuntimeError |

---

# Batch-2（Documents · Memory · Theory）

> 探针：`batch2_20260718T130157Z` · **24 PASS + 1 SKIP · 0 FAIL**

## 部署记录

| 动作 | 说明 |
|------|------|
| 清端口 | 杀旧 uvicorn → 无 reload 启动 `:8000` |
| 实测 | `python scripts/api_quant_probe.py --batch 2 --n 3` |
| 清理 | 删除工作区 `quant_b2_probe.md` |

原始：`data/quant_probe/batch2_20260718T130157Z.jsonl` · `*_summary.json`

## 汇总表

| ID | Method Path | Tier | S | L_min | **L_med** | L_max | H_rid | B_schema | 判定 | 备注 |
|----|-------------|------|---|-------|-----------|-------|-------|----------|------|------|
| B2-01 | POST `/v1/documents` | T2 | 200 | 44.83 | **47.89** | 456.51 | ✓ | ✓ | PASS | cold 偏高 |
| B2-02 | POST `/v1/documents/upload` | T2 | 200 | 39.59 | **40.4** | 44.26 | ✓ | ✓ | PASS | multipart |
| B2-03 | POST `/v1/documents/from-arxiv` | T3 | 200 | 5433 | **5433** | 5433 | ✓ | ✓ | PASS | N=1；1706.03762 |
| B2-04 | GET `/v1/documents` | T1 | 200 | 0.75 | **0.86** | 1.48 | ✓ | ✓ | PASS | |
| B2-05 | GET `…/rag-refs` | T1 | 200 | 0.92 | **0.95** | 1.18 | ✓ | ✓ | PASS | |
| B2-06 | DELETE `/v1/documents/{doc_id}` | T2 | 200 | 39.29 | **39.29** | 39.29 | ✓ | ✓ | PASS | N=1 |
| B2-07 | DELETE `…/session/quant-b2-sess` | T2 | 200 | 1.31 | **1.46** | 306.0 | ✓ | ✓ | PASS | cold 偏高 |
| B2-08 | DELETE `?purge=true` | — | — | — | — | — | — | — | **SKIP** | 全局破坏性 |
| B2-09 | GET `/v1/memory/structured` | T1 | 200 | 1.03 | **1.35** | 6.92 | ✓ | ✓ | PASS | |
| B2-10 | GET `/v1/memory/structured/global` | T1 | 200 | 0.96 | **1.13** | 1.73 | ✓ | ✓ | PASS | |
| B2-11 | GET `/v1/memory/structured/graph` | T1 | 200 | 1.28 | **1.35** | 1.87 | ✓ | ✓ | PASS | |
| B2-12 | POST `/v1/memory/structured` | T2 | 200 | 12.84 | **13.46** | 13.84 | ✓ | ✓ | PASS | |
| B2-13 | POST `…/versions` | T2 | 200 | 11.81 | **11.81** | 11.81 | ✓ | ✓ | PASS | N=1 |
| B2-14 | GET `…/versions` | T1 | 200 | 0.71 | **0.8** | 1.3 | ✓ | ✓ | PASS | |
| B2-15 | POST `…/edges` | T2 | 200 | 12.77 | **12.77** | 12.77 | ✓ | ✓ | PASS | N=1 |
| B2-16 | GET `/v1/theory/workspace` | T1 | 200 | 1.25 | **1.4** | 5.85 | ✓ | ✓ | PASS | |
| B2-17 | PUT `…/quant_b2_probe.md` | T2 | 200 | 0.96 | **1.13** | 1.49 | ✓ | ✓ | PASS | |
| B2-18 | GET `…/quant_b2_probe.md` | T1 | 200 | 0.81 | **0.83** | 0.91 | ✓ | ✓ | PASS | QUANT_B2_MARK |
| B2-19 | GET `/v1/theory/assumption-matrix` | T1 | 200 | 0.81 | **0.82** | 0.94 | ✓ | ✓ | PASS | |
| B2-20 | GET `/v1/theory/symbols` | T1 | 200 | 0.68 | **0.68** | 0.84 | ✓ | ✓ | PASS | |
| B2-21 | GET `/v1/theory/assumptions` | T1 | 200 | 0.72 | **0.73** | 0.79 | ✓ | ✓ | PASS | |
| B2-22 | GET `/v1/theory/assumption-dag` | T1 | 200 | 0.84 | **0.9** | 1.07 | ✓ | ✓ | PASS | |
| B2-23 | GET `…/impact/A4` | T1 | 200 | 0.8 | **0.81** | 1.51 | ✓ | ✓ | PASS | |
| B2-24 | GET `/v1/bibliography` | T1 | 200 | 0.8 | **0.81** | 1.34 | ✓ | ✓ | PASS | |
| B2-25 | GET `/v1/bibliography/export.bib` | T1 | 200 | 0.82 | **0.9** | 0.98 | ✓ | ✓ | PASS | |

**通过率**：`(24 PASS + 1 SKIP) / 25 = 100%`；无 FAIL，无需代码修复。

## Batch-2 后续

- B2-08 按设计 SKIP。
- Batch-3 已完成（见下）。

---

# Batch-3（Projects · Campaigns · Verification · Experiments）

> 探针：`batch3_20260718T131552Z` · **20 PASS · 0 FAIL**  
> 链式：`project_id=cc065643-ce7` · `task_id=4` · `campaign_id=f9b8fe3d-4ba` · `run_id=d7c04719`

## 部署记录

| 动作 | 说明 |
|------|------|
| 清端口 | 杀旧 uvicorn → 无 reload 启动 `:8000` |
| 实测 | `python scripts/api_quant_probe.py --batch 3 --n 3` |
| 残留 | 新建课题 `quant-b3-proj`（`cc065643-ce7`）保留，未删 |

原始：`data/quant_probe/batch3_20260718T131552Z.jsonl` · `*_summary.json`

## 汇总表

| ID | Method Path | Tier | S | L_min | **L_med** | L_max | 判定 | 备注 |
|----|-------------|------|---|-------|-----------|-------|------|------|
| B3-01 | GET `/v1/projects` | T1 | 200 | 0.87 | **1.1** | 27.11 | PASS | |
| B3-02 | POST `/v1/projects` | T2 | 200 | 13.17 | **13.17** | 13.17 | PASS | N=1；建 quant-b3-proj |
| B3-03 | GET `/v1/projects/{id}` | T1 | 200 | 0.75 | **0.85** | 1.38 | PASS | |
| B3-04 | GET `…/members` | T1 | 200 | 0.84 | **0.85** | 1.06 | PASS | list 响应 |
| B3-05 | POST `…/tasks` | T2 | 200 | 12.53 | **12.53** | 12.53 | PASS | N=1 |
| B3-06 | GET `…/tasks` | T1 | 200 | 1.02 | **1.04** | 1.33 | PASS | |
| B3-07 | PATCH `…/tasks/{tid}?status=in_progress` | T2 | 200 | 10.34 | **10.34** | 10.34 | PASS | N=1 |
| B3-08 | POST `…/sessions/quant-b3-sess` | T2 | 200 | 23.0 | **23.0** | 23.0 | PASS | N=1 |
| B3-09 | GET `…/sessions` | T1 | 200 | 0.97 | **1.04** | 1.53 | PASS | FX 含 sess |
| B3-10 | GET `…/campaigns` | T1 | 200 | 1.28 | **1.44** | 5.42 | PASS | |
| B3-11 | POST `…/campaign` | T2 | 200 | 23.87 | **23.87** | 23.87 | PASS | N=1 |
| B3-12 | GET `…/campaign` | T1 | 200 | 1.0 | **1.18** | 1.69 | PASS | 活跃 |
| B3-13 | GET `…/campaigns/{cid}` | T1 | 200 | 0.89 | **1.07** | 1.25 | PASS | |
| B3-14 | PATCH `…/campaigns/{cid}` | T2 | 200 | 7.66 | **7.66** | 7.66 | PASS | status=active |
| B3-15 | GET `/v1/verification/dashboard` | T1 | 200 | 0.94 | **1.08** | 4.85 | PASS | |
| B3-16 | GET `/v1/verification/records` | T1 | 200 | 1.21 | **1.26** | 1.87 | PASS | |
| B3-17 | POST `/v1/verification/run` | T3 | 200 | 118 | **118** | 118 | PASS | N=1；numerical |
| B3-18 | POST `/v1/experiments/runs` | T3 | 200 | 19.52 | **19.52** | 19.52 | PASS | N=1；quadratic_minimum |
| B3-19 | GET `/v1/experiments/runs` | T1 | 200 | 1.2 | **1.26** | 2.42 | PASS | |
| B3-20 | GET `/v1/experiments/runs/{run_id}` | T1 | 200 | 1.01 | **1.01** | 1.01 | PASS | |

**通过率**：`20/20 = 100%`；无 FAIL，无需代码修复 / 重测。

## Batch-3 后续

- Batch-4 已完成（见下）。

---

# Batch-4（Export · Observability · Sync · Jupyter）

> 探针：`batch4_20260718T132256Z` · **11 PASS + 1 PASS(expected) · 0 FAIL**

## 部署记录

| 动作 | 说明 |
|------|------|
| 清端口 | 杀旧 uvicorn → 无 reload 启动 `:8000` |
| 实测 | `python scripts/api_quant_probe.py --batch 4 --n 3` |
| 残留 | Jupyter `nb_*.json` 可保留于 experiments 日志目录 |

原始：`data/quant_probe/batch4_20260718T132256Z.jsonl` · `*_summary.json`

## 汇总表

| ID | Method Path | Tier | S | L_min | **L_med** | L_max | 判定 | 备注 |
|----|-------------|------|---|-------|-----------|-------|------|------|
| B4-01 | GET `/v1/export/preview` | T1 | 200 | 0.92 | **1.14** | 55.9 | PASS | |
| B4-02 | POST `/v1/export/md` | T2 | 200 | 0.86 | **0.94** | 1.37 | PASS | text/markdown；48B |
| B4-03 | POST `/v1/export/latex` | T2 | 200 | 1.51 | **2.13** | 2.87 | PASS | |
| B4-04 | POST `/v1/export/docx` | T2 | 200 | 205 | **205** | 205 | PASS | N=1；~10KB |
| B4-05 | POST `/v1/export/pdf` | T3 | 200 | 307 | **307** | 307 | PASS | N=1；application/pdf |
| B4-06 | POST `/v1/export/polish` | T4 | 200 | 1721 | **1721** | 1721 | PASS | N=1；AI 润色 |
| B4-07 | GET `/v1/observability/summary` | T1 | 200 | 1.13 | **1.33** | 14.67 | PASS | |
| B4-08 | GET `/v1/observability/agent-quality` | T1 | 200 | 1.0 | **1.04** | 1.24 | PASS | |
| B4-09 | POST `/v1/sync/metadata` | T2 | 403 | 2.75 | **2.75** | 2.75 | PASS(expected) | ENABLE_CLOUD_SYNC=false |
| B4-10 | GET `/v1/sync/audit/default` | T1 | 200 | 0.88 | **0.89** | 1.57 | PASS | |
| B4-11 | GET `/v1/jupyter/template` | T1 | 200 | 0.66 | **0.72** | 2.09 | PASS | loss_landscape |
| B4-12 | POST `/v1/jupyter/upload-result` | T2 | 200 | 2.45 | **2.45** | 2.45 | PASS | N=1 |

**通过率**：`12/12 = 100%`；无 FAIL，无需代码修复。

## 四批闭环

| 批次 | 结果 |
|------|------|
| Batch-1 | 11 PASS + 1 WARN（mcp/reload 延迟） |
| Batch-2 | 24 PASS + 1 SKIP（全局 purge） |
| Batch-3 | 20 PASS |
| Batch-4 | 11 PASS + 1 PASS(expected)（sync 403） |

量化排障覆盖 Health→Chat→Documents→Memory→Theory→Projects→Campaigns→Verification→Experiments→Export→Observability→Sync→Jupyter（与 API-COVERAGE 分域一致）。

## 修订记录

| 日期 | 说明 |
|------|------|
| 2026-07-18 | Batch-1 实测 + MCP close 小修 |
| 2026-07-18 | Batch-2 实测；探针 `--batch 2` |
| 2026-07-18 | Batch-3 实测；探针 `--batch 3`；20/20 PASS |
| 2026-07-18 | Batch-4 实测；探针 `--batch 4`；12/12；四批闭环 |
