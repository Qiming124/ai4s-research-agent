# API 测试公共 fixture。

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-ci-only")
    from server.config import get_settings

    get_settings.cache_clear()
    from server.main import create_app

    return TestClient(create_app())


@pytest.fixture
def session_id():
    return "test-session-api-001"


@pytest.fixture
def project_id():
    return "default"
