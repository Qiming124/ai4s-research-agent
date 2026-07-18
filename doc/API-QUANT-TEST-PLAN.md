# API 量化测试计划（MUT · 指标 · 分批）

> **版本**：v1.0 · **范围**：对本地 uvicorn（非容器）的真实 HTTP 探针  
> **契约**：[`API-COVERAGE.md`](API-COVERAGE.md)（67）· [`API-ROUTES.md`](API-ROUTES.md) · `GET /docs`  
> **结果表**：[`API-QUANT-TEST-RESULTS.md`](API-QUANT-TEST-RESULTS.md)  
> **探针**：[`scripts/api_quant_probe.py`](../scripts/api_quant_probe.py)

现有 `tests/api/`（`TestClient`）只做进程内冒烟，**不替代**本计划的 live RTT / 副作用量化。

---

## 1. 单接口最小单元（MUT）

每个端点一次「最小可判定调用」= **1 MUT**：

| 步骤 | 说明 |
|------|------|
| 准备 | 依赖 ID 固定前缀 `quant-b1-*`（后续批用 `quant-b2-*`…） |
| 调用 | 固定 method / path / query / body（见附录） |
| 观测 | `http_status`、`latency_ms`、`X-Request-ID`、关键 body 字段、可选副作用 |
| 判定 | `PASS` / `WARN` / `FAIL` / `SKIP` / `PASS(expected)` |
| 重复 | 默认 **N=3**；标志性延迟用 **median**（`L_med`） |

**判定优先级**：结构/语义错误 → `FAIL`；仅超延迟档 → `WARN`；环境预期（功能关闭等）→ `PASS(expected)`；缺有效 API Key 的 LLM 路径 → `SKIP`（注明条件）。

冷启动：第 1 次可标 `cold`；判定以第 2–3 次 warm 的 median 为准，cold 单独记一行。

---

## 2. 量化指标（标志性）

| 指标 ID | 含义 | 采集 | 阈值规则 |
|---------|------|------|----------|
| `S` | HTTP 状态 ∈ 期望集合 | 每次响应 | 否 → FAIL |
| `L_med` | N=3 延迟中位数 (ms) | `time.perf_counter` | 见档位表 |
| `L_max` | N=3 最大延迟 (ms) | 同上 | &gt; 档位 PASS 上限 ×2 → WARN |
| `H_rid` | 存在响应头 `X-Request-ID` | headers | 缺失 → WARN |
| `B_schema` | 关键 JSON 字段齐全 | 解析 body | 缺字段 → FAIL |
| `FX` | 副作用与 ROUTES 一致 | 二次 GET / 文件 | 不符 → FAIL |
| `SSE_ttfb` | 首个 `data:` 帧 (ms) | stream | 有 Key：&lt; 5000；无 Key：快速 error/finish 或 SKIP |
| `SSE_done` | 出现终态事件 | stream | 60s 内无 `finish`/`error`/`done` → FAIL |

### 延迟档位

| 档 | 适用 | `L_med` PASS | `L_med` WARN | `L_med` FAIL |
|----|------|--------------|--------------|--------------|
| T0 | `/health` | ≤ 50 | ≤ 200 | &gt; 200 |
| T1 | 纯读本地/SQLite | ≤ 300 | ≤ 1000 | &gt; 3000 |
| T2 | 轻写本地 | ≤ 800 | ≤ 2000 | &gt; 5000 |
| T3 | 验证/实验/MCP 数值 | ≤ 30000 | ≤ 90000 | &gt; 180000 |
| T4 | LLM（chat / polish） | ≤ 60000 | ≤ 120000 | &gt; 180000 或无终态 |

**批次通过率**：`(PASS + PASS(expected) + SKIP) / 已测 MUT`。每个 `FAIL` 必须有问题描述 + 修复或 `KNOWN_ISSUES` 条目。

---

## 3. 分批范围

| 批次 | 域 | 约端点数 | 状态 |
|------|-----|----------|------|
| Batch-1 | Health · Chat/Sessions · Agents · MCP · Stats | 12 | 已完成 |
| Batch-2 | Documents · Memory · Theory/Bibliography | 22+1 SKIP | 已完成 |
| Batch-3 | Projects · Campaigns · Verification · Experiments | ~20 | 已完成 |
| Batch-4 | Export · Observability · Sync · Jupyter | 12 | **已完成** |

---

## 4. 部署检查清单（非容器）

每次改代码或重测前：

