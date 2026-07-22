# =============================================================================
# 实验数据多格式解析：JSON / CSV / TSV / Excel → summary + metrics。
# =============================================================================

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedExperimentData:
    """统一解析结果，供入库与 DataPacket 使用。"""

    summary: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    format: str = "unknown"
    preview_rows: list[dict[str, Any]] = field(default_factory=list)


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value.strip())
            return True
        except ValueError:
            return False
    return False


def _to_number(value: Any) -> int | float | Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        s = value.strip()
        try:
            if re.fullmatch(r"-?\d+", s):
                return int(s)
            return float(s)
        except ValueError:
            return value
    return value


def _rows_to_parsed(rows: list[list[Any]], *, fmt: str) -> ParsedExperimentData:
    """
    表格约定：
    1) 两列 key-value → 全部进 metrics
    2) 首行表头 + 多行数据 → 末行数值列进 metrics；summary 含列名/行数；preview 最多 20 行
    """
    cleaned: list[list[Any]] = []
    for row in rows:
        if row is None:
            continue
        cells = [("" if c is None else c) for c in row]
        if all(str(c).strip() == "" for c in cells):
            continue
        cleaned.append(cells)

    if not cleaned:
        return ParsedExperimentData(
            summary={"note": "empty_table"},
            metrics={},
            format=fmt,
        )

    # 两列：优先识别「表头+数据」；否则视为键值对（可带 metric/value 表头）
    if all(len(r) >= 2 for r in cleaned) and max(len(r) for r in cleaned) <= 2:
        first0, first1 = cleaned[0][0], cleaned[0][1]
        headerish = len(cleaned) >= 2 and not _is_number(first0) and not _is_number(first1)
        # 首列后续为数值 → 普通两列表格（如 lr,loss）
        if headerish and any(_is_number(r[0]) for r in cleaned[1:]):
            pass  # fall through to table path
        else:
            kv_rows = cleaned[1:] if headerish else cleaned
            metrics: dict[str, Any] = {}
            for r in kv_rows:
                key = str(r[0]).strip()
                if not key:
                    continue
                metrics[key] = _to_number(r[1])
            return ParsedExperimentData(
                summary={"shape": "key_value", "row_count": len(metrics)},
                metrics=metrics,
                format=fmt,
                preview_rows=[{"key": k, "value": v} for k, v in list(metrics.items())[:20]],
            )

    header = [str(c).strip() or f"col_{i}" for i, c in enumerate(cleaned[0])]
    data_rows = cleaned[1:] if len(cleaned) > 1 else []
    dict_rows: list[dict[str, Any]] = []
    for r in data_rows:
        item: dict[str, Any] = {}
        for i, name in enumerate(header):
            raw = r[i] if i < len(r) else ""
            item[name] = _to_number(raw) if _is_number(raw) else (str(raw).strip() if raw is not None else "")
        dict_rows.append(item)

    metrics = {}
    if dict_rows:
        last = dict_rows[-1]
        for k, v in last.items():
            if _is_number(v) or isinstance(v, (int, float)):
                metrics[k] = _to_number(v)

    summary = {
        "shape": "table",
        "columns": header,
        "row_count": len(dict_rows),
    }
    return ParsedExperimentData(
        summary=summary,
        metrics=metrics,
        format=fmt,
        preview_rows=dict_rows[:20],
    )


def parse_json_bytes(data: bytes) -> ParsedExperimentData:
    obj = json.loads(data.decode("utf-8-sig"))
    if isinstance(obj, list):
        # JSON 数组：当作记录表
        if obj and isinstance(obj[0], dict):
            header = list(obj[0].keys())
            rows = [header] + [[rec.get(h, "") for h in header] for rec in obj if isinstance(rec, dict)]
            parsed = _rows_to_parsed(rows, fmt="json")
            return parsed
        raise ValueError("JSON 数组须为对象列表")
    if not isinstance(obj, dict):
        raise ValueError("JSON 须为对象或对象数组")
    summary = obj.get("summary") if isinstance(obj.get("summary"), dict) else {}
    metrics = obj.get("metrics") if isinstance(obj.get("metrics"), dict) else {}
    if not summary and not metrics:
        # 整个对象当 metrics（数值字段）+ 其余进 summary
        metrics = {k: v for k, v in obj.items() if _is_number(v) or isinstance(v, (int, float))}
        summary = {k: v for k, v in obj.items() if k not in metrics}
        if not metrics and obj:
            metrics = obj
            summary = {"shape": "flat_object"}
    return ParsedExperimentData(summary=dict(summary), metrics=dict(metrics), format="json")


def parse_csv_bytes(data: bytes, *, delimiter: str = ",") -> ParsedExperimentData:
    text = data.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [list(r) for r in reader]
    fmt = "tsv" if delimiter == "\t" else "csv"
    parsed = _rows_to_parsed(rows, fmt=fmt)
    if parsed.preview_rows:
        parsed.summary = {**parsed.summary, "preview": parsed.preview_rows}
    return parsed


def parse_excel_bytes(data: bytes) -> ParsedExperimentData:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise ValueError("服务端未安装 openpyxl，无法解析 Excel。请 pip install openpyxl") from exc

    wb = load_workbook(filename=io.BytesIO(data), read_only=True, data_only=True)
    try:
        ws = wb.active
        rows: list[list[Any]] = []
        for row in ws.iter_rows(values_only=True):
            rows.append(list(row))
    finally:
        wb.close()
    parsed = _rows_to_parsed(rows, fmt="xlsx")
    if parsed.preview_rows:
        parsed.summary = {**parsed.summary, "preview": parsed.preview_rows}
    return parsed


def parse_experiment_file(filename: str, data: bytes) -> ParsedExperimentData:
    """按扩展名分发解析。"""
    name = (filename or "").lower().strip()
    if name.endswith(".json"):
        return parse_json_bytes(data)
    if name.endswith(".csv"):
        return parse_csv_bytes(data, delimiter=",")
    if name.endswith(".tsv"):
        return parse_csv_bytes(data, delimiter="\t")
    if name.endswith(".xlsx") or name.endswith(".xlsm"):
        return parse_excel_bytes(data)
    if name.endswith(".xls"):
        raise ValueError("暂不支持旧版 .xls，请另存为 .xlsx 或导出 CSV")
    # 尝试按内容嗅探
    head = data[:64].lstrip()
    if head.startswith(b"{") or head.startswith(b"["):
        return parse_json_bytes(data)
    raise ValueError(f"不支持的文件格式: {filename}（支持 .json / .csv / .tsv / .xlsx）")
