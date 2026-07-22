# =============================================================================
# 课题级 Artifact 持久化（JSON 文件 + 索引）。
# =============================================================================

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from shared.artifact_models import (
    ArtifactSummary,
    ArtifactType,
    DataPacket,
    DerivationTrace,
    ExperimentPlan,
    NextStepMemo,
)
from server.artifacts.extract import normalize_artifact_payload
from shared.paths import DATA_ROOT

logger = logging.getLogger(__name__)

_TYPE_TO_MODEL = {
    "DerivationTrace": DerivationTrace,
    "ExperimentPlan": ExperimentPlan,
    "DataPacket": DataPacket,
    "NextStepMemo": NextStepMemo,
}


class ArtifactStore:
    """按 project 落盘：data/projects/{id}/artifacts/{type}/{uuid}.json"""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or (DATA_ROOT / "projects")

    def _project_dir(self, project_id: str) -> Path:
        pid = (project_id or "default").strip() or "default"
        return self._root / pid / "artifacts"

    def _type_dir(self, project_id: str, artifact_type: str) -> Path:
        d = self._project_dir(project_id) / artifact_type
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _index_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "index.json"

    def _load_index(self, project_id: str) -> list[dict[str, Any]]:
        path = self._index_path(project_id)
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            logger.warning("artifact index 损坏: %s", path)
            return []

    def _save_index(self, project_id: str, entries: list[dict[str, Any]]) -> None:
        root = self._project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        self._index_path(project_id).write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save(self, artifact_type: ArtifactType, payload: dict[str, Any]) -> dict[str, Any]:
        model_cls = _TYPE_TO_MODEL[artifact_type]
        if not payload.get("id"):
            payload = {**payload, "id": str(uuid.uuid4())}
        payload = normalize_artifact_payload(artifact_type, payload)
        obj = model_cls.model_validate(payload)
        data = obj.model_dump()
        project_id = data.get("project_id") or "default"
        path = self._type_dir(project_id, artifact_type) / f"{data['id']}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        title = data.get("title") or data.get("objectives") or data.get("problem_setup") or data["id"]
        if isinstance(title, str) and len(title) > 80:
            title = title[:77] + "..."
        entry = {
            "id": data["id"],
            "type": artifact_type,
            "project_id": project_id,
            "session_id": data.get("session_id"),
            "title": title or data["id"],
            "created_at": data.get("created_at") or "",
        }
        index = [e for e in self._load_index(project_id) if e.get("id") != data["id"]]
        index.insert(0, entry)
        self._save_index(project_id, index)
        return data

    def get(self, project_id: str, artifact_type: ArtifactType, artifact_id: str) -> dict[str, Any] | None:
        path = self._type_dir(project_id, artifact_type) / f"{artifact_id}.json"
        if not path.is_file():
            # 尝试在各 type 下查找
            for t in _TYPE_TO_MODEL:
                p = self._type_dir(project_id, t) / f"{artifact_id}.json"
                if p.is_file():
                    return json.loads(p.read_text(encoding="utf-8"))
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def get_by_id(self, project_id: str, artifact_id: str) -> tuple[ArtifactType, dict[str, Any]] | None:
        for t in _TYPE_TO_MODEL:
            path = self._type_dir(project_id, t) / f"{artifact_id}.json"
            if path.is_file():
                return t, json.loads(path.read_text(encoding="utf-8"))  # type: ignore[return-value]
        return None

    def update(
        self,
        project_id: str,
        artifact_id: str,
        patch: dict[str, Any],
    ) -> tuple[ArtifactType, dict[str, Any]] | None:
        found = self.get_by_id(project_id, artifact_id)
        if not found:
            return None
        artifact_type, current = found
        merged = {**current, **{k: v for k, v in patch.items() if k != "id"}}
        merged["id"] = artifact_id
        merged["project_id"] = current.get("project_id") or project_id or "default"
        return artifact_type, self.save(artifact_type, merged)

    def delete(self, project_id: str, artifact_id: str) -> bool:
        found = self.get_by_id(project_id, artifact_id)
        if not found:
            return False
        artifact_type, _ = found
        path = self._type_dir(project_id, artifact_type) / f"{artifact_id}.json"
        if path.is_file():
            path.unlink()
        index = [e for e in self._load_index(project_id) if e.get("id") != artifact_id]
        self._save_index(project_id, index)
        return True

    def list(
        self,
        project_id: str,
        *,
        types: list[str] | None = None,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[ArtifactSummary]:
        entries = self._load_index(project_id)
        out: list[ArtifactSummary] = []
        type_set = set(types) if types else None
        for e in entries:
            et = e.get("type")
            if et == "MethodCard":
                continue  # 已下线类型：索引残留忽略
            if type_set and et not in type_set:
                continue
            if session_id and e.get("session_id") != session_id:
                continue
            out.append(ArtifactSummary.model_validate(e))
            if len(out) >= limit:
                break
        return out

    def latest_datapackets(self, project_id: str, *, session_id: str | None = None, limit: int = 5) -> list[DataPacket]:
        items = self.list(
            project_id,
            types=["DataPacket"],
            session_id=session_id,
            limit=limit,
        )
        result: list[DataPacket] = []
        for s in items:
            raw = self.get(project_id, "DataPacket", s.id)
            if raw:
                result.append(DataPacket.model_validate(raw))
        return result


_store: ArtifactStore | None = None


def get_artifact_store() -> ArtifactStore:
    global _store
    if _store is None:
        _store = ArtifactStore()
    return _store
