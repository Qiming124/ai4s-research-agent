# get_active_campaign / workflow finalize 回归

from __future__ import annotations

from server.graph.workflow import finalize_workflow_records, upsert_workflow_record
from server.memory.campaigns import CampaignStore


def test_upsert_collapses_duplicate_plan_steps():
    records: list[dict] = []
    upsert_workflow_record(
        records,
        {"step_kind": "plan", "status": "running", "title": "规划", "detail": "", "tool_call_id": None},
    )
    upsert_workflow_record(
        records,
        {"step_kind": "plan", "status": "running", "title": "规划", "detail": "", "tool_call_id": None},
    )
    upsert_workflow_record(
        records,
        {
            "step_kind": "plan",
            "status": "done",
            "title": "规划",
            "detail": "完成",
            "tool_call_id": "wf-plan",
        },
    )
    assert len(records) == 1
    assert records[0]["status"] == "done"
    assert records[0]["tool_call_id"] == "wf-plan"


def test_finalize_marks_running_done():
    out = finalize_workflow_records(
        [
            {"step_kind": "plan", "status": "running", "title": "规划", "detail": ""},
            {"step_kind": "plan", "status": "running", "title": "规划", "detail": ""},
        ]
    )
    assert out is not None
    assert len(out) == 1
    assert out[0]["status"] == "done"


def test_get_active_prefers_session_bound(tmp_path):
    store = CampaignStore(tmp_path / "c.db")
    # 避免 demo 干扰：直接用空库逻辑 —— CampaignStore 可能 seed demo
    open_camp = store.create_campaign(
        "default", title="open-other", session_id="sess-other",
    )
    store.update_campaign(open_camp["id"], current_stage="S4_counterexample", status="active")
    done = store.create_campaign(
        "default", title="done-mine", session_id="sess-mine",
    )
    store.update_campaign(done["id"], current_stage="S8_archive", status="done")

    mine = store.get_active_campaign("default", session_id="sess-mine", prefer_open=True)
    assert mine is not None
    assert mine["id"] == done["id"]
    assert mine["status"] == "done"

    # 无会话绑定时，prefer_open 应拿到未结束的
    active = store.get_active_campaign("default", prefer_open=True)
    assert active is not None
    assert active["status"] in ("active", "blocked", "iterate")
