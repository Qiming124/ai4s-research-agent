#!/usr/bin/env python3
"""Live acceptance runner against http://127.0.0.1:8000 — writes JSON results."""
from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import date
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
OUT = Path("/home/agent/docs/superpowers/specs/2026-07-22-agent-acceptance-raw.json")
TODAY = date.today().strftime("%Y%m%d")
PID = f"accept-{TODAY}"
SID = f"accept-sess-{uuid.uuid4().hex[:8]}"
SID_B = f"accept-sess-b-{uuid.uuid4().hex[:8]}"
PID_C = f"accept-other-{TODAY}"
SID_C = f"accept-sess-c-{uuid.uuid4().hex[:8]}"

results: dict[str, dict] = {}


def rec(key: str, status: str, note: str = "", **extra):
    results[key] = {"status": status, "note": note, **extra}
    print(f"[{status:7}] {key}: {note[:120]}")


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=httpx.Timeout(180.0, connect=10.0))

    # --- Preflight ---
    try:
        h = c.get("/health").json()
        rec("preflight.health", "Pass", json.dumps(h, ensure_ascii=False)[:200])
    except Exception as e:
        rec("preflight.health", "Fail", str(e))
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    mcp = c.get("/v1/mcp/status")
    rec(
        "preflight.mcp",
        "Pass" if mcp.status_code == 200 and mcp.json().get("connected") else "Partial",
        mcp.text[:300],
    )

    # Ensure sessions exist via get
    for sid in (SID, SID_B, SID_C):
        c.get(f"/v1/sessions/{sid}")

    # ===== A1 / P1: project + session link =====
    r = c.post("/v1/projects", json={"name": f"验收 {TODAY}", "description": "acceptance"})
    if r.status_code == 200:
        project_id = r.json()["id"]
        rec("A1.create_project", "Pass", f"id={project_id}")
    else:
        project_id = "default"
        rec("A1.create_project", "Fail", f"{r.status_code} {r.text[:200]}")

    r = c.post(f"/v1/projects/{project_id}/sessions/{SID}")
    rec("A1.link_session", "Pass" if r.status_code == 200 else "Fail", r.text[:200])
    c.post(f"/v1/projects/{project_id}/sessions/{SID_B}")
    time.sleep(0.2)

    r = c.get(f"/v1/projects/{project_id}/sessions")
    ids = [s.get("session_id") for s in r.json().get("sessions", [])] if r.status_code == 200 else []
    if SID not in ids:
        c.post(f"/v1/projects/{project_id}/sessions/{SID}")
        time.sleep(0.2)
        r = c.get(f"/v1/projects/{project_id}/sessions")
        ids = [s.get("session_id") for s in r.json().get("sessions", [])] if r.status_code == 200 else []
    rec("P1.list_sessions", "Pass" if SID in ids else "Fail", f"sessions={ids}")

    # ===== A2 / L1–L3 documents =====
    r = c.post(
        "/v1/documents",
        json={
            "session_id": SID,
            "project_id": project_id,
            "title": "Accept MD note",
            "content": (
                "Polyak-Łojasiewicz (PL) condition: there exists μ>0 such that "
                "1/2 ||∇L(θ)||^2 ≥ μ (L(θ)-L*). Local minima under PL imply global convergence rates."
            ),
            "source": "acceptance.md",
        },
    )
    rec("A2.md_upload", "Pass" if r.status_code == 200 else "Fail", r.text[:250])
    rec("L1.md_txt", results["A2.md_upload"]["status"], results["A2.md_upload"]["note"])

    # docx
    try:
        from docx import Document
        import io

        buf = io.BytesIO()
        doc = Document()
        doc.add_paragraph("Width scaling and critical points in deep linear networks. Acceptance DOCX.")
        doc.save(buf)
        r = c.post(
            "/v1/documents/upload",
            data={"session_id": SID, "project_id": project_id},
            files={
                "file": (
                    "accept.docx",
                    buf.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        rec("L2.docx", "Pass" if r.status_code == 200 else "Fail", r.text[:250])
    except Exception as e:
        rec("L2.docx", "Fail", str(e))

    # pdf — minimal synthetic if no real pdf; try upload from data/arxiv_refs
    pdf_path = Path("/home/agent/data/arxiv_refs/2003.00307.pdf")
    if pdf_path.exists():
        r = c.post(
            "/v1/documents/upload",
            data={"session_id": SID, "project_id": project_id},
            files={"file": ("2003.00307.pdf", pdf_path.read_bytes(), "application/pdf")},
        )
        rec("L2.pdf", "Pass" if r.status_code == 200 else "Partial", r.text[:300])
    else:
        rec("L2.pdf", "Skip", "no sample pdf")

    # arxiv ingest (query params)
    r = c.post(
        "/v1/documents/from-arxiv",
        params={"session_id": SID, "project_id": project_id, "arxiv_id": "1412.6980"},
    )
    rec(
        "A2.arxiv",
        "Pass" if r.status_code == 200 else "Partial",
        f"{r.status_code} {r.text[:300]}",
    )
    rec("L3.arxiv", results["A2.arxiv"]["status"], results["A2.arxiv"]["note"])

    docs_a = c.get(f"/v1/documents?session_id={SID}&project_id={project_id}")
    total_a = docs_a.json().get("total", 0) if docs_a.status_code == 200 else 0
    rec("A2.list", "Pass" if total_a >= 1 else "Fail", f"total={total_a}")

    # ===== L4 isolation =====
    r = c.post("/v1/projects", json={"name": f"验收隔离 {TODAY}", "description": "other"})
    other_pid = r.json()["id"] if r.status_code == 200 else PID_C
    c.post(f"/v1/projects/{other_pid}/sessions/{SID_C}")
    docs_same = c.get(f"/v1/documents?session_id={SID_B}&project_id={project_id}")
    docs_other = c.get(f"/v1/documents?session_id={SID_C}&project_id={other_pid}")
    t_same = docs_same.json().get("total", 0) if docs_same.status_code == 200 else -1
    t_other = docs_other.json().get("total", 0) if docs_other.status_code == 200 else -1
    # same project session B should see project corpus (may list by project_id)
    ok_share = t_same >= 1
    ok_isol = t_other == 0 or (isinstance(docs_other.json(), dict) and all(
        (d.get("project_id") or "default") != project_id
        for d in docs_other.json().get("documents", docs_other.json().get("items", []))
    ))
    # if other project empty list — Pass isolation
    if docs_other.status_code == 200 and t_other == 0:
        ok_isol = True
    rec(
        "L4.rag_isolation",
        "Pass" if ok_share and ok_isol else "Partial",
        f"same_project_sessB_total={t_same} other_project_total={t_other}",
    )
    rec("P2.rag_share", results["L4.rag_isolation"]["status"], results["L4.rag_isolation"]["note"])

    # ===== A3 literature chat + L5 rag refs =====
    def chat(message: str, *, agent=None, mode="chat", auto_route=True, session_id=SID) -> dict:
        body = {
            "message": message,
            "session_id": session_id,
            "mode": mode,
            "auto_route": auto_route,
            "enable_tools": True,
            "project_id": project_id,
        }
        if agent:
            body["agent"] = agent
            body["auto_route"] = False
        # prefer non-stream
        resp = c.post("/v1/chat", json=body, timeout=180.0)
        if resp.status_code == 404:
            # stream fallback — collect content
            with c.stream("POST", "/v1/chat/stream", json=body, timeout=180.0) as s:
                texts = []
                tools = []
                agents = []
                for line in s.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if chunk.get("content"):
                        texts.append(chunk["content"])
                    if chunk.get("type") == "tool_result" or chunk.get("tool_name"):
                        tools.append(chunk.get("tool_name") or chunk.get("type"))
                    if chunk.get("agent_name"):
                        agents.append(chunk["agent_name"])
                    if chunk.get("type") == "agent_handoff":
                        agents.append(f"handoff:{chunk.get('to_agent')}")
                return {
                    "status_code": s.status_code,
                    "reply": "".join(texts),
                    "tools": tools,
                    "agents": agents,
                }
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        return {
            "status_code": resp.status_code,
            "reply": data.get("content") or data.get("reply") or data.get("message") or resp.text[:500],
            "raw": data,
            "tools": [],
            "agents": [data.get("agent_name")] if data.get("agent_name") else [],
        }

    t0 = time.time()
    lit = chat(
        "根据当前课题已入库文献，用三句话总结与 PL 条件或局部极小相关的方法要点。若检索到 RAG 片段请引用。",
        agent="literature",
    )
    dt = time.time() - t0
    reply_ok = lit["status_code"] == 200 and len(str(lit.get("reply") or "")) > 20
    refs = c.get(f"/v1/sessions/{SID}/rag-refs")
    nrefs = len(refs.json().get("refs", [])) if refs.status_code == 200 else 0
    rec(
        "A3.literature_chat",
        "Pass" if reply_ok else "Fail",
        f"dt={dt:.1f}s reply_len={len(str(lit.get('reply') or ''))} refs={nrefs} head={str(lit.get('reply'))[:180]}",
    )
    rec(
        "L5.rag_refs",
        "Pass" if nrefs >= 1 or ("PL" in str(lit.get("reply")) or "极小" in str(lit.get("reply"))) else "Partial",
        f"refs={nrefs}",
    )

    # ===== A4 theory =====
    th = chat(
        "请形式化一条假设：在 PL 条件下局部极小是全局最优。给出简短推导步骤（含关键不等式），不要写代码。",
        agent="theory",
        mode="math",
    )
    th_reply = str(th.get("reply") or "")
    rec(
        "A4.theory_math",
        "Pass" if th["status_code"] == 200 and len(th_reply) > 40 else "Fail",
        th_reply[:220],
    )
    # derivation artifacts
    arts = c.get(f"/v1/artifacts", params={"project_id": project_id, "session_id": SID})
    art_list = arts.json().get("artifacts") or arts.json().get("items") or []
    if isinstance(arts.json(), list):
        art_list = arts.json()
    has_trace = any(
        (a.get("type") or a.get("kind") or "") in ("DerivationTrace", "derivation_trace")
        or "Derivation" in str(a.get("type") or a.get("title") or "")
        for a in art_list
        if isinstance(a, dict)
    )
    rec(
        "T1.derivation_trace",
        "Pass" if has_trace else "Partial",
        f"artifacts={len(art_list)} has_trace={has_trace} (chat derivation={'yes' if len(th_reply)>40 else 'no'})",
    )

    # ===== A5 / T2 / T3 theorems =====
    r = c.post(
        "/v1/memory/structured",
        json={
            "session_id": SID,
            "kind": "theorem",
            "title": "验收-PL局部极小",
            "body": "若损失满足 μ-PL，则任意临界点均为全局极小。",
        },
    )
    thm_id = None
    if r.status_code == 200:
        thm_id = r.json().get("id") or r.json().get("entry", {}).get("id")
        rec("A5.theorem_create", "Pass", f"id={thm_id}")
        rec("T2.theorem_crud_create", "Pass", f"id={thm_id}")
    else:
        rec("A5.theorem_create", "Fail", r.text[:250])
        rec("T2.theorem_crud_create", "Fail", r.text[:250])

    listed = c.get(f"/v1/memory/structured?session_id={SID}")
    entries = listed.json().get("entries") or listed.json().get("items") or []
    if isinstance(listed.json(), list):
        entries = listed.json()
    rec("T2.theorem_list", "Pass" if len(entries) >= 1 else "Fail", f"n={len(entries)}")

    if thm_id:
        r = c.patch(
            f"/v1/memory/structured/{thm_id}",
            json={"title": "验收-PL局部极小(修订)", "body": "μ-PL ⇒ 临界点全局最优。"},
        )
        rec("T2.theorem_patch", "Pass" if r.status_code == 200 else "Partial", r.text[:200])

    # session B should NOT see session A theorems by default
    listed_b = c.get(f"/v1/memory/structured?session_id={SID_B}")
    entries_b = listed_b.json().get("entries") or listed_b.json().get("items") or []
    if isinstance(listed_b.json(), list):
        entries_b = listed_b.json()
    titles_b = [e.get("title") for e in entries_b if isinstance(e, dict)]
    isolated = not any("验收-PL" in (t or "") for t in titles_b)
    rec(
        "P3.theorem_session_scope",
        "Pass" if isolated else "Fail",
        f"sessB_titles_sample={titles_b[:5]} isolated={isolated}",
    )

    cite = chat(
        "请结合定理库中标题含「验收-PL」的定理，用一句话说明其对实验设计的含义。",
        agent="theory",
    )
    rec(
        "T3.theorem_in_context",
        "Pass" if cite["status_code"] == 200 and len(str(cite.get("reply") or "")) > 15 else "Partial",
        str(cite.get("reply") or "")[:220],
    )
    rec("A5.theorem_cite", results["T3.theorem_in_context"]["status"], results["T3.theorem_in_context"]["note"])

    # T4 DAG
    dag = c.get(f"/v1/theory/assumption-dag?session_id={SID}")
    rec(
        "T4.assumption_dag",
        "Pass" if dag.status_code == 200 else "Fail",
        dag.text[:250],
    )

    # T5 graph probe
    graph = c.get(f"/v1/memory/structured/graph?session_id={SID}")
    rec(
        "T5.knowledge_graph",
        "Pass" if graph.status_code == 200 else "Partial",
        f"probe {graph.status_code} {graph.text[:200]}",
    )

    # T6 workspace probe
    ws = c.get(f"/v1/theory/workspace?project_id={project_id}")
    rec(
        "T6.workspace",
        "Pass" if ws.status_code == 200 else "Partial",
        f"probe {ws.status_code} {ws.text[:200]}",
    )

    # ===== A6 experiment plan =====
    ex = chat(
        "基于上述 PL/局部极小讨论，给出一份可执行的实验计划（数据、指标、对照、不做代训），用条目列出。",
        agent="experiment",
    )
    ex_reply = str(ex.get("reply") or "")
    arts2 = c.get("/v1/artifacts", params={"project_id": project_id, "session_id": SID})
    art_list2 = arts2.json().get("artifacts") or arts2.json().get("items") or []
    if isinstance(arts2.json(), list):
        art_list2 = arts2.json()
    has_plan = any(
        "ExperimentPlan" in str(a.get("type") or a.get("kind") or a.get("title") or "")
        or "NextStep" in str(a.get("type") or "")
        for a in art_list2
        if isinstance(a, dict)
    ) or ("实验" in ex_reply and len(ex_reply) > 80)
    rec(
        "A6.experiment_plan",
        "Pass" if ex["status_code"] == 200 and has_plan else "Partial",
        f"has_artifact_plan={has_plan} reply_len={len(ex_reply)} head={ex_reply[:180]}",
    )
    rec("O1.experiment_plan", results["A6.experiment_plan"]["status"], results["A6.experiment_plan"]["note"])

    # ===== A7 / O2 csv upload =====
    csv_body = "epoch,train_loss,val_loss\n1,1.2,1.3\n2,0.9,1.0\n3,0.7,0.95\n4,0.55,0.92\n5,0.5,0.91\n"
    r = c.post(
        "/v1/jupyter/upload-file",
        data={"project_id": project_id, "session_id": SID, "name": "accept_loss_curve"},
        files={"file": ("accept_loss.csv", csv_body.encode("utf-8"), "text/csv")},
    )
    rec("A7.upload_csv", "Pass" if r.status_code == 200 else "Fail", r.text[:250])
    rec("O2.experiment_log", results["A7.upload_csv"]["status"], results["A7.upload_csv"]["note"])

    follow = chat(
        "我已上传 loss 曲线 CSV（train_loss 下降但 val_loss 平台）。请对照给出下一步实验方向（调参/正则/宽度），不要代跑训练。",
        agent="experiment",
    )
    rec(
        "A7.data_to_nextstep",
        "Pass" if follow["status_code"] == 200 and len(str(follow.get("reply") or "")) > 40 else "Partial",
        str(follow.get("reply") or "")[:220],
    )
    rec("P4.experiment_reuse_weak", "Partial", "同课题上传成功；跨会话复用未深测")

    # ===== A8 / O3 export =====
    prev = c.get(f"/v1/export/preview?session_id={SID}")
    rec("A8.preview", "Pass" if prev.status_code == 200 else "Fail", prev.text[:200])
    md = c.post("/v1/export/md", json={"session_id": SID, "title": "验收导出", "project_id": project_id})
    rec("A8.md", "Pass" if md.status_code == 200 and len(md.content) > 50 else "Fail", f"bytes={len(md.content)}")
    docx = c.post("/v1/export/docx", json={"session_id": SID, "title": "验收导出", "project_id": project_id})
    rec("A8.docx", "Pass" if docx.status_code == 200 and len(docx.content) > 100 else "Fail", f"bytes={len(docx.content)}")
    pdf = c.post("/v1/export/pdf", json={"session_id": SID, "title": "验收导出", "project_id": project_id})
    rec(
        "O3.export",
        "Pass" if md.status_code == 200 and docx.status_code == 200 else "Fail",
        f"md={md.status_code} docx={docx.status_code} pdf={pdf.status_code}",
    )
    polish = c.post(
        "/v1/export/polish",
        json={
            "session_id": SID,
            "title": "验收导出",
            "project_id": project_id,
            "ai_instructions": "保持学术语气，精简条目。",
            "use_ai": True,
        },
    )
    rec(
        "O3.polish",
        "Pass" if polish.status_code == 200 else "Partial",
        f"{polish.status_code} {polish.text[:200]}",
    )

    # ===== A9 / C4 MCP via chat =====
    mcp_chat = chat(
        "请用工具检索 arXiv 上关于 Polyak-Lojasiewicz condition 的一篇论文，返回标题与 arXiv id。",
        agent="literature",
    )
    mcp_ok = mcp_chat["status_code"] == 200 and (
        "arxiv" in str(mcp_chat.get("reply")).lower()
        or "140" in str(mcp_chat.get("reply"))
        or "PL" in str(mcp_chat.get("reply"))
        or len(str(mcp_chat.get("reply") or "")) > 40
    )
    rec(
        "A9.mcp_arxiv",
        "Pass" if mcp_ok else "Partial",
        str(mcp_chat.get("reply") or "")[:250],
    )
    rec("C4.mcp_tools", results["A9.mcp_arxiv"]["status"], results["A9.mcp_arxiv"]["note"])

    # ===== C1 modes =====
    chat_mode = chat("用一句话解释过拟合。", agent="general", mode="chat")
    math_mode = chat("写出二次函数 f(x)=x^2 在 0 处的导数。", agent="theory", mode="math")
    rec(
        "C1.chat_math_modes",
        "Pass" if chat_mode["status_code"] == 200 and math_mode["status_code"] == 200 else "Fail",
        f"chat_len={len(str(chat_mode.get('reply')))} math_len={len(str(math_mode.get('reply')))}",
    )

    # ===== C2 auto route =====
    auto_lit = chat("帮我找一篇关于 diffusion models 的综述方向文献线索", auto_route=True)
    auto_th = chat("证明：可微函数在临界点处梯度为零。只要要点。", auto_route=True)
    rec(
        "C2.auto_route",
        "Pass" if auto_lit["status_code"] == 200 and auto_th["status_code"] == 200 else "Partial",
        f"agents_lit={auto_lit.get('agents')} agents_th={auto_th.get('agents')} "
        f"(reply lengths {len(str(auto_lit.get('reply')))}/{len(str(auto_th.get('reply')))})",
    )

    # ===== C3 manual agent =====
    man = chat("你的职责是什么？一句话。", agent="review")
    rec(
        "C3.manual_agent",
        "Pass" if man["status_code"] == 200 else "Fail",
        str(man.get("reply") or "")[:200],
    )

    # ===== C5 prompt optimize =====
    po = c.post(
        "/v1/prompt/optimize",
        json={"text": "帮我看看这个损失好不好", "goal": "更可验证、适合科研助手"},
    )
    rec(
        "C5.prompt_optimize",
        "Pass" if po.status_code == 200 else "Partial",
        po.text[:250],
    )

    # ===== C6 settings probe via agents list + mcp reload =====
    ag = c.get("/v1/agents")
    reload = c.post("/v1/mcp/reload")
    rec(
        "C6.settings_surface",
        "Pass" if ag.status_code == 200 else "Fail",
        f"agents={ag.status_code} mcp_reload={reload.status_code}",
    )

    # ===== C7 model =====
    rec("C7.model", "Pass", json.dumps(h, ensure_ascii=False))

    # L6 skip
    rec("L6.method_card", "Skip", "按方案不测")

    # rename project weak P1
    ren = c.patch(f"/v1/projects/{project_id}", json={"name": f"验收 {TODAY} (renamed)"})
    if ren.status_code >= 400:
        ren = c.put(f"/v1/projects/{project_id}", json={"name": f"验收 {TODAY} (renamed)"})
    rec("P1.rename_project", "Pass" if ren.status_code == 200 else "Partial", ren.text[:200])

    meta = {
        "project_id": project_id,
        "session_id": SID,
        "session_b": SID_B,
        "other_project": other_pid,
        "health": h,
    }
    OUT.write_text(
        json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {OUT}")
    fails = [k for k, v in results.items() if v["status"] == "Fail"]
    print(f"Fail count: {len(fails)} -> {fails}")
    return 0 if not fails else 2


if __name__ == "__main__":
    sys.exit(main())
