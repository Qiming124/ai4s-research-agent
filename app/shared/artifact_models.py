# =============================================================================
# 理论侧工件（Artifact）数据模型。
# =============================================================================

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


ArtifactType = Literal[
    "DerivationTrace",
    "ExperimentPlan",
    "DataPacket",
    "NextStepMemo",
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class DerivationStep(BaseModel):
    title: str = ""
    body: str = ""
    status: Literal["proven", "pending", "heuristic"] = "pending"


class DerivationTrace(BaseModel):
    id: str
    project_id: str = "default"
    session_id: str | None = None
    l4_ref_ids: list[str] = Field(default_factory=list)
    steps: list[DerivationStep] = Field(default_factory=list)
    claim_yaml: str | None = None
    title: str = ""
    created_at: str = Field(default_factory=_utcnow)


class ExperimentPlan(BaseModel):
    id: str
    project_id: str = "default"
    session_id: str | None = None
    claim_or_theorem_ref: str | None = None
    objectives: str = ""
    variables: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    hyperparams: dict[str, Any] = Field(default_factory=dict)
    success_criteria: list[str] = Field(default_factory=list)
    record_fields: list[str] = Field(default_factory=list)
    notes: str = ""
    title: str = ""
    #: planned=待做 · active=进行中 · done=已完成 · superseded=已被后续计划取代
    status: Literal["planned", "active", "done", "superseded"] = "planned"
    #: 若本计划由旧计划修订而来，填父计划 id（便于追溯历史）
    parent_plan_id: str | None = None
    revision_note: str = ""
    created_at: str = Field(default_factory=_utcnow)


class DataPacket(BaseModel):
    id: str
    project_id: str = "default"
    session_id: str | None = None
    source: Literal["jupyter_upload", "manual", "experiment_log"] = "manual"
    metrics: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    log_path: str | None = None
    raw_ref: str | None = None
    title: str = ""
    created_at: str = Field(default_factory=_utcnow)


class NextStepMemo(BaseModel):
    id: str
    project_id: str = "default"
    session_id: str | None = None
    data_packet_id: str | None = None
    claim_ref: str | None = None
    verdict: Literal["supported", "refuted", "inconclusive"] = "inconclusive"
    missing_data: list[str] = Field(default_factory=list)
    next_experiments: list[str] = Field(default_factory=list)
    notes: str = ""
    title: str = ""
    created_at: str = Field(default_factory=_utcnow)


class ArtifactSummary(BaseModel):
    id: str
    type: ArtifactType
    project_id: str
    session_id: str | None = None
    title: str = ""
    created_at: str = ""


class ArtifactListResponse(BaseModel):
    artifacts: list[ArtifactSummary]


class ArtifactDetailResponse(BaseModel):
    type: ArtifactType
    data: dict[str, Any]
