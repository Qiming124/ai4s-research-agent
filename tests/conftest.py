"""pytest 配置：注入测试用 API Key 并清理 Settings 缓存。"""

import os

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-key-for-pytest-only")

from server.config import get_settings

get_settings.cache_clear()
