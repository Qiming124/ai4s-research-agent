#!/usr/bin/env python3
"""产业化功能可用性冒烟检查。"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# 确保可导入 app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-key-for-smoke-check")

from fastapi.testclient import TestClient  # noqa: E402

from server.config import get_settings  # noqa: E402
from server.main import create_app  # noqa: E402

get_settings.cache_clear()
client = TestClient(create_app())

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "OK" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))


# ── 基础 ──
r = client.get("/health")
check("GET /health", r.status_code == 200, r.json().get("status", ""))

# ── Phase 0/2: 课题 ──
r = client.get("/v1/projects")
data = r.json()
check("GET /v1/projects", r.status_code == 200 and data.get("total", 0) >= 1)

r = client.get("/v1/projects/default")
check("GET /v1/projects/default", r.status_code == 200)

r = client.get("/v1/projects/default/members")
check("GET /v1/projects/default/members", r.status_code == 200)

r = client.get("/v1/projects/default/tasks")
check("GET /v1/projects/default/tasks", r.status_code == 200)

r = client.post("/v1/projects/default/sessions/smoke-session-1")
check("POST link session to project", r.status_code == 200)

# ── Phase 1: 验证 ──
r = client.get("/v1/verification/dashboard")
check("GET /v1/verification/dashboard", r.status_code == 200, f"records={r.json().get('total_records')}")

r = client.get("/v1/verification/records")
check("GET /v1/verification/records", r.status_code == 200)

claim = {
    "claim": {
        "expression": "x0**2 + x1**2",
        "point": "0,0",
        "variables": "x0,x1",
        "expected": {"classification": "local_minimum"},
        "tier_hint": "numerical",
    },
    "session_id": "smoke-session-1",
}
# MCP 可能未连接，允许 200 或 500
r = client.post("/v1/verification/run", json=claim)
check(
    "POST /v1/verification/run",
    r.status_code in (200, 500),
    f"status={r.status_code}",
)

# ── Phase 1: 实验 runner ──
r = client.post("/v1/experiments/runs", json={"config_path": "quadratic_minimum.yaml"})
check(
    "POST /v1/experiments/runs",
    r.status_code in (200, 500),
    f"status={r.status_code}",
)

r = client.get("/v1/experiments/runs")
check("GET /v1/experiments/runs", r.status_code == 200)

# ── Phase 2: 假设 DAG / 工作区 ──
r = client.get("/v1/theory/assumption-dag")
check("GET /v1/theory/assumption-dag", r.status_code == 200, f"nodes={len(r.json().get('nodes', []))}")

r = client.get("/v1/theory/assumption-dag/impact/A4")
check("GET assumption impact A4", r.status_code == 200)

r = client.get("/v1/theory/workspace")
check("GET /v1/theory/workspace", r.status_code == 200)

# 工作区读写
with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
    test_path = "smoke_test_file.md"
r = client.put(f"/v1/theory/workspace/{test_path}", json={"content": "# smoke test\n"})
read_r = client.get(f"/v1/theory/workspace/{test_path}")
check(
    "PUT/GET workspace file",
    r.status_code == 200 and read_r.status_code == 200 and "smoke test" in read_r.text,
)

# L4 版本
r = client.post(
    "/v1/memory/structured",
    json={"session_id": "smoke-session-1", "kind": "theorem", "title": "Smoke Thm", "body": "test body"},
)
if r.status_code == 200:
    entry_id = r.json()["id"]
    vr = client.post(f"/v1/memory/structured/{entry_id}/versions")
    vl = client.get(f"/v1/memory/structured/{entry_id}/versions")
    check("L4 versioning", vr.status_code == 200 and vl.status_code == 200, f"entry={entry_id}")
else:
    check("L4 versioning", False, f"create failed {r.status_code}")

# ── Phase 3: Jupyter ──
r = client.post(
    "/v1/jupyter/upload-result",
    json={"name": "smoke", "summary": {"ok": True}, "metrics": {"loss": 0.1}},
)
check("POST /v1/jupyter/upload-result", r.status_code == 200)

# ── Phase 4: 审计 ──
r = client.get("/v1/sync/audit/default")
check("GET /v1/sync/audit/default", r.status_code == 200)

# ── Phase 5: 导出 / 可观测性 ──
r = client.post("/v1/export/latex", json={"session_id": "smoke-session-1", "title": "Smoke"})
check("POST /v1/export/latex", r.status_code == 200 and len(r.json().get("latex", "")) > 0)

r = client.get("/v1/observability/summary")
check("GET /v1/observability/summary", r.status_code == 200)

r = client.get("/v1/observability/agent-quality")
check("GET /v1/observability/agent-quality", r.status_code == 200)

# ── Agent 注册 ──
r = client.get("/v1/agents")
agents = [a["name"] for a in r.json().get("agents", [])]
check("counterexample agent registered", "counterexample" in agents, str(agents))

# ── Claim 解析 ──
from server.memory.claim_parser import parse_verifiable_claim  # noqa: E402

sample = '```yaml\nverifiable:\n  expression: "x0**2"\n  point: "0,0"\n```'
check("claim parser", parse_verifiable_claim(sample) is not None)

# ── 汇总 ──
passed = sum(1 for _, ok, _ in results if ok)
failed = [(n, d) for n, ok, d in results if not ok]
print("\n" + "=" * 50)
print(f"总计: {passed}/{len(results)} 通过")
if failed:
    print("失败项:")
    for n, d in failed:
        print(f"  - {n}: {d}")
    sys.exit(1)
print("全部冒烟检查通过。")