```bash
# 1) 查占用 8000 的进程
ss -tlnp | grep ':8000' || true
pgrep -af 'uvicorn|server.main' || true

# 2) 结束残留（按 PID 谨慎 kill）
# kill <pid>

# 3) 启动（项目根目录，已激活 venv）
cd /home/agent
source .venv/bin/activate   # 若使用 venv
uvicorn server.main:app --host 0.0.0.0 --port 8000 --app-dir app

# 4) 就绪探测
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/health
```

禁止本轮使用 Docker / compose。前端 Vite 对本批 API 探针**非必须**。

---

## 5. 探针输出约定

```text
data/quant_probe/batch1_<timestamp>.jsonl
```

每行字段：`endpoint_id,method,path,attempt,status,latency_ms,rid,verdict,note`（另可含 `sse_ttfb_ms`、`schema_ok`、`cold`）。

运行：

```bash
python scripts/api_quant_probe.py --batch 1 --base-url http://127.0.0.1:8000 --n 3
```

---

## 附录 A · Batch-1 MUT 清单

固定会话：`quant-b1-sess`。短 prompt，避免烧额度。

| ID | Method | Path | Tier | 期望 `S` | `B_schema` 关键字段 | 备注 |
|----|--------|------|------|----------|-------------------|------|
| B1-01 | GET | `/health` | T0 | {200} | `status`,`model`,`reasoning_effort`；`status==ok` | 冷/warm 分行 |
| B1-02 | GET | `/v1/sessions` | T1 | {200} | `sessions`,`total` | |
| B1-03 | DELETE | `/v1/sessions/quant-b1-sess?purge=false` | T2 | {200} | `status`,`session_id`；`status==cleared` | 副作用：会话可存在 |
| B1-04 | GET | `/v1/sessions/quant-b1-sess` | T1 | {200} | `session_id`,`messages` | 依赖 B1-03 |
| B1-05 | DELETE | `/v1/sessions/quant-b1-sess?purge=true` | T2 | {200} | `status==deleted` | 每次前 `ensure_session`；FX：再 GET → 404 |
| B1-06 | GET | `/v1/sessions/quant-b1-missing` | T1 | {404} | — | 负例 |
| B1-07 | POST | `/v1/chat` | T4 | {200} 或无 Key 时 SKIP / 502→`PASS(expected)` | 200 时：`session_id`,`content` | body 见下；`enable_tools=false` |
| B1-08 | POST | `/v1/chat/stream` | T4 | SSE 200 | `SSE_ttfb`/`SSE_done` | 同上 body；终态含 finish/error |
| B1-09 | GET | `/v1/agents` | T1 | {200} | `orchestration_backend`,`agents`；含 `counterexample` | |
| B1-10 | GET | `/v1/mcp/status` | T1 | {200} | `server_enabled`,`connected`,`servers` | |
| B1-11 | POST | `/v1/mcp/reload` | T2 | {200} 若 ENABLE_MCP；否则 {400}→`PASS(expected)` | 200 时同 status schema | |
| B1-12 | GET | `/v1/stats/tokens` | T1 | {200} | `filters`,`totals`,`by_agent` | |

### Chat body（B1-07 / B1-08）

```json
{
  "message": "Reply with exactly: OK",
  "session_id": "quant-b1-chat",
  "agent": "general",
  "auto_route": false,
  "enable_tools": false,
  "enable_thinking": false,
  "mode": "chat"
}
```

### LLM 判定表（B1-07 / B1-08）

| 条件 | 判定 |
|------|------|
| `DEEPSEEK_API_KEY` 有效且 200 + schema | PASS（看 T4 延迟） |
| Key 缺失/占位 → 502 或 SSE `error` 且 &lt; 5s | `PASS(expected)` |
| 超时无终态 / 5xx 非预期 / schema 破损 | FAIL |
| 探针检测到 Key 为占位且请求会烧费时主动跳过 | SKIP |

---

## 附录 B · Batch-2 MUT 清单

固定：`quant-b2-sess` · 工作区 `quant_b2_probe.md` · 记忆标题 `quant-b2-thm`。  
**不测**全局 `DELETE /v1/documents?purge=true`（B2-08 = SKIP）。

### Documents（7 测 + 1 SKIP）

