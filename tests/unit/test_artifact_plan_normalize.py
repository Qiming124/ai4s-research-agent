# ExperimentPlan 字段清洗（LLM 常输出 list/dict 混用）

from __future__ import annotations

from server.artifacts.extract import normalize_artifact_payload
from server.artifacts.store import get_artifact_store


def test_normalize_experiment_plan_coerces_llm_shapes():
    raw = {
        "id": "t1",
        "objectives": ["验证梯度为零", "Hessian 正定"],
        "variables": {"independent": "theta", "range": "[-2,2]"},
        "controls": {"tol": 1e-6, "flag": True},
        "success_criteria": {"grad_ok": True, "eig_pos": True},
        "record_fields": "min_eigen,min_loss",
        "revision_note": None,
        "status": "weird",
    }
    out = normalize_artifact_payload("ExperimentPlan", raw)
    assert isinstance(out["objectives"], str) and "梯度" in out["objectives"]
    assert isinstance(out["variables"], list) and len(out["variables"]) >= 1
    assert isinstance(out["controls"], list)
    assert isinstance(out["success_criteria"], list)
    assert isinstance(out["record_fields"], list)
    assert out["revision_note"] == ""
    assert out["status"] == "planned"


def test_store_saves_coerced_experiment_plan(tmp_path, monkeypatch):
    from server.artifacts import store as store_mod

    st = store_mod.ArtifactStore(root=tmp_path)
    monkeypatch.setattr(store_mod, "_store", st)
    # bypass singleton if any
    saved = st.save(
        "ExperimentPlan",
        {
            "project_id": "p1",
            "title": "coerce save",
            "objectives": ["a", "b"],
            "variables": {"x": 1},
            "revision_note": None,
        },
    )
    assert saved["objectives"]
    assert isinstance(saved["variables"], list)
    assert (tmp_path / "p1" / "artifacts" / "ExperimentPlan" / f"{saved['id']}.json").is_file()
