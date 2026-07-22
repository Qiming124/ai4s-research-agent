# AI4S 理论侧 Agent 验收结果

- **日期**：2026-07-22  
- **执行环境**：`http://127.0.0.1:8000`（uvicorn + `app/web/dist`）  
- **模型**：`deepseek-v4-pro`（`reasoning_effort=max`）  
- **验收课题**：`7f4ea49e-d7a`  
- **验收会话**：`accept-sess-32bc8fd2`  
- **原始明细**：[`2026-07-22-agent-acceptance-raw.json`](2026-07-22-agent-acceptance-raw.json)  
- **活体脚本**：[`scripts/run_agent_acceptance.py`](../../../scripts/run_agent_acceptance.py)  
- **状态**：已完成  

判定：`Pass` / `Partial` / `Fail` / `Skip`

---

## 0. 前置

| 项 | 结果 | 备注 |
|----|------|------|
| `/health` | Pass | deepseek-v4-pro |
| `ENABLE_RAG` | Pass | 文档入库成功 |
| MCP status | Pass | connected；web_search / arxiv / filesystem / … |
| 验收课题 ID | Pass | `7f4ea49e-d7a` |
| 验收会话 ID | Pass | `accept-sess-32bc8fd2` |

---

## A. 金路径

| ID | 结果 | 现象 / 证据 |
|----|------|-------------|
| A1 | Pass | 课题创建 + `POST .../sessions/{sid}` 关联成功；列表初测偶发空，重链后可见 |
| A2 | Pass | MD/DOCX/PDF 入库；arXiv `1412.6980` 入库；`total=4` |
| A3 | Pass | literature 对话 ~65s，回复含 PL 要点；`rag-refs=8` |
| A4 | Pass | theory+math 形式化 PL 假设；推导迹 artifact 存在 |
| A5 | Pass | 定理 id=83 CRUD；对话成功引用「验收-PL局部极小」 |
| A6 | Pass | experiment 给出计划；artifact 含 ExperimentPlan |
| A7 | Pass | CSV 上传 `indexed`；追问给出 train/val gap 与下一步 |
| A8 | Pass | preview/md/docx/pdf 均 200 |
| A9 | Pass | literature+工具检索到 PL 相关论文标题 |

**金路径结论**：**Pass（主闭环成立）**。文献 → RAG 问答 → 理论推导/定理 → 实验计划 → 数据解读 → 导出 → MCP 检索均可用。

---

## B1 文献 / RAG

| ID | 结果 | 现象 |
|----|------|------|
| L1 | Pass | 文本/MD 入库 |
| L2 | Pass | DOCX + PDF（`2003.00307.pdf`） |
| L3 | Pass | arXiv 1412.6980 |
| L4 | Pass | 同课题 sessB `total=4`；其他课题 `total=0` |
| L5 | Pass | `rag-refs=8` |
| L6 | Skip | 方法卡不测 |

## B2 理论

| ID | 结果 | 现象 |
|----|------|------|
| T1 | Pass | DerivationTrace artifact + 聊天推导 |
| T2 | Pass | create/list/patch 成功 |
| T3 | Pass | 模型明确引用定理库条目 |
| T4 | Pass | assumption-dag 返回 nodes |
| T5 | Pass | graph 探测 200（业务正确性未深测） |
| T6 | Pass | workspace 文件列表 200（完善度未深测） |

## B3 产出

| ID | 结果 | 现象 |
|----|------|------|
| O1 | Pass | ExperimentPlan 可见 |
| O2 | Pass | CSV 上传 indexed |
| O3 | Pass | md/docx/pdf 导出；polish 需 `ai_instructions`（非 `instructions`） |

## B4 课题与会话

| ID | 结果 | 现象 |
|----|------|------|
| P1 | Pass | 创建/关联/重命名；列表偶发延迟空属弱风险 |
| P2 | Pass | RAG 课题共享 / 跨课题隔离 |
| P3 | Pass | 同课题会话 B 定理列表为空（**会话隔离，符合实现**） |
| P4 | Partial | 同课题上传成功；跨会话实验复用未深测 |

## B5 Chat / Agent / MCP

| ID | 结果 | 现象 |
|----|------|------|
| C1 | Pass | chat / math 均返回内容 |
| C2 | Pass | auto_route 两问均 200；非流式响应未带回 agent_name（路由细节弱观测） |
| C3 | Pass | 指定 review 返回审稿职责自述 |
| C4 | Pass | arXiv/搜索类工具链可用 |
| C5 | Pass | `/v1/prompt/optimize` 返回多风格改写 |
| C6 | Pass | `/v1/agents` + `/v1/mcp/reload` 200 |
| C7 | Pass | deepseek-v4-pro |

---

## C. API 冒烟

| 套件 | 结果 | 备注 |
|------|------|------|
| test_smoke_all | Pass | 计入合计 |
| test_documents_full | Pass | 1 skipped（环境） |
| test_projects_full | Pass | |
| test_export_full | Pass | |
| test_jupyter_upload | Pass | |
| test_prompt_optimize | Pass | |
| **合计** | **37 passed, 1 skipped** | ~6.8s |

