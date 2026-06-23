"""
server.mcp.servers 包：自研 MCP Server（python stdio 子进程）。

每个 Server 为独立模块，可单独作为 MCP Server 进程运行：
    python -m server.mcp.servers.arxiv
    python -m server.mcp.servers.web_search
    python -m server.mcp.servers.filesystem

MCPClient 通过 mcp_servers.json 配置启动这些 Server 为 stdio 子进程。
"""
