# =============================================================================
# Skills 桥接：调用外部 Cursor skill 或本地脚本。
# =============================================================================

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from shared.paths import DATA_ROOT, PROJECT_ROOT

logger = logging.getLogger(__name__)

SKILL_SLUGS = (
    "loss-landscape-research",
    "ai-research-explore",
    "academic-paper-reviewer",
    "brainstorming",
)


class SkillsBridge:
    """将外部 skill / 本地脚本与课题工作流衔接。"""

    def __init__(self, explore_output_dir: Path | None = None) -> None:
        self._explore_dir = explore_output_dir or (DATA_ROOT / "explore_outputs")
        self._explore_dir.mkdir(parents=True, exist_ok=True)

    def list_available_skills(self) -> list[str]:
        agents_skills = Path.home() / ".agents" / "skills"
        found = []
        for slug in SKILL_SLUGS:
            if (agents_skills / slug / "SKILL.md").is_file():
                found.append(slug)
        return found

    def write_explore_output(self, name: str, payload: dict[str, Any]) -> str:
        path = self._explore_dir / f"{name}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def invoke_script(self, script: str, *args: str, timeout: int = 120) -> dict[str, Any]:
        script_path = PROJECT_ROOT / script
        if not script_path.is_file():
            return {"status": "error", "reason": f"脚本不存在: {script_path}"}
        try:
            proc = subprocess.run(
                ["python", str(script_path), *args],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(PROJECT_ROOT),
                check=False,
            )
            return {
                "status": "ok" if proc.returncode == 0 else "error",
                "returncode": proc.returncode,
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-2000:],
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "reason": "脚本执行超时"}
        except Exception as exc:
            logger.warning("SkillsBridge 脚本调用失败: %s", exc)
            return {"status": "error", "reason": str(exc)}


_bridge: SkillsBridge | None = None


def get_skills_bridge() -> SkillsBridge:
    global _bridge
    if _bridge is None:
        _bridge = SkillsBridge()
    return _bridge
