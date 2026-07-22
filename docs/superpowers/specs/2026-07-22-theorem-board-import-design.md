# 理论看板可编辑 + PDF 导入 + 实验计划/读数建议 CRUD（方案 2）

- **日期**：2026-07-22  
- **状态**：已实施  
- **范围**：  
  1. L4 定理库 CRUD、Markdown 批量导入、PDF→候选→确认入库  
  2. **实验计划（ExperimentPlan）CRUD**  
  3. **读数建议（NextStepMemo）CRUD**（同实验计划面板，提高可操作性）  
- **不改**：Agent 自动抽取/围栏产出链路（保留）、假设 DAG 自动重建、OCR、symbols.md 自动改写、DataPacket 提交流程（已有实验日志面板）

---

## 1. 背景与目标

### 现状

| 能力 | 现状 |
|------|------|
| 定理库来源 | 主要靠 Theory Agent 输出中 `## 引理/定理` 自动抽取 |
| 前端定理库 | `TheoremLibraryPanel` / `TheoremDetailDrawer` **只读** |
| 后端 L4 | 仅有 `POST /v1/memory/structured` 创建；**无** PATCH/DELETE |
| PDF | `POST /v1/documents/upload` 只进 **RAG**，不进 L4 看板 |
| 实验计划 / 读数建议 | Agent 围栏产出；API 仅 list/get/create；前端只读；**无** PATCH/DELETE |

用户认为 AI 自动写入的理论看板质量不足，需要：**自己导入/修改定理**、**PDF 一键导入**；并要求 **实验计划与读数建议均可 CRUD**，提高可操作性。

### 目标（一句话）

用户能在理论 Tab 管理定理看板（含 PDF 候选确认入库）；在实验相关面板 **手工新建/编辑/删除** 实验计划与读数建议。

### 成功标准

**定理库**

1. 可在当前会话新建、编辑、删除定理/引理/笔记等条目。  
2. 可贴 Markdown（含 `## 定理` 标题）批量导入。  
3. 上传 PDF 后出现候选列表；用户勾选后写入看板；条目带 `source` 元数据。  
4. 可选：同一文件仍可同时写入 RAG（默认开启，可取消）。  
5. AI 自动抽取路径仍可用，互不替代。

**实验计划 / 读数建议**

6. 可新建、编辑、删除 ExperimentPlan（含 status 等字段）。  
7. 可新建、编辑、删除 NextStepMemo（verdict、missing_data、next_experiments、notes 等）。  
8. Agent 对话产出的计划/建议仍追加到历史，与手工条目共存。  
9. DataPacket 仍走现有实验日志上传，第一期不改造其 CRUD UI。

---

## 2. 用户流程（定理库）

实验计划流程见 **§6**。

### 2.1 手工管理

```
理论 Tab → 定理库
  → [新建] 填 kind / 标题 / 正文 → 保存
  → 点击条目 → 抽屉内 [编辑] / [删除]
```

### 2.2 Markdown 导入

```
[从 Markdown 导入] → 粘贴文本 → 预览解析出的条目 → 勾选 → 写入
```

复用现有 `extract_structured_entries()` 规则；导入条目 `metadata.source = "markdown_import"`。

### 2.3 PDF 一键导入（核心）

```
[从 PDF 导入]
  → 选择文件（.pdf；第一期顺带支持已有文本抽取的 .md/.txt/.docx）
  → 服务端抽文本（复用 pdf_ingest.extract_text_from_pdf）
  → LLM 抽取「定理/引理/定义/关键公式」候选 JSON
  → 前端展示候选表（可改标题/正文后再勾选）
  → [确认入库] → 批量 POST 到 L4
  → （可选勾选）同时走 documents/upload 进 RAG
```

候选阶段**不写库**；只有确认才写入。

---

## 3. 数据与元数据约定

### 3.1 条目 kind（沿用现有）

`theorem` | `hypothesis` | `conclusion` | `citation` | `note`

PDF/Markdown 抽取映射建议：

| 抽取标签 | kind |
|----------|------|
| 定理 / 引理 / 推论 / Theorem / Lemma / Corollary | `theorem` |
| 假设 / Assumption | `hypothesis` |
| 定义 / 公式摘录 / 其它 | `note` |

### 3.2 metadata 扩展（写入时）

```json
{
  "source": "manual" | "markdown_import" | "pdf_import" | "ai_extract",
  "status": "draft",
  "import_filename": "paper.pdf",
  "import_page": 3,
  "symbols": [],
  "depends_on": []
}
```

- `ai_extract`：现有 Agent 抽取路径继续写入时补上（若尚未有则兼容缺省）。  
- 编辑保存不强制改 `source`；可追加 `updated_at` / `edited_by: "user"`（可选）。

### 3.3 版本

编辑成功后：若已有 `POST .../versions` 能力，**建议**在更新前自动快照一版（失败则仅记日志，不阻断编辑）。第一期也可只做原地更新、版本手动触发，文档验收以「编辑成功」为准。

