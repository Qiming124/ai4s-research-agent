# MCP 配置指南

本文说明如何在 AI4S Agent 服务端配置、启用与扩展 MCP（Model Context Protocol）工具。

---

## 概述

- **配置文件**：项目根目录 [`mcp_servers.json`](../conf/mcp_servers.json)
- **环境变量**：`conf/.env` 中的 `ENABLE_MCP` 等（见 [环境变量](#环境变量)）
- **架构**：启动时 `MCPClient` 按配置逐个拉起 stdio MCP Server，聚合工具后供 `GeneralAgent` 通过 function calling 调用
- **工具命名**：`{server名}__{工具名}`，例如 `arxiv__search_papers`

Web 端可在 **设置 → MCP 工具** 查看 Server 连接状态与工具列表；是否启用工具由 `ENABLE_MCP` 或侧边栏「启用 MCP 工具」控制。

---

## 快速启用

1. 复制并编辑 `conf/.env`：

```env
ENABLE_MCP=true
MCP_CONFIG_PATH=./conf/mcp_servers.json
MCP_ALLOWED_DIRS=./data/mcp_files
MCP_MAX_TOOL_ROUNDS=5
```

2. 确认 [`mcp_servers.json`](../conf/mcp_servers.json) 中需要的 Server 为 `"enabled": true`

3. **重启 uvicorn**（MCP 在进程启动时连接，修改 json 后需重启）

4. 启动日志应出现类似：

```
MCP: 已启用 (./conf/mcp_servers.json)
MCP Client 已连接 3 个 Server，共 6 个工具
```

5. 验证：`curl http://127.0.0.1:8000/v1/mcp/status`

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ENABLE_MCP` | `false` | 是否启用 MCP 工具层 |
| `MCP_CONFIG_PATH` | `./conf/mcp_servers.json` | MCP Server 配置文件路径 |
| `MCP_ALLOWED_DIRS` | `./data/mcp_files` | filesystem MCP 允许访问的目录，多个路径用 `:` 分隔 |
| `MCP_MAX_TOOL_ROUNDS` | `5` | 单轮对话中 LLM 工具调用循环的上限 |

`ChatRequest.enable_tools` 可在单次请求中覆盖全局开关（Web 侧边栏关闭「MCP：服务端默认」后生效）。

---

## 配置文件格式

[`mcp_servers.json`](../conf/mcp_servers.json) 为 JSON 对象，**键名为 Server 标识**（小写字母、数字、下划线），值为：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `command` | string | 是 | 启动命令，如 `python`、`npx` |
| `args` | string[] | 否 | 命令参数 |
| `env` | object | 否 | 子进程环境变量；值支持 `${VAR}` 引用主机环境 |
| `enabled` | boolean | 否 | 默认 `true`；`false` 时跳过连接 |

### 示例

```json
{
  "web_search": {
    "command": "python",
    "args": ["-m", "server.mcp.servers.web_search"],
    "enabled": true
  },
  "my_tool": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-xxx"],
    "env": {
      "API_KEY": "${MY_API_KEY}"
    },
    "enabled": true
  }
}
```

说明：

- 配置里写 `"command": "python"` 时，运行时自动替换为当前 venv 的 Python 解释器
- `${MCP_ALLOWED_DIRS}` 在加载时从环境变量展开；未设置时使用 `.env` 中的默认值

---

## 内置 MCP Server

| Server | 模块 | 工具（注册名） | 说明 |
|--------|------|----------------|------|
| `web_search` | `server.mcp.servers.web_search` | `web_search__search` | DuckDuckGo 网页搜索，无需 API Key |
| `arxiv` | `server.mcp.servers.arxiv` | `arxiv__search_papers`、`arxiv__get_paper` | arXiv 论文搜索与详情 |
| `filesystem` | `server.mcp.servers.filesystem` | `filesystem__read_file`、`filesystem__write_file`、`filesystem__list_files` | 受限目录内文件读写 |
| `sympy` | `server.mcp.servers.sympy` | `sympy__simplify_expression`、`sympy__differentiate`、`sympy__hessian_eigenvalues`、`sympy__taylor_expand` 等 | 符号计算 |
| `rag` | `server.mcp.servers.rag` | `rag__retrieve` | L3 向量库按需检索 |

实现代码位于 [`app/server/mcp/servers/`](../app/server/mcp/servers/)。

### 单独禁用某个 Server

在 `mcp_servers.json` 中将对应项设为 `"enabled": false`，重启服务即可。

---

## 添加新的 MCP Server

### 方式一：自研 Python Server（推荐）

1. 在 `app/server/mcp/servers/` 下新建模块，使用 FastMCP 声明工具：

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my_server")

@mcp.tool()
def hello(name: str) -> str:
    """示例工具。"""
    return f"Hello, {name}"

def main() -> None:
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
```

