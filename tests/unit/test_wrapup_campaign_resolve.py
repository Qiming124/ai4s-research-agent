# 收尾时不得被浅层测试 Campaign 抢走已完成课题

from __future__ import annotations

from server.graph.research_supervisor import ResearchSupervisorPipeline
from server.memory.campaigns import CampaignStore, campaign_stage_rank


def test_wrapup_intent_detects_keywords():
    assert ResearchSupervisorPipeline._is_wrapup_intent(
        "/research 请收尾总结", "请收尾总结"
    )
    assert not ResearchSupervisorPipeline._is_wrapup_intent(
        "/research 请对损失函数进行研究", "请对损失函数进行研究"
    )


def test_finished_includes_s8_archive():
    pipe = ResearchSupervisorPipeline.__new__(ResearchSupervisorPipeline)
    assert pipe._campaign_finished({"status": "done", "current_stage": "S8_archive"})
    assert pipe._campaign_finished({"status": "active", "current_stage": "complete"})
    assert not pipe._campaign_finished({"status": "active", "current_stage": "S4_counterexample"})


def test_shallow_open_does_not_block_finished_display(tmp_path):
    store = CampaignStore(tmp_path / "wrap.db")
    shallow = store.create_campaign("default", title="test-S1", session_id=None)
    store.update_campaign(shallow["id"], current_stage="S1_literature", status="active")
    done = store.create_campaign("default", title="real-done", session_id="sess-a")
    store.update_campaign(done["id"], current_stage="S8_archive", status="done")

    # 其它会话 + prefer_open：会先撞上未绑定的浅层 active
    stolen = store.get_active_campaign(
        "default", session_id="sess-other", prefer_open=True,
    )
    assert stolen is not None
    assert stolen["id"] == shallow["id"]

    # 收尾/展示路径：应拿到已完成的深层 Campaign
    display = store.get_active_campaign("default", prefer_open=False)
    assert display is not None
    assert display["id"] == done["id"]
    assert campaign_stage_rank(display["current_stage"]) > campaign_stage_rank(
        stolen["current_stage"]
    )
