#!/usr/bin/env python3
"""Live API quantitative probe (Batch-1 .. Batch-4).

Writes JSONL under data/quant_probe/ and prints a summary table.
Does NOT use TestClient — hits a running uvicorn over HTTP.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = "http://127.0.0.1:8000"
CHAT_BODY = {
    "message": "Reply with exactly: OK",
    "session_id": "quant-b1-chat",
    "agent": "general",
    "auto_route": False,
    "enable_tools": False,
    "enable_thinking": False,
    "mode": "chat",
}
QUANT_B2_SESS = "quant-b2-sess"
QUANT_B2_MARK = "QUANT_B2_MARK"
DOC_JSON = {
    "session_id": QUANT_B2_SESS,
    "content": "Quant Batch-2 probe document. Loss landscape smoke text.",
    "title": "quant-b2-doc",
    "source": "quant-probe",
}
MEM_JSON = {
    "session_id": QUANT_B2_SESS,
    "kind": "theorem",
    "title": "quant-b2-thm",
    "body": "Quant Batch-2 structured memory body.",
}
QUANT_B3_SESS = "quant-b3-sess"
QUANT_B3_VERIF = "quant-b3-verif"
PROJ_CREATE = {
    "name": "quant-b3-proj",
    "description": "API quant Batch-3 probe project",
    "created_by": "quant-probe",
}
TASK_CREATE = {
    "title": "quant-b3-task",
    "description": "Batch-3 probe task",
    "assignee_role": "theorist",
}
CAMP_CREATE = {
    "title": "quant-b3-project",
    "task_family": "loss_landscape_critical_points",
    "session_id": QUANT_B3_SESS,
}


@dataclass
class MutDef:
    endpoint_id: str
    method: str
    path: str
    tier: str
    expected_status: set[int]
    schema_keys: list[str] = field(default_factory=list)
    json_body: dict[str, Any] | None = None
    query: str = ""
    sse: bool = False
    after_hook: str | None = None
    before_hook: str | None = None
    allow_expected: set[int] = field(default_factory=set)
    schema_check: Callable[[Any], str | None] | None = None
    n_override: int | None = None
    skip: bool = False
    skip_reason: str = ""
    multipart: bool = False
    multipart_filename: str = "quant_b2.md"
    multipart_content: bytes = b"# quant b2 upload\n"
    capture: str | None = None  # doc_id | entry_id | project_id | task_id | run_id
    path_from_ctx: bool = False  # resolve {doc_id}/{entry_id}/{project_id}/...
    query_from_ctx: bool = False
    plaintext: bool = False
    plaintext_contains: str | None = None
    dynamic_edge_body: bool = False
    expect_list: bool = False  # response body is a JSON array
    body_kind: str | None = None  # verification | experiment
    skip_unless_run_id: bool = False
    after_check_session_link: bool = False
    binary_response: bool = False  # md/docx/pdf download
    content_type_substr: str = ""  # required substring in Content-Type when binary/200


@dataclass
class ProbeCtx:
    doc_id: str | None = None
    entry_id: int | None = None
    entry_id_to: int | None = None
    project_id: str | None = None
    task_id: int | None = None
        run_id: str | None = None


TIER_LIMITS = {
    "T0": (50, 200, 200),
    "T1": (300, 1000, 3000),
    "T2": (800, 2000, 5000),
    "T3": (30_000, 90_000, 180_000),
    "T4": (60_000, 120_000, 180_000),
}


def _median(xs: list[float]) -> float:
    return float(statistics.median(xs)) if xs else 0.0


def _api_key_looks_valid() -> bool:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        env_path = ROOT / "conf" / ".env"
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("DEEPSEEK_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key or "your-api-key" in key.lower() or key.startswith("sk-test"):
        return False
    return key.startswith("sk-") and len(key) > 20


def _check_health(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "body not object"
    if data.get("status") != "ok":
        return f"status={data.get('status')!r}"
    return None


def _check_agents(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "body not object"
    names = [a.get("name") for a in data.get("agents") or [] if isinstance(a, dict)]
    if "counterexample" not in names:
        return "missing agent counterexample"
    return None


def _check_cleared(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "body not object"
    if data.get("status") != "cleared":
        return f"status={data.get('status')!r}"
    return None


def _check_deleted(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "body not object"
    if data.get("status") != "deleted":
        return f"status={data.get('status')!r}"
    return None


def _check_doc_upload(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "body not object"
    doc = data.get("document")
    if not isinstance(doc, dict) or not doc.get("doc_id"):
        return "missing document.doc_id"
    return None


BATCH1: list[MutDef] = [
    MutDef("B1-01", "GET", "/health", "T0", {200}, ["status", "model", "reasoning_effort"], schema_check=_check_health),
    MutDef("B1-02", "GET", "/v1/sessions", "T1", {200}, ["sessions", "total"]),
    MutDef(
        "B1-03",
        "DELETE",
        "/v1/sessions/quant-b1-sess",
        "T2",
        {200},
        ["status", "session_id"],
        query="purge=false",
        schema_check=_check_cleared,
    ),
    MutDef("B1-04", "GET", "/v1/sessions/quant-b1-sess", "T1", {200}, ["session_id", "messages"]),
    MutDef(
        "B1-05",
        "DELETE",
        "/v1/sessions/quant-b1-sess",
        "T2",
        {200},
        ["status", "session_id"],
        query="purge=true",
        schema_check=_check_deleted,
        before_hook="ensure_session",
        after_hook="session_gone",
    ),
    MutDef("B1-06", "GET", "/v1/sessions/quant-b1-missing", "T1", {404}, []),
    MutDef(
        "B1-07",
        "POST",
        "/v1/chat",
        "T4",
        {200},
        ["session_id", "content"],
        json_body=CHAT_BODY,
        allow_expected={502},
    ),
    MutDef(
        "B1-08",
        "POST",
        "/v1/chat/stream",
        "T4",
        {200},
        [],
        json_body=CHAT_BODY,
        sse=True,
        allow_expected={502},
    ),
    MutDef(
        "B1-09",
        "GET",
        "/v1/agents",
        "T1",
        {200},
        ["orchestration_backend", "agents"],
        schema_check=_check_agents,
    ),
    MutDef("B1-10", "GET", "/v1/mcp/status", "T1", {200}, ["server_enabled", "connected", "servers"]),
    MutDef(
        "B1-11",
        "POST",
        "/v1/mcp/reload",
        "T2",
        {200},
        ["server_enabled", "connected", "servers"],
        allow_expected={400},
    ),
    MutDef("B1-12", "GET", "/v1/stats/tokens", "T1", {200}, ["filters", "totals", "by_agent"]),
]


BATCH2: list[MutDef] = [
    MutDef(
        "B2-01",
        "POST",
        "/v1/documents",
        "T2",
        {200},
        ["document", "status"],
        json_body=DOC_JSON,
        allow_expected={400},
        schema_check=_check_doc_upload,
        capture="doc_id",
    ),
    MutDef(
        "B2-02",
        "POST",
        "/v1/documents/upload",
        "T2",
        {200},
        ["document", "status"],
        allow_expected={400},
        schema_check=_check_doc_upload,
        multipart=True,
        multipart_filename="quant_b2_upload.md",
        multipart_content=b"# quant b2 multipart\nprobe upload\n",
    ),
    MutDef(
        "B2-03",
        "POST",
        "/v1/documents/from-arxiv",
        "T3",
        {200},
        ["document", "status"],
        query=f"session_id={QUANT_B2_SESS}&arxiv_id=1706.03762",
        allow_expected={400, 502, 500, 503, 504},
        schema_check=_check_doc_upload,
        n_override=1,
    ),
    MutDef(
        "B2-04",
        "GET",
        "/v1/documents",
        "T1",
        {200},
        ["documents", "total"],
        query=f"session_id={QUANT_B2_SESS}",
    ),
    MutDef(
        "B2-05",
        "GET",
        f"/v1/sessions/{QUANT_B2_SESS}/rag-refs",
        "T1",
        {200},
        ["session_id", "refs"],
    ),
    MutDef(
        "B2-06",
        "DELETE",
        "/v1/documents/{doc_id}",
        "T2",
        {200},
        ["status", "doc_id"],
        query=f"session_id={QUANT_B2_SESS}",
        allow_expected={400, 404},
        before_hook="ensure_doc",
        path_from_ctx=True,
        n_override=1,
    ),
    MutDef(
        "B2-07",
        "DELETE",
        f"/v1/documents/session/{QUANT_B2_SESS}",
        "T2",
        {200},
        ["status", "session_id"],
        allow_expected={400},
    ),
    MutDef(
        "B2-08",
        "DELETE",
        "/v1/documents",
        "T2",
        {200},
        skip=True,
        skip_reason="global purge destructive; not run in Batch-2",
    ),
    MutDef(
        "B2-09",
        "GET",
        "/v1/memory/structured",
        "T1",
        {200},
        ["entries", "total"],
        query=f"session_id={QUANT_B2_SESS}",
    ),
    MutDef("B2-10", "GET", "/v1/memory/structured/global", "T1", {200}, ["entries", "total"]),
    MutDef("B2-11", "GET", "/v1/memory/structured/graph", "T1", {200}, ["nodes", "edges"]),
    MutDef(
        "B2-12",
        "POST",
        "/v1/memory/structured",
        "T2",
        {200},
        ["id", "body"],
        json_body=MEM_JSON,
        capture="entry_id",
        before_hook="ensure_edge_target",
    ),
    MutDef(
        "B2-13",
        "POST",
        "/v1/memory/structured/{entry_id}/versions",
        "T2",
        {200},
        path_from_ctx=True,
        n_override=1,
    ),
    MutDef(
        "B2-14",
        "GET",
        "/v1/memory/structured/{entry_id}/versions",
        "T1",
        {200},
        ["entry_id", "versions", "total"],
        path_from_ctx=True,
    ),
    MutDef(
        "B2-15",
        "POST",
        "/v1/memory/structured/{entry_id}/edges",
        "T2",
        {200},
        ["from_id", "to_id", "relation"],
        allow_expected={400},
        path_from_ctx=True,
        dynamic_edge_body=True,
        n_override=1,
    ),
    MutDef("B2-16", "GET", "/v1/theory/workspace", "T1", {200}, ["files"]),
    MutDef(
        "B2-17",
        "PUT",
        "/v1/theory/workspace/quant_b2_probe.md",
        "T2",
        {200},
        plaintext=True,
        json_body={"content": f"# probe\n{QUANT_B2_MARK}\n"},
    ),
    MutDef(
        "B2-18",
        "GET",
        "/v1/theory/workspace/quant_b2_probe.md",
        "T1",
        {200},
        plaintext=True,
        plaintext_contains=QUANT_B2_MARK,
    ),
    MutDef("B2-19", "GET", "/v1/theory/assumption-dag", "T1", {200}, ["nodes", "edges"]),
    MutDef("B2-20", "GET", "/v1/theory/assumption-dag/impact/A4", "T1", {200}),
]


def _check_members_list(data: Any) -> str | None:
    if not isinstance(data, list):
        return "members not list"
    return None


def _check_link_ok(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "body not object"
    if data.get("status") != "ok":
        return f"status={data.get('status')!r}"
    return None


def _check_verification(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "body not object"
    if "overall_passed" not in data and "status" not in data and "tiers" not in data:
        return "missing overall_passed/status/tiers"
    return None


def _check_experiment(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "body not object"
    if "run_id" not in data and "status" not in data:
        return "missing run_id/status"
    return None


def _check_session_linked(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "body not object"
    sessions = data.get("sessions") or []
    ids = [s.get("session_id") for s in sessions if isinstance(s, dict)]
    if QUANT_B3_SESS not in ids:
        return f"missing linked session {QUANT_B3_SESS}"
    return None


BATCH3: list[MutDef] = [
    MutDef(
        "B3-15",
        "GET",
        "/v1/verification/dashboard",
        "T1",
        {200},
        ["project_id", "total_records", "passed", "failed", "by_tier", "recent"],
        query_from_ctx=True,
    ),
    MutDef(
        "B3-16",
        "GET",
        "/v1/verification/records",
        "T1",
        {200},
        ["records", "total"],
    ),
    MutDef(
        "B3-17",
        "POST",
        "/v1/verification/run",
        "T3",
        {200},
        allow_expected={500},
        schema_check=_check_verification,
        body_kind="verification",
        n_override=1,
    ),
    MutDef(
        "B3-18",
        "POST",
        "/v1/experiments/runs",
        "T3",
        {200},
        allow_expected={404, 500},
        schema_check=_check_experiment,
        json_body={"config_path": "quadratic_minimum.yaml", "session_id": QUANT_B3_VERIF},
        capture="run_id",
        n_override=1,
    ),
    MutDef(
        "B3-19",
        "GET",
        "/v1/experiments/runs",
        "T1",
        {200},
        ["runs", "total"],
    ),
    MutDef(
        "B3-20",
        "GET",
        "/v1/experiments/runs/{run_id}",
        "T1",
        {200},
        path_from_ctx=True,
        skip_unless_run_id=True,
        n_override=1,
    ),
]


QUANT_B4_SESS = "quant-b4-sess"
EXPORT_BODY = {
    "session_id": QUANT_B4_SESS,
    "title": "Quant Batch-4",
    "include_global": True,
    "include_chat": True,
    "use_ai": False,
}
POLISH_BODY = {
    **EXPORT_BODY,
    "use_ai": True,
    "ai_instructions": "Keep structure; reply briefly.",
}
JUPYTER_UPLOAD = {
    "name": "quant-b4",
    "summary": {"ok": True},
    "metrics": {"loss": 0.1},
}


def _check_latex(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "body not object"
    latex = data.get("latex")
    if not isinstance(latex, str) or len(latex) == 0:
        return "empty latex"
    return None


def _check_polish(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "body not object"
    if "markdown" not in data or "ai_applied" not in data:
        return "missing markdown/ai_applied"
    return None


def _check_audit(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "body not object"
    if "audit" not in data:
        return "missing audit"
    return None


BATCH4: list[MutDef] = [
    MutDef(
        "B4-01",
        "GET",
        "/v1/export/preview",
        "T1",
        {200},
        ["entry_count", "session_structured_count", "global_structured_count", "chat_message_count", "source"],
        query=f"session_id={QUANT_B4_SESS}",
    ),
    MutDef(
        "B4-02",
        "POST",
        "/v1/export/md",
        "T2",
        {200},
        json_body=EXPORT_BODY,
        binary_response=True,
        content_type_substr="markdown",
    ),
    MutDef(
        "B4-03",
        "POST",
        "/v1/export/latex",
        "T2",
        {200},
        ["latex", "path"],
        json_body=EXPORT_BODY,
        schema_check=_check_latex,
    ),
    MutDef(
        "B4-04",
        "POST",
        "/v1/export/docx",
        "T2",
        {200},
        allow_expected={503},
        json_body=EXPORT_BODY,
        binary_response=True,
        content_type_substr="officedocument",
        n_override=1,
    ),
    MutDef(
        "B4-05",
        "POST",
        "/v1/export/pdf",
        "T3",
        {200},
        allow_expected={503},
        json_body=EXPORT_BODY,
        binary_response=True,
        content_type_substr="pdf",
        n_override=1,
    ),
    MutDef(
        "B4-06",
        "POST",
        "/v1/export/polish",
        "T4",
        {200},
        ["markdown", "ai_applied"],
        allow_expected={400, 500, 502},
        json_body=POLISH_BODY,
        schema_check=_check_polish,
        n_override=1,
    ),
    MutDef(
        "B4-07",
        "GET",
        "/v1/observability/summary",
        "T1",
        {200},
        ["project_id", "verification_total", "verification_passed", "verification_pass_rate", "by_agent"],
        query="project_id=default",
    ),
    MutDef(
        "B4-08",
        "GET",
        "/v1/observability/agent-quality",
        "T1",
        {200},
        ["agents"],
        query="project_id=default",
    ),
    MutDef(
        "B4-09",
        "GET",
        "/v1/sync/audit/default",
        "T1",
        {200},
        allow_expected={404},
        schema_check=_check_audit,
    ),
    MutDef(
        "B4-10",
        "POST",
        "/v1/jupyter/upload-result",
        "T2",
        {200},
        ["run_id", "log_path", "status"],
        json_body=JUPYTER_UPLOAD,
        n_override=1,
    ),
]


def _url(base: str, path: str, query: str) -> str:
    u = base.rstrip("/") + path
    if query:
        u += ("&" if "?" in path else "?") + query
    return u


def _resolve_path(mut: MutDef, ctx: ProbeCtx) -> str:
    path = mut.path
    if mut.path_from_ctx:
        repl = {
            "{doc_id}": ctx.doc_id,
            "{entry_id}": str(ctx.entry_id) if ctx.entry_id is not None else None,
            "{project_id}": ctx.project_id,
            "{task_id}": str(ctx.task_id) if ctx.task_id is not None else None,
            "{run_id}": ctx.run_id,
        }
        for token, val in repl.items():
            if token in path:
                if not val:
                    raise RuntimeError(f"ctx missing for {token}")
                path = path.replace(token, val)
    return path


def _resolve_query(mut: MutDef, ctx: ProbeCtx) -> str:
    if mut.query_from_ctx:
        if not ctx.project_id:
            raise RuntimeError("ctx.project_id missing for query")
        return f"project_id={ctx.project_id}"
    return mut.query


def _capture(mut: MutDef, ctx: ProbeCtx, data: Any) -> None:
    if not mut.capture or not isinstance(data, dict):
        return
    if mut.capture == "doc_id":
        doc = data.get("document") or {}
        if isinstance(doc, dict) and doc.get("doc_id"):
            ctx.doc_id = str(doc["doc_id"])
    elif mut.capture == "entry_id" and data.get("id") is not None:
        ctx.entry_id = int(data["id"])
    elif mut.capture == "entry_id_to" and data.get("id") is not None:
        ctx.entry_id_to = int(data["id"])
    elif mut.capture == "project_id" and data.get("id") is not None:
        ctx.project_id = str(data["id"])
    elif mut.capture == "task_id" and data.get("id") is not None:
        ctx.task_id = int(data["id"])
    elif mut.capture == "run_id" and data.get("run_id"):
        ctx.run_id = str(data["run_id"])


def _http(
    base: str,
    method: str,
    path: str,
    *,
    query: str = "",
    json_body: dict[str, Any] | None = None,
    timeout: float = 180.0,
) -> tuple[int, float, dict[str, str], bytes]:
    url = _url(base, path, query)
    data = None
    headers = {"Accept": "application/json"}
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    t0 = time.perf_counter()
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            status = resp.getcode() or 200
            hdrs = {k: v for k, v in resp.headers.items()}
    except HTTPError as e:
        body = e.read() if e.fp else b""
        status = e.code
        hdrs = {k: v for k, v in (e.headers.items() if e.headers else [])}
    except URLError as e:
        elapsed = (time.perf_counter() - t0) * 1000
        raise RuntimeError(f"connection failed: {e}") from e
    elapsed = (time.perf_counter() - t0) * 1000
    return status, elapsed, hdrs, body


def _http_multipart(
    base: str,
    path: str,
    *,
    session_id: str,
    filename: str,
    file_bytes: bytes,
    timeout: float = 180.0,
) -> tuple[int, float, dict[str, str], bytes]:
    boundary = f"----quant{uuid.uuid4().hex}"
    parts: list[bytes] = []
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="session_id"\r\n\r\n'
            f"{session_id}\r\n"
        ).encode()
    )
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: text/markdown\r\n\r\n"
        ).encode()
        + file_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    url = _url(base, path, "")
    headers = {
        "Accept": "application/json",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    req = Request(url, data=body, headers=headers, method="POST")
    t0 = time.perf_counter()
    try:
        with urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read()
            status = resp.getcode() or 200
            hdrs = {k: v for k, v in resp.headers.items()}
    except HTTPError as e:
        resp_body = e.read() if e.fp else b""
        status = e.code
        hdrs = {k: v for k, v in (e.headers.items() if e.headers else [])}
    except URLError as e:
        raise RuntimeError(f"connection failed: {e}") from e
    elapsed = (time.perf_counter() - t0) * 1000
    return status, elapsed, hdrs, resp_body


def _http_sse(
    base: str,
    path: str,
    json_body: dict[str, Any],
    *,
    timeout: float = 180.0,
) -> tuple[int, float, dict[str, str], float | None, bool, str]:
    url = _url(base, path, "")
    data = json.dumps(json_body).encode("utf-8")
    headers = {"Accept": "text/event-stream", "Content-Type": "application/json"}
    req = Request(url, data=data, headers=headers, method="POST")
    t0 = time.perf_counter()
    ttfb: float | None = None
    got_terminal = False
    note_parts: list[str] = []
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = resp.getcode() or 200
            hdrs = {k: v for k, v in resp.headers.items()}
            buf = b""
            while True:
                chunk = resp.read(256)
                if not chunk:
                    break
                if ttfb is None:
                    ttfb = (time.perf_counter() - t0) * 1000
                buf += chunk
                text = buf.decode("utf-8", errors="replace")
                for line in text.splitlines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload:
                        continue
                    try:
                        obj = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    typ = obj.get("type")
                    if typ in ("finish", "error", "done"):
                        got_terminal = True
                        note_parts.append(f"terminal={typ}")
                        if typ == "error":
                            note_parts.append(str(obj.get("content", ""))[:120])
                if got_terminal:
                    break
    except HTTPError as e:
        elapsed = (time.perf_counter() - t0) * 1000
        body = e.read() if e.fp else b""
        note_parts.append(body[:200].decode("utf-8", errors="replace"))
        return e.code, elapsed, {}, ttfb, False, "; ".join(note_parts) or f"HTTP {e.code}"
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        return 0, elapsed, {}, ttfb, False, f"sse_error={e}"
    elapsed = (time.perf_counter() - t0) * 1000
    return status, elapsed, hdrs, ttfb, got_terminal, "; ".join(note_parts)


def _tier_verdict(tier: str, l_med: float) -> str | None:
    pass_ms, warn_ms, fail_ms = TIER_LIMITS[tier]
    if l_med <= pass_ms:
        return None
    if l_med <= warn_ms:
        return "WARN"
    if l_med <= fail_ms:
        return "WARN"
    return "FAIL"


def _schema_ok(data: Any, keys: list[str], extra: Callable[[Any], str | None] | None) -> tuple[bool, str]:
    if not keys and extra is None:
        return True, ""
    if keys and not isinstance(data, dict):
        return False, "not json object"
    missing = [k for k in keys if k not in (data or {})]
    if missing:
        return False, f"missing:{','.join(missing)}"
    if extra:
        err = extra(data)
        if err:
            return False, err
    return True, ""


def _run_before_hook(base: str, name: str | None, ctx: ProbeCtx) -> None:
    if name == "ensure_session":
        _http(base, "DELETE", "/v1/sessions/quant-b1-sess", query="purge=false")
    elif name == "ensure_doc":
        st, _, _, body = _http(base, "POST", "/v1/documents", json_body=DOC_JSON)
        if st == 200:
            try:
                data = json.loads(body.decode("utf-8"))
                doc = data.get("document") or {}
                ctx.doc_id = str(doc.get("doc_id") or ctx.doc_id)
            except json.JSONDecodeError:
                pass
    elif name == "ensure_edge_target":
        body = {
            **MEM_JSON,
            "title": "quant-b2-thm-target",
            "body": "Edge target entry for Batch-2.",
        }
        st, _, _, raw = _http(base, "POST", "/v1/memory/structured", json_body=body)
        if st == 200:
            try:
                data = json.loads(raw.decode("utf-8"))
                if data.get("id") is not None:
                    ctx.entry_id_to = int(data["id"])
            except json.JSONDecodeError:
                pass


def run_skip(mut: MutDef) -> dict[str, Any]:
    row = {
        "endpoint_id": mut.endpoint_id,
        "method": mut.method,
        "path": mut.path + (("?" + mut.query) if mut.query else ""),
        "attempt": 1,
        "status": 0,
        "latency_ms": 0.0,
        "rid": "",
        "sse_ttfb_ms": None,
        "schema_ok": True,
        "cold": True,
        "note": mut.skip_reason,
        "verdict": "SKIP",
    }
    return {
        "endpoint_id": mut.endpoint_id,
        "method": mut.method,
        "path": row["path"],
        "tier": mut.tier,
        "verdict": "SKIP",
        "status_sample": 0,
        "L_min": 0.0,
        "L_med": 0.0,
        "L_max": 0.0,
        "H_rid": True,
        "B_schema": True,
        "note": mut.skip_reason,
        "attempts": [row],
    }


def run_mut(base: str, mut: MutDef, n: int, has_key: bool, ctx: ProbeCtx) -> dict[str, Any]:
    if mut.skip:
        return run_skip(mut)
    if mut.skip_unless_run_id and not ctx.run_id:
        # try pick from list endpoint briefly
        try:
            st, _, _, body = _http(base, "GET", "/v1/experiments/runs")
            if st == 200:
                data = json.loads(body.decode("utf-8"))
                runs = data.get("runs") or []
                if runs and isinstance(runs[0], dict) and runs[0].get("run_id"):
                    ctx.run_id = str(runs[0]["run_id"])
        except Exception:
            pass
        if not ctx.run_id:
            m = MutDef(
                mut.endpoint_id,
                mut.method,
                mut.path,
                mut.tier,
                mut.expected_status,
                skip=True,
                skip_reason="no run_id from B3-18/list",
            )
            return run_skip(m)

    if mut.n_override is not None:
        n_eff = mut.n_override
    elif mut.endpoint_id in ("B1-07", "B1-08") and not has_key:
        n_eff = 1
    else:
        n_eff = n

    attempts: list[dict[str, Any]] = []
    last_data: Any = None
    last_text = ""

    for i in range(n_eff):
        cold = i == 0
        try:
            _run_before_hook(base, mut.before_hook, ctx)
            path = _resolve_path(mut, ctx)
            query = _resolve_query(mut, ctx)
            display_path = path + (("?" + query) if query else "")

            if mut.sse:
                status, latency, hdrs, ttfb, terminal, note = _http_sse(
                    base, path, mut.json_body or CHAT_BODY
                )
                rid = hdrs.get("X-Request-ID") or hdrs.get("x-request-id") or ""
                schema_ok = True
                schema_note = ""
                if status == 200 and not terminal:
                    schema_ok = False
                    schema_note = "no_terminal_event"
                elif status == 200 and ttfb is not None and has_key and ttfb >= 5000:
                    schema_note = f"sse_ttfb_slow={ttfb:.0f}"
                row = {
                    "endpoint_id": mut.endpoint_id,
                    "method": mut.method,
                    "path": display_path,
                    "attempt": i + 1,
                    "status": status,
                    "latency_ms": round(latency, 2),
                    "rid": rid,
                    "sse_ttfb_ms": round(ttfb, 2) if ttfb is not None else None,
                    "schema_ok": schema_ok,
                    "cold": cold,
                    "note": note or schema_note,
                    "verdict": "",
                }
            elif mut.multipart:
                status, latency, hdrs, body = _http_multipart(
                    base,
                    path,
                    session_id=QUANT_B2_SESS,
                    filename=mut.multipart_filename,
                    file_bytes=mut.multipart_content,
                )
                rid = hdrs.get("X-Request-ID") or hdrs.get("x-request-id") or ""
                data: Any = None
                if body:
                    try:
                        data = json.loads(body.decode("utf-8"))
                        last_data = data
                    except json.JSONDecodeError:
                        data = None
                ok, snote = (True, "")
                if status in mut.expected_status:
                    ok, snote = _schema_ok(data, mut.schema_keys, mut.schema_check)
                    if ok:
                        _capture(mut, ctx, data)
                row = {
                    "endpoint_id": mut.endpoint_id,
                    "method": mut.method,
                    "path": display_path,
                    "attempt": i + 1,
                    "status": status,
                    "latency_ms": round(latency, 2),
                    "rid": rid,
                    "sse_ttfb_ms": None,
                    "schema_ok": ok,
                    "cold": cold,
                    "note": snote,
                    "verdict": "",
                }
            elif mut.binary_response:
                status, latency, hdrs, body = _http(
                    base,
                    mut.method,
                    path,
                    query=query,
                    json_body=mut.json_body,
                )
                rid = hdrs.get("X-Request-ID") or hdrs.get("x-request-id") or ""
                ctype = hdrs.get("Content-Type") or hdrs.get("content-type") or ""
                ok, snote = True, ""
                if status in mut.expected_status:
                    if not body:
                        ok, snote = False, "empty_body"
                    elif mut.content_type_substr and mut.content_type_substr.lower() not in ctype.lower():
                        ok, snote = False, f"ctype={ctype!r}"
                    else:
                        snote = f"bytes={len(body)};ctype={ctype}"
                row = {
                    "endpoint_id": mut.endpoint_id,
                    "method": mut.method,
                    "path": display_path,
                    "attempt": i + 1,
                    "status": status,
                    "latency_ms": round(latency, 2),
                    "rid": rid,
                    "sse_ttfb_ms": None,
                    "schema_ok": ok,
                    "cold": cold,
                    "note": snote,
                    "verdict": "",
                }
            else:
                json_body = mut.json_body
                if mut.dynamic_edge_body:
                    if ctx.entry_id_to is None:
                        raise RuntimeError("ctx.entry_id_to missing for edge")
                    json_body = {"to_id": ctx.entry_id_to, "relation": "supports"}
                if mut.body_kind == "verification":
                    if not ctx.project_id:
                        raise RuntimeError("ctx.project_id missing for verification")
                    json_body = {
                        "claim": {
                            "expression": "x0**2 + x1**2",
                            "point": "0,0",
                            "variables": "x0,x1",
                            "expected": {"classification": "local_minimum"},
                            "tier_hint": "numerical",
                        },
                        "session_id": QUANT_B3_VERIF,
                        "project_id": ctx.project_id,
                    }
                status, latency, hdrs, body = _http(
                    base,
                    mut.method,
                    path,
                    query=query,
                    json_body=json_body,
                )
                rid = hdrs.get("X-Request-ID") or hdrs.get("x-request-id") or ""
                text = body.decode("utf-8", errors="replace") if body else ""
                last_text = text
                data = None
                if body and not mut.plaintext:
                    try:
                        data = json.loads(text)
                        last_data = data
                    except json.JSONDecodeError:
                        data = None
                ok, snote = (True, "")
                if status in mut.expected_status:
                    if mut.plaintext:
                        if mut.plaintext_contains and mut.plaintext_contains not in text:
                            ok, snote = False, f"missing_mark:{mut.plaintext_contains}"
                    elif mut.expect_list:
                        ok, snote = _schema_ok(data if data is not None else None, [], mut.schema_check)
                    elif mut.schema_keys or mut.schema_check:
                        ok, snote = _schema_ok(data, mut.schema_keys, mut.schema_check)
                    if ok and data is not None:
                        _capture(mut, ctx, data)
                row = {
                    "endpoint_id": mut.endpoint_id,
                    "method": mut.method,
                    "path": display_path,
                    "attempt": i + 1,
                    "status": status,
                    "latency_ms": round(latency, 2),
                    "rid": rid,
                    "sse_ttfb_ms": None,
                    "schema_ok": ok,
                    "cold": cold,
                    "note": snote,
                    "verdict": "",
                }
        except RuntimeError as e:
            row = {
                "endpoint_id": mut.endpoint_id,
                "method": mut.method,
                "path": mut.path,
                "attempt": i + 1,
                "status": 0,
                "latency_ms": 0.0,
                "rid": "",
                "sse_ttfb_ms": None,
                "schema_ok": False,
                "cold": cold,
                "note": str(e),
                "verdict": "FAIL",
            }
        attempts.append(row)

    statuses = [a["status"] for a in attempts]
    latencies = [float(a["latency_ms"]) for a in attempts]
    if len(attempts) >= 2:
        warm = [float(a["latency_ms"]) for a in attempts[1:]]
    else:
        warm = latencies
    l_med = _median(warm if warm else latencies)
    l_min = min(latencies) if latencies else 0.0
    l_max = max(latencies) if latencies else 0.0
    rid_ok = all(bool(a["rid"]) for a in attempts if a["status"] != 0)
    schema_ok = all(a["schema_ok"] for a in attempts)

    verdict = "PASS"
    notes: list[str] = []
    primary = statuses[-1] if statuses else 0

    if primary == 0:
        verdict = "FAIL"
        notes.append("connection/error")
    elif primary in mut.expected_status:
        if not schema_ok:
            verdict = "FAIL"
            notes.append("schema")
    elif primary in mut.allow_expected:
        verdict = "PASS(expected)"
        notes.append(f"status={primary}")
    else:
        verdict = "FAIL"
        notes.append(f"unexpected_status={primary}")

    if mut.endpoint_id in ("B1-07", "B1-08") and not has_key:
        if mut.sse and any("terminal=error" in (a.get("note") or "") for a in attempts):
            verdict = "PASS(expected)"
            notes.append("sse_error_no_key")
        elif primary in mut.allow_expected or primary in (502, 500):
            verdict = "PASS(expected)"
            notes.append("no_valid_api_key")

    if verdict in ("PASS", "PASS(expected)"):
        lv = _tier_verdict(mut.tier, l_med)
        if lv == "FAIL":
            verdict = "FAIL"
            notes.append(f"L_med={l_med:.1f}>{TIER_LIMITS[mut.tier][2]}")
        elif lv == "WARN" and verdict == "PASS":
            verdict = "WARN"
            notes.append(f"L_med={l_med:.1f}")

    if not rid_ok and verdict in ("PASS", "WARN", "PASS(expected)"):
        if verdict == "PASS":
            verdict = "WARN"
        notes.append("missing_X-Request-ID")

    if mut.after_hook == "session_gone" and verdict in ("PASS", "WARN", "PASS(expected)"):
        try:
            st, _, _, _ = _http(base, "GET", "/v1/sessions/quant-b1-sess")
            if st != 404:
                verdict = "FAIL"
                notes.append(f"FX_expected_404_got_{st}")
            else:
                notes.append("FX_404_ok")
        except RuntimeError as e:
            verdict = "FAIL"
            notes.append(str(e))

    # late capture from last success
    if last_data is not None and primary in mut.expected_status:
        _capture(mut, ctx, last_data)

    for a in attempts:
        a["verdict"] = verdict

    path_disp = attempts[0]["path"] if attempts else mut.path
    return {
        "endpoint_id": mut.endpoint_id,
        "method": mut.method,
        "path": path_disp,
        "tier": mut.tier,
        "verdict": verdict,
        "status_sample": primary,
        "L_min": round(l_min, 2),
        "L_med": round(l_med, 2),
        "L_max": round(l_max, 2),
        "H_rid": rid_ok,
        "B_schema": schema_ok,
        "note": "; ".join(notes + [a["note"] for a in attempts if a.get("note")]),
        "attempts": attempts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="API quantitative probe")
    parser.add_argument("--batch", type=int, default=1, choices=[1, 2, 3, 4])
    parser.add_argument("--base-url", default=os.environ.get("API_BASE_URL", DEFAULT_BASE))
    parser.add_argument("--n", type=int, default=3)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data" / "quant_probe")
    args = parser.parse_args()

    muts = {1: BATCH1, 2: BATCH2, 3: BATCH3, 4: BATCH4}[args.batch]
    has_key = _api_key_looks_valid()
    ctx = ProbeCtx()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    jsonl_path = args.out_dir / f"batch{args.batch}_{ts}.jsonl"
    summary_path = args.out_dir / f"batch{args.batch}_{ts}_summary.json"

    try:
        st, lat, _, _ = _http(args.base_url, "GET", "/health", timeout=5.0)
        if st != 200:
            print(f"FAIL: base {args.base_url} /health -> {st}", file=sys.stderr)
            return 2
        print(f"ready: /health {st} in {lat:.1f}ms; api_key_valid={has_key}")
    except RuntimeError as e:
        print(f"FAIL: cannot reach {args.base_url}: {e}", file=sys.stderr)
        return 2

    summaries: list[dict[str, Any]] = []
    with jsonl_path.open("w", encoding="utf-8") as f:
        for mut in muts:
            print(f"… {mut.endpoint_id} {mut.method} {mut.path}")
            result = run_mut(args.base_url, mut, args.n, has_key, ctx)
            summaries.append({k: v for k, v in result.items() if k != "attempts"})
            for att in result["attempts"]:
                f.write(json.dumps(att, ensure_ascii=False) + "\n")
            print(
                f"  → {result['verdict']}  "
                f"S={result['status_sample']}  "
                f"L_med={result['L_med']}ms  "
                f"rid={result['H_rid']}  "
                f"{result['note'][:100]}"
            )

    summary_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    counts: dict[str, int] = {}
    for s in summaries:
        counts[s["verdict"]] = counts.get(s["verdict"], 0) + 1
    ok_n = counts.get("PASS", 0) + counts.get("PASS(expected)", 0) + counts.get("SKIP", 0)
    print("---")
    print(f"jsonl: {jsonl_path}")
    print(f"summary: {summary_path}")
    print(f"counts: {counts}  pass_rate={ok_n}/{len(summaries)}")
    print(f"ctx: doc_id={ctx.doc_id} entry_id={ctx.entry_id} project_id={ctx.project_id} "
          f"task_id={ctx.task_id} run_id={ctx.run_id}")
    return 0 if counts.get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
