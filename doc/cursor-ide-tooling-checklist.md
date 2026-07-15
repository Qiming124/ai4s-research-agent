# Cursor IDE 开发辅助安装清单

> 仅针对 **Cursor 编辑器本身**（`~/.cursor/mcp.json`、Skills、Rules、Hooks 等）。  
> **不包含** AI4S 项目内置 MCP（`conf/mcp_servers.json`）。  
> 生成日期：2026-06-29

---

## 配置位置速查

| 类型 | 全局（所有项目） | 项目级（仅当前仓库） |
|------|------------------|----------------------|
| MCP | `~/.cursor/mcp.json` | `.cursor/mcp.json` |
| Rules | `~/.cursor/rules/` 或 User Rules | `.cursor/rules/*.mdc` |
| Skills | `~/.cursor/skills-cursor/`、`~/.agents/skills/` | 同上（Cursor 全局加载） |
| Hooks | `~/.cursor/hooks.json` | 项目内 hooks |
| 改完生效 | 重启 Cursor 或 Reload Window | 同上 |

建议：与你当前 loss-landscape 研究相关的 MCP，优先写在 **项目级** `.cursor/mcp.json`，避免所有项目都加载大量工具占 token。

---

## 一、你已安装的（Cursor IDE）

### MCP（当前会话可见）

| MCP | 用途 | 对你是否够用 |
|-----|------|--------------|
| cursor-ide-browser | 浏览器自动化、截图 | 一般够用；论文站不如专用 arXiv MCP |
| GitKraken / GitLens | Git 操作 | 够用 |
| Firecrawl | 网页抓取 | 够用 |
| Fetch | 拉 URL 正文 | 够用 |
| 百度搜索 | 中文检索 | 够用 |
| Excel | 表格读写 | 整理符号表、实验矩阵 |

### Skills（已安装）

| Skill | 建议保留 | 与你工作的关系 |
|-------|----------|----------------|
| **brainstorming** | ✅ | 设计 agent 阶段、拆引理 |
| **canvas** | ✅ | 损失曲面、优化轨迹交互图 |
| **sdk** | ✅ | 用 Cursor SDK 编排自动化 |
| **create-rule** | ✅ | 写推导规范 rule |
| **create-skill** | ✅ | 固化 theory 工作流 |
| **find-skills** | ✅ | 发现更多 skill |
| **skill-creator** | 可选 | 优化自定义 skill |
| **review-bugbot / review-security** | 可选 | 改 agent 代码时用 |
| **frontend-design / canvas-design** | 低优先 | 除非大改 Web UI |
| **automate / create-hook / loop** | 可选 | 保存证明稿时自动检查 |
| **babysit / split-to-prs** | 协作时 | PR 维护 |
| **update-cursor-settings / statusline** | 按需 | 编辑器偏好 |

---

## 二、建议新装的 MCP（Cursor IDE）

按你的场景（**理论推导 + 文献 + 长期记忆**）排序。

### P0 — 强烈建议

#### 1. 学术文献 MCP（三选一或组合）

