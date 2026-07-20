# =============================================================================
# Skills 桥接：调用外部 Cursor skill 或本地脚本。
#
# 职责：
#     1. SkillsBridge 映射 SKILL_SLUGS 到本地脚本或外部命令
#     2. 将 Campaign 阶段与 loss-landscape-research 等 skill 衔接
#     3. subprocess 执行并捕获 JSON 输出
#
# 架构位置：
#     - 被调用：server/graph/research_supervisor.py（可选 skill 阶段）
#     - 调用：shared/paths.PROJECT_ROOT、subprocess
#
# 阅读提示：
#     - 新人先看 SkillsBridge.run_skill 与 SKILL_SLUGS
#
# Debug：
#     - skill 未找到 → slug 不在 SKILL_SLUGS 或脚本路径缺失
#     - 非零 exit code → 检查脚本 stderr 日志
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
    """将项目内 Campaign 与外部 skill / 脚本衔接。"""

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

    def bootstrap_campaign_artifact(self, project_id: str, campaign: dict[str, Any]) -> str:
        return self.write_explore_output(
            f"campaign-{project_id}-{campaign.get('id', 'unknown')}",
            {
                "kind": "campaign_bootstrap",
                "project_id": project_id,
                "campaign": campaign,
            },
        )


_bridge: SkillsBridge | None = None


def get_skills_bridge() -> SkillsBridge:
    global _bridge
    if _bridge is None:
        _bridge = SkillsBridge()
    return _bridge
