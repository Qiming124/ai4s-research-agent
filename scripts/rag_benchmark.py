#!/usr/bin/env python3
"""
RAG 可量化基准测试：索引、检索 Hit@K、MRR、距离分布、延迟。

用法（项目根目录）:
  DEEPSEEK_API_KEY=sk-test python scripts/rag_benchmark.py
  DEEPSEEK_API_KEY=sk-test python scripts/rag_benchmark.py --provider sentence_transformers
  DEEPSEEK_API_KEY=sk-test python scripts/rag_benchmark.py --top-k 4 --cases tests/rag_benchmark_cases.json

通过标准见 cases JSON 内 thresholds，或下方报告中的 PASS/FAIL。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-key-for-rag-benchmark")

from server.config import get_settings
from server.memory.rag.store import RagStore


def load_cases(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def hit_at_k(retrieved_doc_ids: list[str], expected: list[str], k: int) -> float:
    if not expected:
        return 1.0 if not any(retrieved_doc_ids[:k]) else 0.0
    top = retrieved_doc_ids[:k]
    return 1.0 if any(e in top for e in expected) else 0.0


def reciprocal_rank(retrieved_doc_ids: list[str], expected: list[str]) -> float:
    if not expected:
        return 1.0
    for rank, doc_id in enumerate(retrieved_doc_ids, start=1):
        if doc_id in expected:
            return 1.0 / rank
    return 0.0


def run_benchmark(
    cases_path: Path,
    provider: str | None,
    top_k: int,
) -> dict:
    get_settings.cache_clear()
    cases = load_cases(cases_path)
    thresholds = cases.get("thresholds", {})

    with tempfile.TemporaryDirectory() as tmp:
        chroma_path = Path(tmp) / "chroma"
        cache_home = Path(tmp) / "cache"
        cache_home.mkdir(parents=True, exist_ok=True)
        os.environ["XDG_CACHE_HOME"] = str(cache_home)
        settings = get_settings()
        settings.enable_rag = True
        settings.rag_chroma_path = str(chroma_path)
        if provider:
            settings.rag_embedding_provider = provider

        store = RagStore(settings, embedding_provider=provider or settings.rag_embedding_provider)

        index_start = time.perf_counter()
        indexed: list[dict] = []
        for doc in cases["documents"]:
            record = store.add_document(
                doc["content"],
                title=doc.get("title"),
                doc_id=doc.get("doc_id"),
            )
            indexed.append(
                {
                    "doc_id": record.doc_id,
                    "chunk_count": record.chunk_count,
                    "title": record.title,
                }
            )
        index_latency_ms = (time.perf_counter() - index_start) * 1000

        positive_hits: list[float] = []
        negative_false_hits = 0
        mrr_scores: list[float] = []
        positive_distances: list[float] = []
        negative_distances: list[float] = []
        retrieve_latencies: list[float] = []
        query_details: list[dict] = []

        for q in cases["queries"]:
            q_start = time.perf_counter()
            snippets = store.retrieve(q["query"], top_k=top_k)
            q_latency_ms = (time.perf_counter() - q_start) * 1000
            retrieve_latencies.append(q_latency_ms)

            retrieved_ids = [s.doc_id for s in snippets]
            expected = q.get("expected_doc_ids", [])
            hit = hit_at_k(retrieved_ids, expected, top_k)
            rr = reciprocal_rank(retrieved_ids, expected)
            top_score = snippets[0].score if snippets else None

            if q.get("type") == "positive":
                positive_hits.append(hit)
                mrr_scores.append(rr)
                if snippets and snippets[0].score is not None:
                    positive_distances.append(snippets[0].score)
            elif q.get("type") == "negative":
                top_dist = snippets[0].score if snippets else None
                neg_min = thresholds.get("negative_top1_distance_min", 0.2)
                # 小语料库下仍会返回结果；用 top1 距离判断是否「误相关」
                if top_dist is not None and top_dist < neg_min:
                    negative_false_hits += 1
                if top_dist is not None:
                    negative_distances.append(top_dist)

            query_details.append(
                {
                    "id": q["id"],
                    "type": q.get("type"),
                    "hit@k": hit,
                    "mrr": rr,
                    "latency_ms": round(q_latency_ms, 2),
                    "top_doc_id": retrieved_ids[0] if retrieved_ids else None,
                    "top_distance": top_score,
                    "expected": expected,
                }
            )

        n_pos = len(positive_hits) or 1
        hit_at_k_mean = sum(positive_hits) / n_pos
        mrr_mean = sum(mrr_scores) / n_pos if mrr_scores else 0.0
        retrieve_latency_p95 = (
            sorted(retrieve_latencies)[int(0.95 * len(retrieve_latencies)) - 1]
            if retrieve_latencies
            else 0.0
        )

        total_chunks = sum(i["chunk_count"] for i in indexed)
        metrics = {
            "embedding_provider": provider or settings.rag_embedding_provider,
            "top_k": top_k,
            "documents_indexed": len(indexed),
            "total_chunks": total_chunks,
            "index_latency_ms": round(index_latency_ms, 2),
            "retrieve_latency_p95_ms": round(retrieve_latency_p95, 2),
            "hit_at_k": round(hit_at_k_mean, 4),
            "mrr": round(mrr_mean, 4),
            "positive_query_count": len(positive_hits),
            "negative_false_hits": negative_false_hits,
            "positive_top1_distance_mean": (
                round(sum(positive_distances) / len(positive_distances), 4)
                if positive_distances
                else None
            ),
            "negative_top1_distance_mean": (
                round(sum(negative_distances) / len(negative_distances), 4)
                if negative_distances
                else None
            ),
            "indexed": indexed,
            "queries": query_details,
        }

        checks = {
            "hit_at_k": hit_at_k_mean >= thresholds.get("hit_at_k_min", 0.75),
            "mrr": mrr_mean >= thresholds.get("mrr_min", 0.5),
            "total_chunks": total_chunks >= thresholds.get("index_chunk_count_min", 1),
            "index_latency_ms": index_latency_ms <= thresholds.get("index_latency_ms_max", 5000),
            "retrieve_latency_p95_ms": retrieve_latency_p95 <= thresholds.get(
                "retrieve_latency_ms_max", 2000
            ),
            "negative_false_hits": negative_false_hits <= thresholds.get(
                "negative_false_hit_max", 0
            ),
        }
        pos_max = thresholds.get("positive_top1_distance_max")
        if pos_max is not None and positive_distances:
            checks["positive_distance"] = (
                sum(positive_distances) / len(positive_distances) <= pos_max
            )
        metrics["checks"] = checks
        metrics["passed"] = all(checks.values())
        return metrics


def print_report(metrics: dict) -> None:
    print("=" * 60)
    print("RAG Benchmark Report")
    print("=" * 60)
    print(f"Provider:        {metrics['embedding_provider']}")
    print(f"Top-K:           {metrics['top_k']}")
    print(f"Docs indexed:    {metrics['documents_indexed']}")
    print(f"Total chunks:    {metrics['total_chunks']}")
    print(f"Index latency:   {metrics['index_latency_ms']} ms")
    print(f"Retrieve P95:    {metrics['retrieve_latency_p95_ms']} ms")
    print(f"Hit@{metrics['top_k']}:          {metrics['hit_at_k']:.2%}")
    print(f"MRR:             {metrics['mrr']:.4f}")
    print(f"Neg false hits:  {metrics['negative_false_hits']}")
    if metrics["positive_top1_distance_mean"] is not None:
        print(f"Pos distance μ:  {metrics['positive_top1_distance_mean']}")
    if metrics["negative_top1_distance_mean"] is not None:
        print(f"Neg distance μ:  {metrics['negative_top1_distance_mean']}")
    print("-" * 60)
    for q in metrics["queries"]:
        status = "OK" if q["hit@k"] >= 1.0 or q["type"] == "negative" else "MISS"
        print(
            f"  [{status}] {q['id']}: hit={q['hit@k']} mrr={q['mrr']:.3f} "
            f"lat={q['latency_ms']}ms top={q['top_doc_id']} dist={q['top_distance']}"
        )
    print("-" * 60)
    for name, ok in metrics["checks"].items():
        print(f"  {'PASS' if ok else 'FAIL'}: {name}")
    print("=" * 60)
    print("OVERALL:", "PASS" if metrics["passed"] else "FAIL")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG retrieval benchmark")
    parser.add_argument(
        "--cases",
        type=Path,
        default=ROOT / "tests" / "rag_benchmark_cases.json",
    )
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--json", action="store_true", help="仅输出 JSON")
    args = parser.parse_args()

    metrics = run_benchmark(args.cases, args.provider, args.top_k)
    if args.json:
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
    else:
        print_report(metrics)
    return 0 if metrics["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
