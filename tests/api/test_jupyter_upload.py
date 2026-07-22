# Jupyter / 实验文件上传 API

from __future__ import annotations

import io

from openpyxl import Workbook
from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


def test_upload_file_csv():
    raw = b"metric,value\nmin_eigen,0.05\nmin_loss,0.0\n"
    r = client.post(
        "/v1/jupyter/upload-file",
        files={"file": ("m.csv", raw, "text/csv")},
        data={"name": "csv_demo", "project_id": "default"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "indexed"
    assert body["run_id"]


def test_upload_file_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.append(["lr", "loss"])
    ws.append([0.1, 1.0])
    ws.append([0.01, 0.2])
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post(
        "/v1/jupyter/upload-file",
        files={
            "file": (
                "t.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"name": "xlsx_demo", "project_id": "default"},
    )
    assert r.status_code == 200
    assert r.json()["run_id"]


def test_upload_file_rejects_empty():
    r = client.post(
        "/v1/jupyter/upload-file",
        files={"file": ("empty.csv", b"", "text/csv")},
        data={"name": "empty"},
    )
    assert r.status_code == 400
