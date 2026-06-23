"""意图路由规则测试。"""

from server.graph.router import classify_intent


def test_math_mode_routes_to_theory():
    agent, reason = classify_intent("hello", mode="math")
    assert agent == "theory"
    assert reason == "mode=math"


def test_literature_keyword():
    agent, reason = classify_intent("请检索 arxiv 上关于 loss landscape 的论文")
    assert agent == "literature"
    assert reason == "keyword:literature"


def test_experiment_keyword():
    agent, reason = classify_intent("分析训练曲线和实验日志中的 loss")
    assert agent == "experiment"
    assert reason == "keyword:experiment"


def test_theory_keyword():
    agent, reason = classify_intent("请证明该损失函数的收敛性")
    assert agent == "theory"
    assert reason == "keyword:theory"


def test_default_general():
    agent, reason = classify_intent("今天天气怎么样")
    assert agent == "general"
    assert reason == "default"