---

## 4. API 设计

### 4.1 补全 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| 已有 POST | `/v1/memory/structured` | 新建（前端新建/批量确认复用） |
| **新增 PATCH** | `/v1/memory/structured/{entry_id}` | 更新 title / body / kind / metadata（部分字段） |
| **新增 DELETE** | `/v1/memory/structured/{entry_id}` | 删除条目；级联删除相关 `memory_edges` |

请求体（PATCH）：

```json
{
  "kind": "theorem",
  "title": "...",
  "body": "...",
  "metadata": { }
}
```

字段均可选；至少提供一个。

Store 层新增：`get_entry`、`update_entry`、`delete_entry`（删边再删行）。

### 4.2 Markdown 预览（可选独立接口）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/memory/structured/preview-markdown` | body: `{ "content": "..." }` → `{ "candidates": [...] }` |

也可纯前端调同一正则逻辑的镜像；为与 PDF 流程一致，**推荐后端统一预览**。

### 4.3 PDF / 文档 → 候选

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/memory/structured/import-preview` | `multipart/form-data`: `file` + 可选 `session_id` |

响应：

```json
{
  "filename": "paper.pdf",
  "text_chars": 12000,
  "truncated": false,
  "candidates": [
    {
      "kind": "theorem",
      "title": "Lemma 1: …",
      "body": "…（Markdown，公式用 $...$）",
      "page": 3,
      "confidence": 0.7,
      "selected_default": true
    }
  ],
  "warnings": []
}
```

确认入库：前端对勾选项循环 `POST /v1/memory/structured`（或新增批量接口，见下）。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST（可选） | `/v1/memory/structured/bulk` | `{ "session_id", "entries": [...] }` 事务批量写入 |

第一期可用循环 POST；条目 > 20 时再上 bulk。

### 4.4 抽取实现要点

1. **文本**：复用 `extract_text_from_pdf`；docx/md 复用 documents 已有 ingest。  
2. **长度策略**：**不为省 token 截断**。将可抽取的全文（或尽量完整的分页文本）交给 LLM；用户明确表示不关心 token 开销。仅在基础设施硬限制（请求体/模型上下文硬顶）时才截断，并必须 `truncated: true` + 明确警告。  
3. **LLM**：专用 system prompt，强制输出 JSON 数组；禁止编造原文中不存在的定理；鼓励覆盖文中主要定理/引理/定义。  
4. **失败**：无文本（扫描件）→ 400 + 明确提示「需可选文字 PDF，暂不支持 OCR」。  
5. **候选条数**：不设为省成本的硬上限；若单次结果过多，前端用分页/折叠展示，仍允许全选入库。

### 4.5 与 RAG 的关系

- 导入预览**默认不写 RAG**。  
- 确认入库 UI 提供勾选「同时加入文献库 (RAG)」：调用现有 `/v1/documents/upload`。  
- 两路独立：取消 RAG 不影响 L4；L4 失败不回滚已成功的 RAG（提示即可）。

---

## 5. 前端设计

### 5.1 `TheoremLibraryPanel`

- 工具栏增加：`新建` | `Markdown 导入` | `PDF 导入` | `刷新`  
- 空态文案改为：可手工新建 / 导入，不只依赖 Math/Theory Agent。

### 5.2 `TheoremDetailDrawer`

- `编辑`：标题、kind、正文（textarea，预览可用现有 MarkdownContent）  
- `删除`：确认对话框  
- 展示 `metadata.source` 小标签（手工 / PDF / AI）

### 5.3 导入向导（模态）

共用组件 `TheoremImportModal`：

1. 步骤 A：选文件或贴 Markdown  
2. 步骤 B：候选列表（checkbox、可内联改 title/body）  
3. 步骤 C：确认结果（成功条数 / 失败原因）

### 5.4 Hook

扩展 `useStructuredMemory`：`createEntry` / `updateEntry` / `deleteEntry` / `previewImport` / `confirmImport`。

---

## 6. 实验计划与读数建议 CRUD

### 6.1 现状与落点

- 模型：`ExperimentPlan`、`NextStepMemo`（`shared/artifact_models.py`）。  
- 存储：`ArtifactStore`；已有 `save` / `get` / `list`，**缺 update/delete**。  
- API：`POST /v1/artifacts` 可建；**缺 PATCH/DELETE**。  
- UI：`ArtifactsPanel mode="experiment-plans"` 只读展示两类工件。

### 6.2 用户流程

```
实验计划面板
  → [新建计划] / [新建读数建议]
  → 展开条目 → [编辑] / [删除]（二次确认）
  → （计划可选）[另存为修订]：parent_plan_id=旧 id