2. 在 `mcp_servers.json` 增加条目：

```json
"my_server": {
  "command": "python",
  "args": ["-m", "server.mcp.servers.my_server"],
  "enabled": true
}
```

3. 重启 uvicorn，在 Web 设置或 `GET /v1/mcp/status` 中确认工具已注册。

### 方式二：接入第三方 MCP Server

在 json 中配置第三方包的启动命令，例如：

```json
"tavily": {
  "command": "npx",
  "args": ["-y", "@anthropic/mcp-server-tavily"],
  "env": {
    "TAVILY_API_KEY": "${TAVILY_API_KEY}"
  },
  "enabled": true
}
```

在 `.env` 中配置对应密钥。接入前请确认命令来源可信，避免 arbitrary command 风险。

---

## 调用链路

```
用户消息 → GeneralAgent
  → MCPClient.get_openai_tools()  # 工具 schema
  → DeepSeek function calling
  → MCPClient.call_tool(qualified_name, args)
  → stdio MCP Server 子进程
  → SSE：tool_call_start / tool_call_result / content
```

相关代码：

- [`app/server/mcp/client.py`](../app/server/mcp/client.py) — 连接与调用
- [`app/server/agents/base.py`](../app/server/agents/base.py) — 工具循环
- [`app/server/api/mcp.py`](../app/server/api/mcp.py) — `GET /v1/mcp/status`

---

## 测试

```bash
# MCP Client 与内置 Server 集成
pytest tests/test_mcp.py -v

# MCP 状态 API
pytest tests/test_api.py::test_mcp_status_disabled -v
pytest tests/test_api.py::test_mcp_status_enabled -v
```

本地手动验证单个 Server（不经过 Agent）：

```bash
python -m server.mcp.servers.filesystem  # stdio 模式，需 MCP 客户端配合
```

---

## 常见问题

| 现象 | 处理 |
|------|------|
| 启动日志 `MCP: 未启用` | `.env` 中设置 `ENABLE_MCP=true` 并重启 |
| 侧边栏工具列表为空 | 确认 `ENABLE_MCP=true`；点击「刷新」；检查启动日志是否有连接错误 |
| 修改 json 不生效 | 必须重启 uvicorn（当前无热重载 API） |
| `filesystem` 读写失败 | 路径须在 `MCP_ALLOWED_DIRS` 内；目录需存在或可创建 |
| `web_search` / `arxiv` 失败 | 检查服务器出站网络；arxiv 需能访问 `export.arxiv.org`；web_search 依次尝试 DuckDuckGo 与 Wikipedia，部分地区需代理 |
| 工具从不被调用 | 问题需明确需要外部信息；或侧边栏启用 MCP；模型可能直接回答 |

---

## 团队部署说明

当前 MCP 为**进程级共享池**：所有用户共用同一份 `mcp_servers.json` 与 `MCP_ALLOWED_DIRS`，无 per-user 隔离。小团队内网部署通常足够；多租户 SaaS 需另行设计认证、沙箱与 per-user 配置（不在 Phase 2B 范围内）。

---

## 后续规划（未实现）

- SymPy 符号计算 MCP
- Tavily 等商业搜索 API
- `rag_retrieve`（Phase 3 RAG）
- MCP 配置热重载（无需重启）
