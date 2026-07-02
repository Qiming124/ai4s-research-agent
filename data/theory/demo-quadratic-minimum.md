# v0.3 演示场景：二次损失的局部极小点

## 问题

证明损失函数 $L(\theta) = \|\theta\|^2$ 在 $\theta^* = 0$ 处为严格局部极小点。

## 启动配置

```env
ORCHESTRATION_BACKEND=langgraph
ENABLE_MCP=true
ENABLE_RAG=true
RAG_INDEX_MCP_FILES=true
MCP_ALLOWED_DIRS=./data/mcp_files:./data/theory
STRUCTURED_MEMORY_AGENTS=theory
```

## 请求

```bash
curl -N -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"证明 L(theta)=theta^2 在 theta=0 为严格局部极小","mode":"math","session_id":"demo-v03"}'
```

## 预期行为

1. 路由至 **theory** Agent（`mode=math`）
2. 输出分阶段：定义 → 引理/定理 → 证明 → 边界条件
3. SSE 事件含 `sympy__*` 工具调用或 `verification_result`
4. `GET /v1/memory/structured?session_id=demo-v03` 可见自动持久化的引理/定理

## SymPy 手动验证

```bash
# hessian_eigenvalues 对 x**2 应返回 local_minimum
uv run python -c "
import asyncio, json
from server.mcp.servers import sympy as s
async def main():
    r = await s.hessian_eigenvalues('x**2', 'x')
    print(json.loads(r))
asyncio.run(main())
"
```