```

### 6.3 API

| 方法 | 路径 | 说明 |
|------|------|------|
| 已有 POST | `/v1/artifacts` | 新建（type=ExperimentPlan \| NextStepMemo） |
| **新增 PATCH** | `/v1/artifacts/{artifact_id}` | `{ "project_id", "data": { ... } }` |
| **新增 DELETE** | `/v1/artifacts/{artifact_id}` | query `project_id` |

Store：`update` / `delete`（对所有 Artifact 类型通用）。  
UI 第一期对 **ExperimentPlan + NextStepMemo** 暴露完整表单；MethodCard 等不做编辑入口。

### 6.4 前端可编辑字段

**ExperimentPlan**：title、objectives、variables / controls / success_criteria / record_fields（一行一项）、hyperparams、notes、status、claim_or_theorem_ref、revision_note、parent_plan_id（只读展示或高级项）。

**NextStepMemo**：title、verdict（supported / refuted / inconclusive）、missing_data、next_experiments（一行一项）、notes、data_packet_id、claim_ref。

- 工具栏：`新建计划` | `新建读数建议` | `刷新`。  
- `useArtifacts`：`create` / `update` / `remove`。  
- 空态：可手工新建，不只依赖对话。

### 6.5 与 DataPacket

| 类型 | 第一期 |
|------|--------|
| ExperimentPlan | **完整 CRUD** |
| NextStepMemo | **完整 CRUD** |
| DataPacket | 不纳入；继续用现有实验日志上传 |

### 6.6 不做（实验侧）

- 从 PDF 导入实验计划 / 读数建议  
- 自动根据 DataPacket 改计划状态  
- 计划与 Jupyter 单元格双向同步  

---

## 7. 非目标（第一期不做）

- 扫描版 PDF OCR  
- 导入后自动重建假设 DAG / 自动写 `symbols.md`  
- 跨会话全局定理库合并 UI  
- 从 arXiv URL 远程拉 PDF（本地上传即可）  
- 改写 Agent 自动抽取质量（另项）  
- MethodCard / DerivationTrace / DataPacket 完整 CRUD UI  
- 不为省 token 截断 PDF（见 §4.4；仅硬顶时截断）  

---

## 8. 实施顺序

1. **L4 Store**：`get` / `update` / `delete` + 级联删边  
2. **L4 API**：PATCH / DELETE + schemas  
3. **L4 API**：`import-preview` + 可选 `preview-markdown`  
4. **Artifact Store/API**：update / delete + PATCH/DELETE  
5. **定理库 UI**：Hook + Panel/Drawer + `TheoremImportModal`  
6. **实验面板 UI**：ExperimentPlan + NextStepMemo 新建/编辑/删除  
7. 文档：`doc/API.md`、README/Help 短说明  

---

## 9. 验收清单

**定理库**

- [ ] 新建一条 theorem，刷新后出现在当前 session 定理库  
- [ ] 编辑正文后保存，抽屉与列表预览更新  
- [ ] 删除后列表消失，相关边不再出现在 graph  
- [ ] Markdown 粘贴含 `## 定理 1` 可预览并勾选入库，`source=markdown_import`  
- [ ] 上传可选文字 PDF，出现候选；全不选则不写库；勾选后写入，`source=pdf_import`  
- [ ] 扫描件或空文本给出可读错误，不静默空列表  
- [ ] Theory Agent 自动抽取仍可用  

**实验计划 / 读数建议**

- [ ] 手工新建 ExperimentPlan，刷新后出现在时间线  
- [ ] 编辑计划 objectives / status 后更新可见  
- [ ] 手工新建 NextStepMemo，可改 verdict / next_experiments 并保存  
- [ ] 删除计划或读数建议后时间线不再显示  
- [ ] Agent 再产出计划/建议仍可追加，不覆盖手工条目  

---

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| LLM 乱抽 / 幻觉 | 候选确认；prompt 禁止无依据条目；confidence 低默认不勾选 |
| 长 PDF 请求超时 / 模型上下文硬顶 | 仅在硬限制时截断并警告；可调大超时；**不以省 token 为设计目标** |
| 公式乱码 | 要求输出 LaTeX `$...$`；用户可在确认前改 body |
| 误删定理/计划/建议 | 删除二次确认；定理可选版本快照 |
| 原地改历史计划导致「修订语义」混乱 | UI 文案提示可用「新建」保留旧计划；可选「另存为修订」 |
| NextStepMemo.data_packet_id 类型错误 | 表单按字符串校验；与已知 DataPacket id 对齐（可选手动填写） |

---

## 修订记录

| 日期 | 说明 |
|------|------|
| 2026-07-22 | 初稿：用户确认落地方案 2 |
| 2026-07-22 | 增补：实验计划（ExperimentPlan）CRUD |
| 2026-07-22 | 用户确认：不考虑 token 开销；PDF 导入默认送全文 |
| 2026-07-22 | 增补：NextStepMemo 完整 CRUD，提高可操作性 |
| 2026-07-22 | 用户确认规格并实施：L4 CRUD+导入、Artifact PATCH/DELETE、前端面板 |
