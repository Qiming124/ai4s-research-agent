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


def test_normalize_derivation_trace_from_lemmas_theorem():
    """模型常用 lemmas/theorem 结构 → 应收成非空 steps + title。"""
    raw = {
        "id": "d1",
        "problem": "quadratic_loss_strict_local_minimum",
        "definitions": {"L": "0.5 * theta^T A theta", "hessian": "A"},
        "assumptions": ["A symmetric", "A positive definite"],
        "lemmas": [
            {
                "id": "lemma_1",
                "claim": "gradient = A*theta",
                "proof": "component-wise differentiation",
            }
        ],
        "theorem": {
            "statement": "theta*=0 is strict local minimum",
            "proof": "Rayleigh quotient",
            "key_inequality": "theta^T A theta >= lambda_min ||theta||^2",
        },
        "verification": {"method": "sympy", "result": "local_minimum"},
    }
    out = normalize_artifact_payload("DerivationTrace", raw)
    assert out["title"]
    assert "quadratic" in out["title"] or "minimum" in out["title"].lower()
    assert isinstance(out["steps"], list) and len(out["steps"]) >= 3
    titles = " ".join(s["title"] for s in out["steps"])
    assert "假设" in titles or "lemma" in titles.lower() or "gradient" in titles.lower()
    assert out.get("claim_yaml")
    assert "lemmas" not in out
    assert "theorem" not in out


def test_store_saves_coerced_derivation_trace(tmp_path, monkeypatch):
    from server.artifacts import store as store_mod

    st = store_mod.ArtifactStore(root=tmp_path)
    monkeypatch.setattr(store_mod, "_store", st)
    saved = st.save(
        "DerivationTrace",
        {
            "project_id": "p1",
            "problem": "demo-problem",
            "lemmas": [{"claim": "c1", "proof": "p1"}],
            "theorem": {"statement": "结论成立", "proof": "略"},
        },
    )
    assert saved["title"]
    assert len(saved["steps"]) >= 2
    assert (tmp_path / "p1" / "artifacts" / "DerivationTrace" / f"{saved['id']}.json").is_file()


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
