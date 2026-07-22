# Artifact 围栏解析与场景路由

from __future__ import annotations

from server.artifacts.extract import extract_artifacts_from_text
from server.config import Settings
from server.graph.scenes.workflow import match_scene


def test_extract_method_card_ignored():
    """MethodCard 已下线：围栏应被忽略。"""
    text = """
一些说明

```artifact:MethodCard
{"title": "Keskar sharpness", "problem_setup": "min L", "loss_form": "CE", "key_assumptions": ["A1"]}
```
"""
    found = extract_artifacts_from_text(text)
    assert found == []


def test_extract_derivation_trace():
    text = """
```artifact:DerivationTrace
{"title": "PL 短证", "steps": [{"title": "代入", "body": "grad=0", "status": "proven"}]}
```
"""
    found = extract_artifacts_from_text(text)
    assert len(found) == 1
    assert found[0][0] == "DerivationTrace"
    assert found[0][1]["title"] == "PL 短证"


def test_extract_invalid_json_skipped():
    text = "```artifact:ExperimentPlan\n{not json\n```"
    assert extract_artifacts_from_text(text) == []


def test_match_scene_lit_method():
    s = Settings(deepseek_api_key="sk-test-key-not-placeholder", research_pipeline_mode="auto")
    m = match_scene("/method 提炼这篇论文公式", agent="literature", mode="chat", settings=s)
    assert m is not None
    assert m.scene_id == "lit_to_theory"


def test_match_scene_experiment_plan():
    s = Settings(deepseek_api_key="sk-test-key-not-placeholder", research_pipeline_mode="auto")
    m = match_scene(
        "请设计一组验证局部极小的实验方案与对照表",
        agent="experiment",
        mode="chat",
        settings=s,
        project_id="scene-test-no-data",
    )
    assert m is not None
    assert m.scene_id == "experiment_plan"


def test_match_scene_off_in_single_mode():
    s = Settings(deepseek_api_key="sk-test-key-not-placeholder", research_pipeline_mode="single")
    m = match_scene("/method 公式", agent="literature", mode="chat", settings=s)
    assert m is None