| ID | Method | Path / 调用 | Tier | 期望 `S` | `B_schema` / 备注 |
|----|--------|-------------|------|----------|-------------------|
| B2-01 | POST | `/v1/documents` JSON 短正文 | T2 | {200}；RAG 关 {400}`PASS(expected)` | `document`,`status`；记下 `doc_id` |
| B2-02 | POST | `/v1/documents/upload` multipart 极小 `.md` | T2 | 同 B2-01 | Form: `session_id` + `file` |
| B2-03 | POST | `/v1/documents/from-arxiv?session_id=&arxiv_id=1706.03762` | T3 | {200}；网络/解析失败 {400,502,5xx}`PASS(expected)` | N=1；外网 |
| B2-04 | GET | `/v1/documents?session_id=quant-b2-sess` | T1 | {200} | `documents`,`total` |
| B2-05 | GET | `/v1/sessions/quant-b2-sess/rag-refs` | T1 | {200} | `session_id`,`refs` |
| B2-06 | DELETE | `/v1/documents/{doc_id}?session_id=quant-b2-sess` | T2 | {200} | 链式 `doc_id`；每次前保证文档存在 |
| B2-07 | DELETE | `/v1/documents/session/quant-b2-sess` | T2 | {200} | 会话级清空 |
| B2-08 | DELETE | `/v1/documents?purge=true` | — | — | **SKIP**（全局破坏性） |

### Memory L4（7）

| ID | Method | Path | Tier | 期望 `S` | 备注 |
|----|--------|------|------|----------|------|
| B2-09 | GET | `/v1/memory/structured?session_id=quant-b2-sess` | T1 | {200} | `entries`,`total` |
| B2-10 | GET | `/v1/memory/structured/global` | T1 | {200} | |
| B2-11 | GET | `/v1/memory/structured/graph` | T1 | {200} | `nodes`,`edges` |
| B2-12 | POST | `/v1/memory/structured` | T2 | {200} | 记下 `id`；再写一条作 edge 目标 |
| B2-13 | POST | `/v1/memory/structured/{id}/versions` | T2 | {200} | |
| B2-14 | GET | `/v1/memory/structured/{id}/versions` | T1 | {200} | `entry_id`,`versions`,`total` |
| B2-15 | POST | `/v1/memory/structured/{id}/edges` | T2 | {200}；非法边 {400}`PASS(expected)` | `to_id` 指向第二条记忆 |

### Theory / Bibliography（10）

| ID | Method | Path | Tier | 期望 `S` | 备注 |
|----|--------|------|------|----------|------|
| B2-16 | GET | `/v1/theory/workspace` | T1 | {200} | `files` |
| B2-17 | PUT | `/v1/theory/workspace/quant_b2_probe.md` | T2 | {200} | body `content` 含 `QUANT_B2_MARK` |
| B2-18 | GET | `/v1/theory/workspace/quant_b2_probe.md` | T1 | {200} | 正文含标记 |
| B2-19 | GET | `/v1/theory/assumption-matrix` | T1 | {200} 或 {404}`PASS(expected)` | plaintext |
| B2-20 | GET | `/v1/theory/symbols` | T1 | {200} | plaintext |
| B2-21 | GET | `/v1/theory/assumptions` | T1 | {200} | |
| B2-22 | GET | `/v1/theory/assumption-dag` | T1 | {200} | |
| B2-23 | GET | `/v1/theory/assumption-dag/impact/A4` | T1 | {200} | 与 smoke 一致 |
| B2-24 | GET | `/v1/bibliography` | T1 | {200} | |
| B2-25 | GET | `/v1/bibliography/export.bib` | T1 | {200} | plaintext |

测后清理：`unlink` 工作区 `quant_b2_probe.md`（无 DELETE 文件 API）。

运行：

```bash
python scripts/api_quant_probe.py --batch 2 --base-url http://127.0.0.1:8000 --n 3
```

---

## 附录 C · Batch-3 MUT 清单

固定：`quant-b3-proj`（课题名）· `quant-b3-sess` · `quant-b3-verif`。  
课题用新建 `project_id` 链式传递，避免污染 `default`。

### Projects（9）

| ID | Method | Path | Tier | 期望 `S` | 备注 |
|----|--------|------|------|----------|------|
| B3-01 | GET | `/v1/projects` | T1 | {200} | `projects`,`total` |
| B3-02 | POST | `/v1/projects` | T2 | {200} | name=`quant-b3-proj`；记下 `id` |
| B3-03 | GET | `/v1/projects/{project_id}` | T1 | {200} | |
| B3-04 | GET | `/v1/projects/{project_id}/members` | T1 | {200} | 响应为 **list** |
| B3-05 | POST | `/v1/projects/{project_id}/tasks` | T2 | {200} | 记下 `task_id`/`id` |
| B3-06 | GET | `/v1/projects/{project_id}/tasks` | T1 | {200} | `tasks`,`total` |
| B3-07 | PATCH | `/v1/projects/{project_id}/tasks/{task_id}?status=in_progress` | T2 | {200} | |
| B3-08 | POST | `/v1/projects/{project_id}/sessions/quant-b3-sess` | T2 | {200} | `status==ok` |
| B3-09 | GET | `/v1/projects/{project_id}/sessions` | T1 | {200} | FX：含 quant-b3-sess |