---

## 三行结论

1. **主闭环是否成立**：**是。** 金路径 A1–A9 全部 Pass；定位（文献→理论→实验指导→导出）可走通。  
2. **隔离是否符合实现表**：**是。** RAG 按课题共享；定理按会话隔离（与「同课题共享定理」的产品期望不一致 → **需求缺口**，非回归失败）。  
3. **P2 / 环境债**：方法卡未测；关系图谱/工作区仅探测通过；实验跨会话复用弱测；课题会话列表关联后偶发空列表；导出润色 API 字段名为 `ai_instructions`；长跑验收后偶发连接重置（需稳服务）。

---

## 回答效果评判（相对「能不能跑」）

样本会话：`accept-sess-32bc8fd2`（24 条消息）。评分维度：正确性 / 接地（RAG·工具）/ 任务契合 / 科研可用性 / 表达克制。量表：优 / 良 / 中 / 差。

### 分题点评

| 场景 | 效果 | 评语 |
|------|------|------|
| 文献三句总结（literature） | **良** | 正确抓住 PL 线性收敛 + 深度线性网无次优局部极小，并挂钩入库文献；但用户只要「三句话」，实际长文 + 强制 MethodCard 围栏，**克制失败**。 |
| 文献→形式化推导（pipeline） | **良偏中** | PL/梯度流一段可核、与课题符号对齐较好；Kawaguchi「局部极小⇒残差为 0」论证偏跳步（投影算子处近乎断言）。篇幅过长（7k+ 字）。 |
| 短问：PL⇒临界点全局最优 | **优** | 标准正确证明：\(\|\nabla L\|^2\ge 2\mu(L-L^*)\) 在 \(\nabla L=0\) 时强制 \(L=L^*\)。干净、可用作定理库素材。 |
| 实验计划（experiment） | **优** | 明确「不代跑」；给可证伪判据（\(\hat\mu\)、\(L-L^*\)）；缺数时诚实写 DataPacket 空。符合理论侧顾问定位。 |
| 上传 CSV 后下一步 | **优** | 正确诊断过拟合（train↓ val 平台、gap↑）；优先正则/早停而非盲目加宽；区分「优化健康」与「泛化失败」，并声明现有数据不足以直接判 H1。 |
| arXiv/PL 检索 | **优** | 命中经典 Karimi et al. `1608.04636`，并与课题不等式对照，检索质量高。 |
| diffusion 综述线索（auto） | **良** | 推荐 `2209.00796` 等合理；硬把扩散拉回 PL 课题略牵强。 |
| 「临界点梯度为零」要点 | **中** | 末尾正确指出「临界点即定义为梯度为零」；主体却证「局部极小⇒临界点」，与字面问题不完全同向（元认知有、主证明跑偏）。 |
| review 角色自述 | **优** | 一句话职责清晰、符合审稿 Agent。 |

### 总评

**整体：良（B+）——作为「理论侧科研助手」可用，尚未到稳定「可直接引用进论文」级别。**

| 维度 | 判定 | 说明 |
|------|------|------|
| 核心理论正确性 | 强 | PL 基本事实、过拟合诊断、实验顾问边界把握好 |
| RAG / 文献接地 | 中强 | 有引用痕迹与工具命中；片段噪声大（公式 OCR 碎），总结有时夸大「两篇核心文献」覆盖面 |
| 实验指导可用性 | 强 | 可执行、可证伪、不越权代训 |
| 形式化严谨性 | 中 | 短证明优；长推导有跳步与「文献方法」标签掩盖未证步骤 |
| 交互体验 | 弱–中 | 过长、流水线强塞 MethodCard/工件围栏，压过用户「三句话/只要要点」约束 |

### 对产品定位的含义

- **已经像科研助手的部分**：读文献要点、给可检验实验计划、用上传数据做下一步建议、检索经典论文。  
- **还不够「深领域可信」的部分**：长推导需人工审稿；RAG 引用质量不稳定；回答长度与强制工件损害可用性。  
- **优先改进（效果向，非通断向）**：  
  1. 抑制与问题无关的 MethodCard 强制附加；服从「三句话/只要要点」。  
  2. 长推导要求逐步标注「文献复述 / 自证 / 未证假设」。  
  3. RAG 引用展示可读 snippet，避免碎公式片段充当「证据」。

---

## 需求 / 体验缺口（非本次 Fail）

| 项 | 说明 |
|----|------|
| 定理作用域 | 产品口述「同课题共享」，实现为会话级 + global |
| 方法卡 | 用途未澄清；流水线仍会强制注入，干扰短问答 |
| 关系图谱 / 工作区 | 能开、能列，业务闭环未验 |
| 会话列表时序 | link 成功后立即 list 可能为空，建议前端重试或后端事务确认 |
| polish 字段 | 前端/文档应对齐 `ai_instructions` |
| 回答克制 | 效果债：默认过长 + 工件围栏 |
