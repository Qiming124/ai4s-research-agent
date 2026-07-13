# SkillsBridge 与 run_campaign CLI 测试。

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_skills_bridge_list():
    from server.skills.bridge import get_skills_bridge

    bridge = get_skills_bridge()
    skills = bridge.list_available_skills()
    assert isinstance(skills, list)


def test_skills_bridge_explore_output(tmp_path, monkeypatch):
    from server.skills.bridge import SkillsBridge

    bridge = SkillsBridge(explore_output_dir=tmp_path)
    path = bridge.write_explore_output("test-artifact", {"ok": True})
    assert Path(path).is_file()
    assert json.loads(Path(path).read_text())["ok"] is True


def test_run_campaign_cli_list():
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "run_campaign.py"), "list"],
        capture_output=True,
        text=True,
        cwd=str(root),
        check=False,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert isinstance(data, list)
