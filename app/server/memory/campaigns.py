# =============================================================================
# 科研 Campaign 存储：8 阶段流水线状态与产物。
#
# 职责：
#     1. CRUD Campaign 记录、阶段、门禁 gates 与 status
#     2. 管理 data/campaigns/{project_id}/{campaign_id}/ 产物目录
#     3. delete_campaigns_for_project() 批量清理课题下 Campaign
#
# 架构位置：
#     - 被调用：server/api/campaigns.py、graph/research_supervisor.py、api/projects.py
#     - 调用：shared/paths.DATA_ROOT、server/config.py
#
# 阅读提示：
#     - 新人先看 CAMPAIGN_STAGES、CampaignStore.create_campaign、
#       update_campaign、delete_campaigns_for_project
#
# Debug：
#     - 阶段不推进 → gates JSON 或 advance_stage 调用
#     - 产物目录缺失 → campaign_artifacts_dir 与 mkdir 逻辑
# =============================================================================

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from server.config import get_settings
from shared.paths import DATA_ROOT

CAMPAIGN_STAGES: tuple[str, ...] = (
    "S0_campaign",
    "S1_literature",
    "S2_formalization",
    "S3_theory",
    "S4_counterexample",
    "S5_experiment",
    "S6_synthesis",
    "S7_review",
    "S8_archive",
)


def campaign_stage_rank(stage: str | None) -> int:
    """阶段进度排序：越大越接近完成；complete / S8 视为最高。"""
    s = str(stage or "")
    if s in ("complete", "S8_archive"):
        return len(CAMPAIGN_STAGES)
    try:
        return CAMPAIGN_STAGES.index(s)
    except ValueError:
        return -1

