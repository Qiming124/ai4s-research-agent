"""RAG 检索基准：可量化 Hit@K、MRR、延迟（使用隔离临时 Chroma + 当前 embedding provider）。"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from rag_benchmark import run_benchmark  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "rag_benchmark_cases.json"


@pytest.mark.parametrize("provider", ["test", "chroma_default"])
def test_rag_benchmark_metrics(provider: str) -> None:
    """test provider 验管道；chroma_default 验语义检索（阈值略宽松）。"""
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    thresholds = cases["thresholds"]

    metrics = run_benchmark(CASES_PATH, provider=provider, top_k=4)

    assert metrics["total_chunks"] >= thresholds["index_chunk_count_min"]
    assert metrics["index_latency_ms"] <= thresholds["index_latency_ms_max"]

    if provider == "test":
        # 哈希伪向量无语义，只要求管道可跑、负例不误命中过多
        assert metrics["negative_false_hits"] <= thresholds["negative_false_hit_max"]
    else:
        assert metrics["hit_at_k"] >= thresholds["hit_at_k_min"]
        assert metrics["mrr"] >= thresholds["mrr_min"]
        assert metrics["retrieve_latency_p95_ms"] <= thresholds["retrieve_latency_ms_max"]