| 包 / 仓库 | 特点 | 安装方式示例 |
|-----------|------|--------------|
| **[paperbase-mcp](https://github.com/bettyguo/paperbase-mcp)** | arXiv + Semantic Scholar + OpenAlex；引用图、BibTeX、related work | `uvx` / 见仓库 `docs/install.md` |
| **[ref-finder-mcp](https://github.com/dowoonlee/ref-finder-mcp)** | 多源搜索；**按章节**读 arXiv 全文（省 token） | Python / uv，见仓库 README |
| **[lit-mcp](https://github.com/gauravfs-14/lit-mcp)** | arXiv + DBLP；带 research summary 类 prompt | `uvx lit-mcp` |

**推荐组合**：`ref-finder-mcp`（读论文正文）+ `paperbase-mcp`（引用链 + BibTeX）。

```json
// .cursor/mcp.json 示例（路径按各仓库文档调整）
{
  "mcpServers": {
    "lit-mcp": {
      "command": "uvx",
      "args": ["lit-mcp"]
    }
  }
}
```

#### 2. 持久记忆 MCP

长周期推导需要记住：符号约定、已证引理、待证问题。

| 包 | 特点 |
|----|------|
| `@modelcontextprotocol/server-memory` | 官方简单记忆，零配置 |
| [cursor-brain](https://github.com/samhith123/cursor-brain) | 本地 SQLite + 可选语义搜索 |
| [mcp-memory-engine](https://github.com/forneverand/mcp-memory-engine) | 功能多（矛盾检测、schema），较重 |

**推荐**：先试官方 `server-memory` 或 `cursor-brain`；复杂后再上 memory-engine。

```json
"memory": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-memory"]
}
```

#### 3. GitHub MCP

管理 issue、PR、读 review 评论；与 `gh` 互补。

```json
"github": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "${env:GITHUB_TOKEN}"
  }
}
```

---

### P1 — 很有用

#### 4. 更强搜索（可选 API Key）

| MCP | 用途 |
|-----|------|
| `@anthropic/mcp-server-tavily` | 面向研究的网页搜索，比 DuckDuckGo 稳 |
| `@modelcontextprotocol/server-brave-search` | 通用搜索备选 |

#### 5. 本地 PDF / 论文 RAG

| 包 | 特点 |
|----|------|
| [arxiv-intelligence-mcp](https://github.com/rishimule/arxiv-intelligence-mcp) | 下载 PDF → DocLing 解析 → Chroma RAG；适合精读库 |

适合：你把 loss landscape、NTK、implicit bias 等经典论文 ingest 后，在 Cursor 里直接 `ask_paper`。

#### 6. Zotero（文献管理）

若你用 Zotero 管理 PDF 和 BibTeX，可找社区 **Zotero MCP**（GitHub 搜 `zotero mcp`），在 Cursor 里查库、导出引用。

---

### P2 — 按需

| MCP | 何时装 |
|-----|--------|
| **Wolfram Alpha MCP** | 查特殊函数、矩阵性质；需 API Key |
| **Playwright MCP** | 已有 browser MCP，一般不必重复 |
| **Notion / Linear MCP** | 用这些做研究笔记 / 任务板时 |
| **Postgres / SQLite MCP** | 想把引理、假设存结构化 DB 时 |
| **Filesystem MCP**（官方 `@modelcontextprotocol/server-filesystem`） | 让 Cursor 读写指定目录；注意目录白名单 |

---

### 不太建议为 Cursor IDE 优先装

| 类型 | 原因 |
|------|------|
| 第三个通用搜索 MCP | Fetch + Firecrawl + 百度已够 |
| 未审计的 npm `-y` 小包 | MCP 供应链风险高，见下文安全说明 |
| SymPy MCP（第三方） | Cursor 里 LLM 可直接写 Python/SymPy 脚本验证；专用 MCP 收益不如文献 + 记忆 |

---

## 三、建议新装的 Skills（Cursor IDE）

Skills 通过 [skills.sh](https://skills.sh/) 或 `npx skills` 安装：

```bash
npx skills find "math"
npx skills find "research"
npx skills find "latex"
npx skills add <owner/repo/skill-name>
```

### 从生态里找（搜索关键词）

| 搜索词 | 可能找到的能力 |
|--------|----------------|
| `math` / `theorem` / `proof` | 证明写作、符号规范 |
| `research` / `paper` / `arxiv` | 文献综述 workflow |
| `latex` / `academic` | 论文 / 公式排版 |
| `python` / `pytorch` | 实验脚本、数值验证 |

安装前看 **install 数、来源**（优先 `anthropics`、`vercel-labs`、高 star 仓库）。

### 更值得 **自建** 的 Skills（比搜现成的更贴你的课题）

用 **create-skill** 或手动写到 `~/.agents/skills/`：

| 自建 Skill 名 | 作用 |
|---------------|------|
| `loss-landscape-workflow` | 形式化 → 局部分析 → SymPy/数值验证 → 审稿清单 |
| `derivation-verify` | 从文稿抽 L(θ)，要求跑符号求导 + 低维 Hessian 数值检查 |
| `paper-review` | 每步必须标 arXiv ID 或「自证」，禁止跳步 |
| `notation-guard` | 对照 `symbols.md`，符号不一致则报错 |

---

## 四、建议写的 Rules（Cursor IDE）

用 **create-rule** 或在 `.cursor/rules/` 添加 `.mdc`：

| Rule 文件 | 内容要点 |
|-----------|----------|
| `theory-derivation.mdc` | 损失函数、临界点、Hessian 定义；禁止「显然」 |
| `agent-workflow.mdc` | 你正在开发的 multi-agent 阶段划分与输出格式 |
| `citation.mdc` | BibTeX / arXiv ID 引用格式 |

**Glob 示例**：只对理论稿生效

```yaml
---
description: 损失函数理论推导规范
globs: theory/**/*.md, docs/**/*.tex
alwaysApply: false
---
```

---

## 五、Hooks 与 Automations（可选）

| 能力 | Skill | 用途 |
|------|-------|------|
| **Hooks** | create-hook | 保存 `proofs/*.md` 时触发检查脚本 |
| **Automations** | automate | 定时跑「待证引理」提醒、同步文献 |
| **Loop** | loop | 周期性 review 推导 backlog |

---

## 六、其他 Cursor 功能（非 MCP，但很有用）

| 功能 | 用法 |
|------|------|
| **@Docs** | Settings → Indexing：把 arXiv 帮助页、SymPy 文档、PyTorch 文档加进索引 |
| **Codebase indexing** | 整个 agent 仓库可被 @codebase 引用 |
| **Notepads** | 固定符号表、假设列表，多对话共用 |
| **User Rules** | 全局「推导必须分引理编号」类短规则 |
| **Canvas** | 用 canvas skill 做 loss landscape 交互说明 |

---

## 七、针对你课题的「最小套装」

若只想装 **5 样**，建议：

1. **文献 MCP**：`ref-finder-mcp` 或 `paperbase-mcp`
2. **记忆 MCP**：`@modelcontextprotocol/server-memory` 或 `cursor-brain`
3. **GitHub MCP**：跟踪 agent 工作流开发
4. **自建 Skill**：`loss-landscape-workflow`
5. **自建 Rule**：`theory-derivation.mdc`

已有 Firecrawl / Fetch / 百度 / browser **不必重复加搜索类 MCP**。

---

## 八、安装步骤（通用）

1. 编辑 `~/.cursor/mcp.json` 或项目 `.cursor/mcp.json`
2. 粘贴 server 配置（`command` + `args` + `env`）
3. **Cursor → Settings → MCP** 确认绿灯
4. **Developer: Reload Window**
5. 新对话里让 Agent「列出可用 MCP 工具」做冒烟测试

Skills：

```bash
npx skills find loss
npx skills add <package>   # 按搜索结果安装
```

---

## 九、安全提醒

- MCP 会以子进程权限运行，**只装你审查过的仓库**；优先 pin 版本或 commit，避免每次 `npx -y` 拉最新未知包。
- **GitHub Token、Tavily Key** 放环境变量，不要写进 git 跟踪的 json。
- 文献 MCP 若需 `mailto`（OpenAlex polite pool），用真实邮箱。
- Cursor 会在会话开始时加载 MCP tool schema，**装太多 MCP 会占 context**；建议活跃 MCP ≤ 5～8 个。

---

## 十、勾选总表

| 类别 | 项目 | 优先级 | 完成 |
|------|------|--------|------|
| MCP | ref-finder-mcp / paperbase-mcp | P0 | ☐ |
| MCP | server-memory 或 cursor-brain | P0 | ☐ |
| MCP | server-github | P0 | ☐ |
| MCP | arxiv-intelligence-mcp（本地 RAG） | P1 | ☐ |
| MCP | Tavily 搜索 | P1 | ☐ |
| MCP | Zotero MCP | P1 | ☐ |
| MCP | Wolfram Alpha | P2 | ☐ |
| Skill | loss-landscape-workflow（自建） | P0 | ☐ |
| Skill | derivation-verify（自建） | P1 | ☐ |
| Rule | theory-derivation.mdc | P0 | ☐ |
| 其他 | @Docs 索引 SymPy / PyTorch | P1 | ☐ |
| 其他 | Notepads 符号表 | P1 | ☐ |

---

## 相关文档

- 项目侧 MCP（本文 **不包含**）：[mcp-config.md](mcp-config.md)
- 架构与流水线：[ARCHITECTURE.md](ARCHITECTURE.md)