DEFAULT_GATES: dict[str, str] = {
    "S1_literature": "pending",
    "S3_theory": "pending",
    "S5_experiment": "pending",
    "S7_review": "pending",
}

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS research_campaigns (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL,
    title           TEXT NOT NULL,
    task_family     TEXT NOT NULL DEFAULT 'loss_landscape_critical_points',
    dataset         TEXT NOT NULL DEFAULT '',
    benchmark       TEXT NOT NULL DEFAULT '',
    sota_reference  TEXT NOT NULL DEFAULT '[]',
    compute_budget  TEXT NOT NULL DEFAULT '{}',
    assumptions     TEXT NOT NULL DEFAULT '[]',
    current_stage   TEXT NOT NULL DEFAULT 'S0_campaign',
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK(status IN ('active','blocked','done','iterate')),
    stage_artifacts TEXT NOT NULL DEFAULT '{}',
    gates           TEXT NOT NULL DEFAULT '{}',
    session_id      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def campaign_artifacts_dir(project_id: str, campaign_id: str) -> Path:
    root = DATA_ROOT / "campaigns" / project_id / campaign_id
    root.mkdir(parents=True, exist_ok=True)
    return root


class CampaignStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.commit()
        self._ensure_demo_campaign()

    def _ensure_demo_campaign(self) -> None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM research_campaigns WHERE id = 'pl-critical-points-demo'"
            ).fetchone()
            if row:
                return
            now = _now_iso()
            payload = {
                "id": "pl-critical-points-demo",
                "project_id": "default",
                "title": "PL 条件下经验损失临界点分类 — 从二次损失到浅层 MLP",
                "task_family": "loss_landscape_critical_points",
                "dataset": "synthetic_quadratic + MNIST_subset",
                "benchmark": "critical_point_classification + hessian_min_eig",
                "sota_reference": json.dumps(
                    ["arXiv:1712.06559", "arXiv:1902.02366"],
                    ensure_ascii=False,
                ),
                "compute_budget": json.dumps(
                    {"max_torch_runs": 3, "max_llm_turns": 50},
                    ensure_ascii=False,
                ),
                "assumptions": json.dumps(["A1", "A4", "A6"], ensure_ascii=False),
                "current_stage": "S0_campaign",
                "status": "active",
                "stage_artifacts": "{}",
                "gates": json.dumps(DEFAULT_GATES, ensure_ascii=False),
                "session_id": None,
                "created_at": now,
                "updated_at": now,
            }
            self._conn.execute(
                """
                INSERT INTO research_campaigns (
                    id, project_id, title, task_family, dataset, benchmark,
                    sota_reference, compute_budget, assumptions, current_stage,
                    status, stage_artifacts, gates, session_id, created_at, updated_at
                ) VALUES (
                    :id, :project_id, :title, :task_family, :dataset, :benchmark,
                    :sota_reference, :compute_budget, :assumptions, :current_stage,
                    :status, :stage_artifacts, :gates, :session_id, :created_at, :updated_at
                )
                """,
                payload,
            )
            self._conn.commit()
        campaign_artifacts_dir("default", "pl-critical-points-demo")
        problem_path = DATA_ROOT / "theory" / "campaigns" / "pl-critical-points.md"
        problem_path.parent.mkdir(parents=True, exist_ok=True)
        if not problem_path.exists():
            problem_path.write_text(
                "# PL 条件下经验损失临界点分类\n\n"
                "> 在假设 A1（光滑）、A4（PL）、A6（有限样本）下，经验风险 "
                "$L(\\theta)$ 的临界点如何分类（局部极小 / 鞍点）？\n",
                encoding="utf-8",
            )

    def list_campaigns(self, project_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM research_campaigns
                WHERE project_id = ?
                ORDER BY updated_at DESC
                """,
                (project_id,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM research_campaigns WHERE id = ?",
                (campaign_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_campaign_for_session(
        self,
        project_id: str,
        session_id: str | None,
    ) -> dict[str, Any] | None:
        """优先返回绑定到该会话的 Campaign（含已完成），用于会话-课题对齐。"""
        if not session_id:
            return None
        matches: list[dict[str, Any]] = []
        for camp in self.list_campaigns(project_id):
            if camp.get("session_id") != session_id:
                continue
            # 忽略 done 且停在 S0 的空壳
            if (
                camp.get("status") == "done"
                and str(camp.get("current_stage") or "") in ("", "S0_campaign")
            ):
                continue
            matches.append(camp)
        if not matches:
            return None
        # 同会话多条时取进度最深的，避免新开的浅进度盖住已完成
        return max(
            matches,
            key=lambda c: (
                campaign_stage_rank(c.get("current_stage")),
                1 if c.get("status") == "done" else 0,
                str(c.get("updated_at") or ""),
            ),
        )

    def get_active_campaign(
        self,
        project_id: str,
        campaign_id: str | None = None,
        *,
        session_id: str | None = None,
        prefer_open: bool = True,
    ) -> dict[str, Any] | None:
        if campaign_id:
            camp = self.get_campaign(campaign_id)
            if camp and camp["project_id"] == project_id:
                return camp
            return None

        # 会话绑定优先，避免同课题下不同会话串到别的 Campaign
        if session_id:
            bound = self.get_campaign_for_session(project_id, session_id)
            if bound:
                return bound

        # list_campaigns 已按 updated_at DESC
        campaigns = self.list_campaigns(project_id)
        if not campaigns:
            return None

        # 忽略「done 且仍停在 S0」的空壳，避免盖住真实进度
        visible = [
            c
            for c in campaigns
            if not (
                c.get("status") == "done"
                and str(c.get("current_stage") or "") in ("", "S0_campaign")
            )
        ] or campaigns

        open_camps = [
            c for c in visible if c.get("status") in ("active", "blocked", "iterate")
        ]
        # 其它会话绑定的未结束 Campaign 不抢当前会话
        if session_id:
            open_camps = [
                c
                for c in open_camps
                if not c.get("session_id") or c.get("session_id") == session_id
            ]
        if prefer_open and open_camps:
            # 执行路径：优先未结束；同状态下取进度更深、更新更近的
            return max(
                open_camps,
                key=lambda c: (
                    campaign_stage_rank(c.get("current_stage")),
                    str(c.get("updated_at") or ""),
                ),
            )
        # 展示路径：按阶段进度取最深的，避免「新开的 S1」盖住已完成的 S8
        return max(
            visible,
            key=lambda c: (
                campaign_stage_rank(c.get("current_stage")),
                1 if c.get("status") == "done" else 0,
                str(c.get("updated_at") or ""),
            ),
        )
    def create_campaign(
        self,
        project_id: str,
        *,
        title: str,
        task_family: str = "loss_landscape_critical_points",
        dataset: str = "",
        benchmark: str = "",
        sota_reference: list[str] | None = None,
        compute_budget: dict[str, Any] | None = None,
        assumptions: list[str] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        cid = str(uuid.uuid4())[:12]
        now = _now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO research_campaigns (
                    id, project_id, title, task_family, dataset, benchmark,
                    sota_reference, compute_budget, assumptions, current_stage,
                    status, stage_artifacts, gates, session_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'S0_campaign', 'active', '{}', ?, ?, ?, ?)
                """,
                (
                    cid,
                    project_id,
                    title,
                    task_family,
                    dataset,
                    benchmark,
                    json.dumps(sota_reference or [], ensure_ascii=False),
                    json.dumps(compute_budget or {}, ensure_ascii=False),
                    json.dumps(assumptions or [], ensure_ascii=False),
                    json.dumps(DEFAULT_GATES, ensure_ascii=False),
                    session_id,
                    now,
                    now,
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM research_campaigns WHERE id = ?", (cid,)
            ).fetchone()
        campaign_artifacts_dir(project_id, cid)
        return self._row_to_dict(row)

    def update_campaign(self, campaign_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {
            "current_stage",
            "status",
            "stage_artifacts",
            "gates",
            "session_id",
            "title",
            "dataset",
            "benchmark",
        }
        updates: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in allowed or value is None:
                continue
            if key in ("stage_artifacts", "gates"):
                updates[key] = json.dumps(value, ensure_ascii=False)
            else:
                updates[key] = value
        if not updates:
            return self.get_campaign(campaign_id)
        updates["updated_at"] = _now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with self._lock:
            self._conn.execute(
                f"UPDATE research_campaigns SET {set_clause} WHERE id = ?",
                (*updates.values(), campaign_id),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM research_campaigns WHERE id = ?", (campaign_id,)
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def save_stage_artifact(
        self,
        campaign_id: str,
        stage: str,
        artifact: dict[str, Any],
        *,
        persist_file: bool = True,
    ) -> dict[str, Any] | None:
        camp = self.get_campaign(campaign_id)
        if not camp:
            return None
        artifacts = dict(camp.get("stage_artifacts") or {})
        artifacts[stage] = artifact
        if persist_file:
            root = campaign_artifacts_dir(camp["project_id"], campaign_id)
            path = root / f"{stage}.json"
            path.write_text(
                json.dumps(artifact, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            artifact["artifact_path"] = str(path)
            artifacts[stage] = artifact
        return self.update_campaign(
            campaign_id,
            stage_artifacts=artifacts,
            current_stage=stage,
        )

    def update_gate(self, campaign_id: str, stage: str, status: str) -> dict[str, Any] | None:
        camp = self.get_campaign(campaign_id)
        if not camp:
            return None
        gates = dict(camp.get("gates") or {})
        gates[stage] = status
        camp_status = camp.get("status", "active")
        if status == "fail":
            camp_status = "blocked"
        return self.update_campaign(campaign_id, gates=gates, status=camp_status)

    def advance_stage(self, campaign_id: str, next_stage: str) -> dict[str, Any] | None:
        return self.update_campaign(campaign_id, current_stage=next_stage)

    def delete_campaigns_for_project(self, project_id: str) -> int:
        """
        删除课题下全部 Campaign 记录，并移除 data/campaigns/{project_id}/。

        参数:
            project_id: 课题 ID

        返回:
            删除的 Campaign 行数
        """
        pid = (project_id or "").strip()
        if not pid:
            return 0
        with self._lock:
            rows = self._conn.execute(
                "SELECT id FROM research_campaigns WHERE project_id = ?",
                (pid,),
            ).fetchall()
            self._conn.execute(
                "DELETE FROM research_campaigns WHERE project_id = ?",
                (pid,),
            )
            self._conn.commit()
        root = DATA_ROOT / "campaigns" / pid
        if root.exists():
            try:
                shutil.rmtree(root)
            except OSError:
                logger.exception("删除 Campaign 目录失败 project_id=%s path=%s", pid, root)
        return len(rows)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "title": row["title"],
            "task_family": row["task_family"],
            "dataset": row["dataset"],
            "benchmark": row["benchmark"],
            "sota_reference": json.loads(row["sota_reference"] or "[]"),
            "compute_budget": json.loads(row["compute_budget"] or "{}"),
            "assumptions": json.loads(row["assumptions"] or "[]"),
            "current_stage": row["current_stage"],
            "status": row["status"],
            "stage_artifacts": json.loads(row["stage_artifacts"] or "{}"),
            "gates": json.loads(row["gates"] or "{}"),
            "session_id": row["session_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


_campaign_store: CampaignStore | None = None


def get_campaign_store() -> CampaignStore:
    global _campaign_store
    if _campaign_store is None:
        settings = get_settings()
        _campaign_store = CampaignStore(settings.session_db_path)
    return _campaign_store
