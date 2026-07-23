# 实验数据多格式解析

from __future__ import annotations

import json

from openpyxl import Workbook

from server.experiments.data_import import parse_csv_bytes, parse_excel_bytes, parse_experiment_file, parse_json_bytes


def test_parse_json_metrics_object():
    raw = json.dumps({"metrics": {"min_loss": 0.1}, "summary": {"ok": True}}).encode()
    p = parse_json_bytes(raw)
    assert p.metrics["min_loss"] == 0.1
    assert p.summary["ok"] is True


def test_parse_csv_key_value():
    raw = b"min_eigen,0.01\nmin_loss,0.0\n"
    p = parse_csv_bytes(raw)
    assert p.metrics["min_eigen"] == 0.01
    assert p.metrics["min_loss"] == 0.0


def test_parse_csv_table_last_row_metrics():
    raw = b"lr,loss\n0.1,1.0\n0.01,0.2\n"
    p = parse_csv_bytes(raw)
    assert p.metrics["lr"] == 0.01
    assert p.metrics["loss"] == 0.2
    assert p.summary["row_count"] == 2


def test_parse_excel_key_value(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["metric", "value"])
    ws.append(["min_eigen", 0.02])
    ws.append(["passed", 1])
    buf_path = tmp_path / "t.xlsx"
    wb.save(buf_path)
    data = buf_path.read_bytes()
    p = parse_excel_bytes(data)
    assert p.format == "xlsx"
    assert p.summary["shape"] == "key_value"
    assert p.metrics["min_eigen"] == 0.02
    assert p.metrics["passed"] == 1


def test_parse_experiment_file_dispatch():
    p = parse_experiment_file("a.csv", b"a,1\nb,2\n")
    assert p.format == "csv"
    assert p.metrics["a"] == 1


def test_parse_wide_labeled_table_readable_metrics():
    """宽表：首列指标名 + 多列模型取值 → 可读 metrics，而非仅 col_*。"""
    raw = b",Adam,SGD\ntrain_loss,0.12,0.34\ntest_acc,0.91,0.88\n"
    p = parse_csv_bytes(raw)
    assert p.summary.get("shape") == "wide_labeled"
    assert "Adam__train_loss" in p.metrics or any("train_loss" in k for k in p.metrics)
    assert p.summary.get("readable")
    assert p.summary.get("notable_cells")


def test_parse_placeholder_header_has_notable_cells():
    raw = b",,\nfoo,1,2\nbar,3,4\n"
    p = parse_csv_bytes(raw)
    assert p.summary.get("notable_cells")
    assert "readable" in p.summary
