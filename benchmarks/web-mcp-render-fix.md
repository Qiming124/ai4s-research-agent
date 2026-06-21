# Web 前端 MCP 渲染修复验证

本次修复针对 MCP 调用时页面变白屏/渲染崩溃问题，采用多层防御兜底策略。

## 问题根因

1. **ToolTimeline 组件无错误边界**: MCP 流式过程中 `timeline` 对象可能因状态更新时序不一致而产生渲染异常，导致整个 React 树卸载
2. **MessageBubble 缺少逐条隔离**: 单条消息渲染崩溃会连锁影响整个消息列表
3. **SSE 管道缺少防御**: `applyStreamEvent` / `processStreamEvents` 对异常 JSON 或非字符串 content 没有保护

## 修复内容

| 文件 | 改动 |
|------|------|
| `web/src/components/ToolTimeline.tsx` | 添加 `ToolTimelineGuard` ErrorBoundary + 内层 try/catch；简化渲染，不依赖 `timeline-dot` CSS 类 |
| `web/src/components/MessageBubble.tsx` | 添加 `BubbleGuard` ErrorBoundary，逐条隔离；移除 Agent 标签（减少渲染树复杂度） |
| `web/src/hooks/useChatStream.ts` | `safeContent` 统一处理 tool 结果；`processStreamEvents` 每步 try/catch；`parseSseBuffer` 加固 |

## 自动化测试

```bash
cd /home/agent
source .venv/bin/activate
pytest tests/ -q                          # 84 passed
cd web && npm run build                    # build PASS
```

## 手动验证清单

### 1. 启动后端

```bash
cd /home/agent
source .venv/bin/activate
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 启动前端

```bash
cd /home/agent/web
npm run dev                                # http://localhost:5173
```

### 3. 基础对话

打开 http://localhost:5173 ，发送消息「你好」。

- [ ] 消息发送后立即显示用户气泡
- [ ] assistant 气泡出现，填写中显示闪烁光标
- [ ] 回答完成后光标消失，使用量显示

### 4. MCP 工具调用（核心验证）

确保 `.env` 中 `ENABLE_MCP=true`。

发送消息：「列出 data/mcp_files 目录文件」

- [ ] 消息气泡中出现「执行时间线」面板
- [ ] 面板列出 `filesystem__list_files` → 状态「完成」
- [ ] 最终回答在时间线下方正常展示
- [ ] **页面不会变白屏**
- [ ] 可继续发送后续消息

### 5. 多轮对话 + 多次 MCP

连续发送两条带 MCP 的消息（如「列出文件」「读取 mcp_test.txt」）。

- [ ] 每次 MCP 调用完成后页面保持稳定
- [ ] 不需要刷新即可看到所有工具调用结果
- [ ] 会话列表左侧同步更新

### 6. curl 快速冒烟

```bash
curl -s -N -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"读取 data/mcp_files 下任意文件","session_id":"smoke-fix","enable_tools":true}' \
  --max-time 60 | head -10
```

预期输出含 `tool_call_start`、`tool_call_result` 事件。

### 7. 异常情况宽容

在前端控制台（F12）中，即便出现红色错误日志，页面不应整体白屏。每条消息若渲染失败会显示「消息渲染出错（已跳过）」的红色提示条。

## 预期结果

| 检查项 | 预期 |
|--------|------|
| 普通对话 | 正常显示 |
| MCP 工具调用 | 时间线面板正常显示，页面不白屏 |
| 多次 MCP | 连续稳定 |
| 构建 | `npm run build` 通过 |
| 后端测试 | `pytest tests/ -q` 84 passed |

## Git 提交

```
63c9673 fix(web): 加固 SSE streaming 与工具时间线渲染，防止 MCP 调用时页面白屏
```

位于本地 `dev` 分支，未推送。
