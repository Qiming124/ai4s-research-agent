# 产品定位改写设计：AI4S 理论侧多智能体（方案 2）

- **日期**：2026-07-22  
- **状态**：已实施（方案 B）  
- **范围**：叙事文案 + Agent 系统提示词泛化（方案 B / 推荐改法 2）  
- **不改**：API、路由、Agent 名单、A1–A6 种子文件内容、默认课题磁盘数据

---

## 1. 背景与目标

### 现状

产品对外与 Agent 提示词均锚定「深度学习损失函数**局部极小值**理论」，易被理解为**唯一**领域。

### 目标定位（一句话）

面向「**用深度学习解决科学问题**」的 **理论侧多智能体系统**：检索并阅读文献 → 理论推导/形式化 → 设计实验或下一步科研方向。  
**DL 优化 / 局部极小等**是能力子集与示范课题，不是唯一领域。

### 能力边界（保持）

| 做 | 不做 |
|----|------|
| AI 检索文献并阅读/方法提炼 | 代训、部署模型 |
| 理论推导与形式化 | 大规模数值实跑作为核心卖点 |
| 实验设计、缺数诊断、下一步方向 | 完整科研流水线复现（旧 Campaign） |
| 用户提交数据后的对照解读 | 云端训模型 / 代部署推理 |

### 能力闭环（主叙事）

```
literature → MethodCard → theory →（可选 review / counterexample）
  → experiment（ExperimentPlan / NextStepMemo）
  ← 用户交回 DataPacket ←
```

场景短协作（`RESEARCH_PIPELINE_MODE=auto`）仍为：`lit_to_theory` / `experiment_plan` / `data_to_nextstep`。

---

## 2. 命名与对外文案

| 项 | 新表述 |
|----|--------|
| 产品名（可保留） | AI4S 理论侧科研助手 / 理论侧多智能体 |
| 领域 | 用深度学习做科学问题的理论侧协作（AI for Science · 理论侧） |
| 示范 | 损失函数局部极小 / PL / A1–A6 等为**示范课题种子**，非唯一主题 |
| 版本叙事 | 仍属 v2.2；定位从「窄领域」上提为「AI4S 理论侧」 |

---

## 3. 改动清单

### 3.1 文档（必改）

- `doc/PRODUCT-VISION.md` — 领域/定位/Agent 职责表述  
- 根 `README.md`、`doc/README.md`  
- `doc/ARCHITECTURE.md` 开篇与能力边界  
- 其它文档中「唯一领域 = 局部极小」的硬断言（Help 相关说明若在 `doc/web.md` 则同步）

### 3.2 前端帮助（必改）

- `app/web/src/components/HelpPanel.tsx` — 产品名说明与副标题  

### 3.3 Agent 提示词（必改）

文件：`app/server/llm/prompts.py`

| Prompt | 策略 |
|--------|------|
| `DEFAULT_SYSTEM_PROMPT` | 定位改为 AI4S 理论侧总览；能力闭环四条；局部极小仅作示例 |
| `MATH_MODE_SYSTEM_PROMPT` | 泛化为科学问题中的数学推导；优化/损失为常见子类 |
| `THEORY_AGENT_PROMPT` | 先「问题形式化（目标量/假设/符号）」；损失景观步骤改为「若属优化/损失分析则适用」；仍可对照 `symbols.md` / `assumptions.md` |
| `EXPERIMENT_AGENT_PROMPT` | 实验顾问泛化为科学问题下的计划/读数/下一步；禁止代训不变 |
| `LITERATURE_AGENT_PROMPT` | 检索范围改为 DL-for-Science / DL 理论等用户问题域；方法卡保留；去掉「只做局部极小」 |
| `REVIEW_AGENT_PROMPT` | 审稿对象改为当前课题推导；清单对照仍可用 |
| `COUNTEREXAMPLE_AGENT_PROMPT` | 反例针对当前猜想/假设；不绑死损失景观 |

文件头注释同步新定位。

### 3.4 轻触（建议）

- `conf/prompt/test_cases.json`、`apiLab/presets.ts`：标题标明「示范：…」  
- Schema / OpenAPI **examples** 中局部极小例句可保留（示范），不必清空  

### 3.5 明确不改

- `data/theory/assumptions.md`、`symbols.md`、A1–A6 语义  
- Agent 枚举与路由代码  
- Artifact schema  
- Cursor rule `theory-derivation.mdc`（可选后续另开：加「示范课题」说明；本次可不改以免扩大范围）

---

## 4. 验收标准

1. 打开根 README / PRODUCT-VISION：读者不会认为产品**只能**做局部极小。  
2. 新对话（general / theory / literature / experiment）system 侧不再写「专注于损失函数局部极小值」作为唯一身份。  
3. HelpPanel 文案与文档一致。  
4. 现有局部极小示范种子与场景联测路径仍可用（回归：提示词仍允许优化/损失类问题）。  
5. 能力边界句子仍明确：不代训、不部署、不大规模实跑。

---

## 5. 非目标（本次不做）

- 新增物理/化学等垂直 Agent  
- 重写或删除 A1–A6 / 默认课题任务文案（属方案 C）  
- 实现代训 / 部署 / 大规模实验跑批  

---

## 6. 实施顺序（确认后）

1. 改 `PRODUCT-VISION.md` + 根/`doc` README 与架构开篇  
2. 改 `prompts.py` 全部 Agent  
3. 改 `HelpPanel.tsx` + 轻触测试案例/预设标题  
4. 快速全文检索残留「专注于…局部极小值」硬断言并清理文档侧  

---

## 修订记录

| 日期 | 说明 |
|------|------|
| 2026-07-22 | 初稿：用户确认选 B + 方案 2 |
| 2026-07-22 | 用户确认「先实现 B」；文档 + prompts + Help/Onboarding/OpenAPI 已落地 |