### Campaigns（5）

| ID | Method | Path | Tier | 期望 `S` | 备注 |
|----|--------|------|------|----------|------|
| B3-10 | GET | `/v1/projects/{project_id}/campaigns` | T1 | {200} | |
| B3-11 | POST | `/v1/projects/{project_id}/campaign` | T2 | {200} | title 短；记下 `campaign_id` |
| B3-12 | GET | `/v1/projects/{project_id}/campaign` | T1 | {200}；无活跃 {404}`PASS(expected)` | 创建后期望 200 |
| B3-13 | GET | `/v1/projects/{project_id}/campaigns/{campaign_id}` | T1 | {200} | |
| B3-14 | PATCH | `…/campaigns/{campaign_id}` | T2 | {200} | body: `{"status":"active"}` |

### Verification（3）

| ID | Method | Path | Tier | 期望 `S` | 备注 |
|----|--------|------|------|----------|------|
| B3-15 | GET | `/v1/verification/dashboard?project_id=…` | T1 | {200} | |
| B3-16 | GET | `/v1/verification/records` | T1 | {200} | `records`,`total` |
| B3-17 | POST | `/v1/verification/run` | T3 | {200}；{500}`PASS(expected)` | N=1；numerical claim |

### Experiments（3）

| ID | Method | Path | Tier | 期望 `S` | 备注 |
|----|--------|------|------|----------|------|
| B3-18 | POST | `/v1/experiments/runs` | T3 | {200}；{404,500}`PASS(expected)` | N=1；`quadratic_minimum.yaml`；记下 `run_id` |
| B3-19 | GET | `/v1/experiments/runs` | T1 | {200} | `runs`,`total` |
| B3-20 | GET | `/v1/experiments/runs/{run_id}` | T1 | {200}；无 id → SKIP | |

运行：

```bash
python scripts/api_quant_probe.py --batch 3 --base-url http://127.0.0.1:8000 --n 3
```

---

## 附录 D · Batch-4 MUT 清单

固定：`session_id=quant-b4-sess` · `title=Quant Batch-4` · Sync/Observability `project_id=default`。

### Export（6）

| ID | Method | Path | Tier | 期望 `S` | 备注 |
|----|--------|------|------|----------|------|
| B4-01 | GET | `/v1/export/preview?session_id=quant-b4-sess` | T1 | {200} | `entry_count` 等 |
| B4-02 | POST | `/v1/export/md` | T2 | {200} | 非 JSON；Content-Type 含 markdown；body 非空 |
| B4-03 | POST | `/v1/export/latex` | T2 | {200} | `latex`,`path`；len(latex)>0 |
| B4-04 | POST | `/v1/export/docx` | T2 | {200}；{503}`PASS(expected)` | 非 JSON |
| B4-05 | POST | `/v1/export/pdf` | T3 | {200}；{503}`PASS(expected)` | 非 JSON |
| B4-06 | POST | `/v1/export/polish` | T4 | {200}；{400,500,502}`PASS(expected)` | N=1；短 ai_instructions |

共用导出 body：`session_id`、`title`、`include_global`、`include_chat`、`use_ai=false`（polish 另设）。

### Observability（2）

| ID | Method | Path | Tier | 期望 `S` |
|----|--------|------|------|----------|
| B4-07 | GET | `/v1/observability/summary?project_id=default` | T1 | {200} |
| B4-08 | GET | `/v1/observability/agent-quality?project_id=default` | T1 | {200} |

### Sync（2）

| ID | Method | Path | Tier | 期望 `S` | 备注 |
|----|--------|------|------|----------|------|
| B4-09 | POST | `/v1/sync/metadata` | T2 | {403}`PASS(expected)` 或 {200} | 默认云同步关 |
| B4-10 | GET | `/v1/sync/audit/default` | T1 | {200}；{404}`PASS(expected)` | `audit` |

### Jupyter（2）

| ID | Method | Path | Tier | 期望 `S` |
|----|--------|------|------|----------|
| B4-11 | GET | `/v1/jupyter/template?name=loss_landscape` | T1 | {200} 含 `cells` |
| B4-12 | POST | `/v1/jupyter/upload-result` | T2 | {200} `run_id`,`log_path`,`status` |

运行：

```bash
python scripts/api_quant_probe.py --batch 4 --base-url http://127.0.0.1:8000 --n 3
```

四批完成后量化闭环（覆盖 API-COVERAGE 分域排障）；不另开第五批。
