# 下线：方法卡 / 工作区文件 API / 假设 DAG / 关系图谱

- **日期**：2026-07-22  
- **原因**：方法卡干扰短问答且用途不清；工作区文件 API 体验弱；假设依赖图与关系图谱展示效果差，验收中评为弱价值。

## 已去除

| 表面 | 处理 |
|------|------|
| MethodCard 模型 / 围栏解析 / lit_to_theory 强制附加 | 删除类型与强制；literature 仅 Markdown 提炼 |
| UI「方法卡」面板 | 删除 |
| `GET/PUT /v1/theory/workspace*` | 路由删除（磁盘种子与 prompt 注入**保留**） |
| UI「工作区文件」 | 删除 |
| `GET /v1/theory/assumption-dag*` | 路由删除 |
| UI「假设依赖图」 | 删除 |
| `GET /v1/memory/structured/graph` | 路由删除 |
| UI「关系图谱」 | 删除 |

## 仍保留

- `/v1/artifacts`（DerivationTrace / ExperimentPlan / DataPacket / NextStepMemo）
- 定理库结构化记忆 CRUD、边创建 API
- `theory_workspace.py` 对 theory/review 的符号与假设注入（无 HTTP）
- `lit_to_theory` 场景：文献 Markdown → 理论 + DerivationTrace（无 MethodCard）

## 验收影响

原 T4/T5/T6、L6、工作区探测改为「已下线」。
