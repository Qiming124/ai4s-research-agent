# 证据链修复：注入 / 种子 / filesystem / 场景

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.config import Settings
from server.graph.scenes.workflow import _is_persist_plan_only, match_scene
from server.memory.structured.injection import build_structured_augmented_prompt
from server.mcp.servers import filesystem as fs_mod


def test_augmented_prompt_has_no_workspace_section(tmp_path):
    """Fix1：不再注入「项目理论工作区」段。"""
    db = tmp_path / "sessions.db"
    s = Settings(
        deepseek_api_key="sk-test-key-not-placeholder",
        session_db_path=str(db),
        enable_structured_memory=True,
    )
    out = build_structured_augmented_prompt(
        "BASE_PROMPT",
        session_id="sess-inject-1",
        agent_name="theory",
        settings=s,
    )
    assert out == "BASE_PROMPT" or "结构化科研记忆" in out
    assert "项目理论工作区" not in out
    assert "A1（光滑性）" not in out
    assert "symbols.md" not in out
    assert "assumptions.md" not in out


def test_seed_theory_workspace_no_a1a6_templates(tmp_path, monkeypatch):
    """Fix2：新建课题 theory 下无 assumptions/symbols 模板。"""
    from server.memory import projects as projects_mod

    monkeypatch.setattr(projects_mod, "DATA_ROOT", tmp_path)
    db = tmp_path / "proj.db"
    store = projects_mod.ProjectStore(str(db))
    pid = store.create_project(name="seed-test")["id"]
    root = store.seed_theory_workspace(pid)
    assert root.is_dir()
    assert not (root / "assumptions.md").exists()
    assert not (root / "symbols.md").exists()
    assert not (root / "assumption-matrix.md").exists()
    assert not (root / "review-checklist.md").exists()
    assert (root / ".gitkeep").exists()


def test_filesystem_blocks_theory_seed(tmp_path, monkeypatch):
    """Fix3：禁止访问 data/theory 与课题 theory 已下线 md。"""
    mcp_files = tmp_path / "mcp_files"
    projects = tmp_path / "projects"
    mcp_files.mkdir()
    exp = projects / "p1" / "experiments"
    exp.mkdir(parents=True)
    (exp / "ok.txt").write_text("hi", encoding="utf-8")

    monkeypatch.setenv("MCP_ALLOWED_DIRS", f"{mcp_files}:{projects}")

    fake_theory = tmp_path / "data" / "theory" / "assumptions.md"
    fake_theory.parent.mkdir(parents=True)
    fake_theory.write_text("A1", encoding="utf-8")

    with pytest.raises(ValueError, match="理论种子|禁止"):
        fs_mod._resolve_safe(str(fake_theory))

    proj_theory = projects / "p1" / "theory" / "assumptions.md"
    proj_theory.parent.mkdir(parents=True)
    proj_theory.write_text("A1", encoding="utf-8")
    with pytest.raises(ValueError):
        fs_mod._resolve_safe(str(proj_theory))

    ok = exp / "ok.txt"
    assert fs_mod._resolve_safe(str(ok)) == ok.resolve()


def test_whitelist_review_has_no_filesystem():
    """Fix3：review 白名单不含 filesystem。"""
    path = Path(__file__).resolve().parents[2] / "conf" / "mcp_tool_whitelist.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    review = data["agents"]["review"]
    assert review == []
    assert not any("filesystem" in str(x) for x in review)


def test_match_persist_experiment_plan():
    """Fix6：短指令写入实验计划 → experiment_plan 场景。"""
    assert _is_persist_plan_only("请写入实验计划")
    assert _is_persist_plan_only("保存实验计划到面板")
    assert not _is_persist_plan_only("请设计一套完整的可复现实验计划并详细说明每一步")

    s = Settings(deepseek_api_key="sk-test-key-not-placeholder", research_pipeline_mode="auto")
    m = match_scene("写入实验计划", agent="general", mode="chat", settings=s)
    assert m is not None
    assert m.scene_id == "experiment_plan"
    assert m.reason == "scene:persist_experiment_plan"
