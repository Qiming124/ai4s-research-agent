# 代码注释规范

本项目文档与代码注释统一使用**中文**。

## Python

- 模块顶部：说明职责、架构位置、调试提示（见现有 `app/server/api/chat.py`）。
- 类：说明用途与主要字段。
- 公开函数/方法：使用 docstring，包含：
  - 功能说明
  - **参数**：名称与含义
  - **返回**：类型与含义
  - **异常**（如有）

示例：

```python
async def get_session(session_id: str) -> SessionResponse:
    """
    查询指定会话的完整历史消息。

    参数:
        session_id: 会话唯一标识

    返回:
        SessionResponse，含 session_id 与 messages 列表

    异常:
        HTTPException 404: 会话不存在
    """
```

私有方法（`_` 前缀）可用单行注释。

## TypeScript / React

- 导出函数、Hook、组件 Props：使用 JSDoc `/** ... */`。
- 说明参数、返回值、副作用。

## 文档

- 用户向文档放在 `doc/` 与根 `README.md`。
- MCP 专题：`doc/mcp-config.md`。
- 部署：`doc/DEPLOY.md`、`doc/docker.md`。
