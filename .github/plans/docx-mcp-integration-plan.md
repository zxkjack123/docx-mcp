# docx-mcp 集成部署执行方案

| 字段 | 值 |
|------|-----|
| 版本 | v1.0 |
| 生成日期 | 2026-07-24 |
| 状态 | Step 1 ✅ / Steps 2-3 📋 |
| 目标 | 将 docx-mcp 集成到现有 agent 生态，填补直接 DOCX 操作空白 |

---

## 背景与目标

现有 MCP 工具链覆盖了文档格式转换（formatforge）、引用管理（mcpzotero）、学术规范检查（manuscript-lint）等环节，但缺少 **agent 直接编辑已有 DOCX 文档** 的能力。docx-mcp 提供 219 个底层 OOXML 编辑工具，填补了这一核心空白。

### 核心使用场景

1. **合同/报告审核**：在现有 DOCX 中进行修订追踪编辑 + 注释
2. **脚注/尾注管理**：在学术文档中添加、修改、校验脚注
3. **表格精确修改**：修改现有表格的单元格内容、行列结构
4. **文档结构操作**：插入分页/分节符、设置页面属性
5. **文档审计**：OOXML 结构完整性检查（paraId 唯一性、脚注交叉引用等）

---

## Step 1：安装与部署 ✅ 已完成

### 1.1 包安装

```bash
# 使用 uvx（推荐，自动管理虚拟环境）
uvx docx-mcp-server
# 首次运行自动下载依赖（lxml, spacy, presidio 等，约 80MB）
```

状态：✅ 已安装，依赖解析成功

### 1.2 MCP Server 配置

在 `~/.config/opencode/opencode.jsonc` 的 `mcp` 块中添加：

```jsonc
"docx-mcp": {
  "type": "local",
  "command": [
    "uvx",
    "docx-mcp-server",
  ],
  "enabled": true,
  "timeout": 600000,
  "environment": {
    "PATH": "/home/gw/.local/bin:/snap/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
  },
}
```

状态：✅ 已添加至 L1021-L1032

### 1.3 Skill 文件部署

```bash
cp /home/gw/opt/docx-mcp/skill/SKILL.md \
   /home/gw/.config/opencode/skills/docx-mcp-skill.md
```

状态：✅ 已部署（590 行 OOXML 操作指南）

---

## Step 2：Agent 指令集成方案

### 2.1 目标

创建一份 agent 指令文件，让 agent 明确：
- **什么时候用 docx-mcp**（编辑操作）
- **什么时候用 formatforge**（格式转换）
- **两者如何配合使用**
- **OOXML 关键陷阱速查**

### 2.2 指令文件内容

**文件路径**：`/home/gw/.config/opencode/instructions/docx-workflow.instructions.md`

```markdown
# DOCX Document Workflow — Agent Instructions

## Tool Selection Matrix

| 操作意图 | 使用工具 | 原因 |
|----------|---------|------|
| 打开已有 DOCX 做修改 | `docx-mcp.*` | 唯一的直接编辑能力 |
| 修订追踪编辑（增/删/改） | `docx-mcp.insert_text / delete_text / replace_text` | 生产 Word 原生的修订标记 |
| 添加/回复注释 | `docx-mcp.add_comment / reply_to_comment` | 注释锚定到段落 |
| 管理脚注/尾注 | `docx-mcp.add_footnote / validate_footnotes` | OOXML 级脚注操作 |
| 修改表格单元格 | `docx-mcp.modify_cell / add_table_row` | 保持表格结构完整性 |
| 格式设置（字体/颜色/粗斜体） | `docx-mcp.set_formatting / set_run_font / set_run_size / set_run_color` | 修订追踪感知的格式设置 |
| 页面版式（分页/边距/方向） | `docx-mcp.add_page_break / set_page_margins / set_page_orientation` | 直接 OOXML sectPr 操作 |
| 文档审计 | `docx-mcp.audit_document / validate_paraids / validate_footnotes` | 保存前的结构完整性 |
| 删除水印 | `docx-mcp.remove_watermark` | 交付前的清理 |
| Markdown → DOCX 转换 | `formatforge.convert_markdown_to_docx` | 格式保真度更高 |
| DOCX → Markdown 转换 | `formatforge.convert_docx_to_markdown` | 格式保真度更高 |
| DOCX → LaTeX | `formatforge.convert_docx_to_latex` | 完整的模板/字体/CJK 支持 |
| DOCX → EPUB | `formatforge.convert_docx_to_epub` | 电子书出版管道 |
| 引用注入（Zotero 字段代码） | `mcpzotero.inject_citations` | 原生 Zotero 引用管理 |
| 从 DOI 添加论文到 Zotero | `mcpzotero.add_items_by_doi` | 自动元数据 + OA PDF |
| 学术内容质量检查 | `manuscript-lint.*` | 内容级审计（摘要/引用/统计） |

## Workflow: 从零创建学术论文 DOCX

```
1. [Research]     zotpilot.search_academic_databases  → 找到参考文献
2. [Collect]      mcpzotero.add_items_by_doi          → 添加到 Zotero 库
3. [Draft]        formatforge.convert_markdown_to_docx → MD → DOCX 初稿
4. [Cite]         mcpzotero.inject_citations           → 注入 Zotero 引用字段
5. [Polish]       docx-mcp.open_document               → 打开 DOCX
6. [Edit]         docx-mcp.add_footnote / set_formatting → 添加脚注/格式
7. [Audit]        docx-mcp.audit_document              → 结构验证
8. [Export]       docx-mcp.save_document               → 保存
9. [Publish]      formatforge.convert_docx_to_latex    → 导出 LaTeX/PDF
```

## Workflow: 审阅已有 DOCX（修订追踪）

```
1. [Open]         docx-mcp.open_document                → 打开 DOCX
2. [Scan]         docx-mcp.get_headings                 → 了解文档结构
3. [Search]       docx-mcp.search_text                  → 查找目标文本
4. [Verify]       docx-mcp.get_paragraph                → 确认精确文本
5. [Edit]         docx-mcp.delete_text + insert_text    → 带修订的删除+插入
6. [Comment]      docx-mcp.add_comment                  → 解释修改原因
7. [Repeat]       Steps 3-6 for each change
8. [Audit]        docx-mcp.audit_document               → 结构完整性检查
9. [Save]         docx-mcp.save_document("revised.docx") → 保存为新文件
```

## OOXML 关键陷阱（速查）

| 陷阱 | 规则 | 检查工具 |
|------|------|----------|
| paraId 唯一性 | 所有 XML 部件中必须是唯一的（包括脚注/页眉/页脚） | `validate_paraids()` |
| 脚注 1:1 映射 | 每个脚注 ID 在 document.xml 中恰好引用一次 | `validate_footnotes()` |
| 脚注 ID 连续性 | 无间隙 — 从 id="1" 开始 | `validate_footnotes()` |
| 不间断空格 | Word 使用 \xa0 — 直接字符串匹配会失败 | `search_text()` 自动处理 |
| 删除整个段落 | 还必须将段落标记标记为已删除，否则接受修订后留下空段落 | `audit_document()` |
| 字段代码顺序 | `w:fldChar` 和 `w:instrText` 必须各自在单独的 `<w:r>` 中 | — |

## 强制规则

1. **始终 `audit_document()` 在 `save_document()` 之前** — 在修订损坏文件之前发现问题。
2. **始终保存到新文件** — 使用 `save_document("original_revised.docx")`，不要覆盖原始文件。
3. **在 `delete_text()` 之前验证文本** — 先用 `get_paragraph()`，文本必须在单个 run 内精确匹配。
4. **不混合职责** — 使用 formatforge 进行格式转换，使用 docx-mcp 进行内容编辑。不要对同一项任务同时使用两者。

## 与 formatforge 的接口

formatforge 转换后 → docx-mcp 打开 → 编辑 → 保存。
docx-mcp 导出 → formatforge 转换格式。

不要在转换后使用 docx-mcp 重新生成文档。不要在 docx-mcp 会话中间使用 formatforge 重新转换。在启动 docx-mcp 会话之前，选择一个管道并坚持执行。
```

### 2.3 部署

```bash
mkdir -p /home/gw/.config/opencode/instructions
cp /path/to/docx-workflow.instructions.md \
   /home/gw/.config/opencode/instructions/docx-workflow.instructions.md
```

---

## Step 3：学术文档工作流集成方案

### 3.1 目标

将 docx-mcp 与 mcpzotero + formatforge + manuscript-lint 配对，形成完整的学术文档撰写工作流。

### 3.2 完整管道

```
┌──────────────────────────────────────────────────────────────┐
│                  学术论文 DOCX 工作流                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Phase 1: RESEARCH & COLLECT                                 │
│  ┌──────────────────────────────────────────────┐            │
│  │ zotpilot.search_academic_databases           │ 找论文     │
│  │ zotpilot.ingest_papers                       │ 入库       │
│  │ mcpzotero.add_items_by_doi                   │ 元数据+PDF │
│  └──────────────────────────────────────────────┘            │
│                         ↓                                    │
│  Phase 2: DRAFT                                              │
│  ┌──────────────────────────────────────────────┐            │
│  │ formatforge.convert_markdown_to_docx         │ MD→DOCX    │
│  │   - docx_standard: "nuclear-fusion" 或 "ieee"│            │
│  │   - reference_doc: 期刊模板.docx              │            │
│  └──────────────────────────────────────────────┘            │
│                         ↓                                    │
│  Phase 3: CITE                                               │
│  ┌──────────────────────────────────────────────┐            │
│  │ mcpzotero.inject_citations                   │ 引用注入   │
│  │   - style: "ieee" 或 "apa"                   │            │
│  │   - file_path: 生成的 .docx                   │            │
│  └──────────────────────────────────────────────┘            │
│                         ↓                                    │
│  Phase 4: EDIT (docx-mcp)                                    │
│  ┌──────────────────────────────────────────────┐            │
│  │ docx-mcp.open_document                       │ 打开       │
│  │ docx-mcp.add_footnote                        │ 脚注       │
│  │ docx-mcp.set_formatting                      │ 格式       │
│  │ docx-mcp.add_page_break / add_section_break  │ 版式       │
│  │ docx-mcp.add_comment                         │ 注释       │
│  │ docx-mcp.audit_document                      │ 审计       │
│  │ docx-mcp.save_document                       │ 保存       │
│  └──────────────────────────────────────────────┘            │
│                         ↓                                    │
│  Phase 5: AUDIT (content)                                    │
│  ┌──────────────────────────────────────────────┐            │
│  │ manuscript-lint.full_scan                    │ 内容质量   │
│  │   - profile: "paper"                          │            │
│  │ citation-lint.full_scan                      │ 引用校验   │
│  └──────────────────────────────────────────────┘            │
│                         ↓                                    │
│  Phase 6: PUBLISH                                            │
│  ┌──────────────────────────────────────────────┐            │
│  │ formatforge.convert_docx_to_latex            │ DOCX→LaTeX │
│  │ formatforge.convert_docx_to_epub             │ 或→EPUB    │
│  │ docx-mcp.export_markdown                     │ 或→MD      │
│  └──────────────────────────────────────────────┘            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 Agent 路由规则

创建 agent 指令，根据任务类型自动路由到正确工具：

```yaml
# 学术文档任务的 agent 路由规则

tasks:
  - match: "添加引用|插入文献|cite|reference|bibliography"
    tools: [mcpzotero.*, zotpilot.*]

  - match: "脚注|footnote|endnote"
    tools: [docx-mcp.add_footnote, docx-mcp.validate_footnotes]

  - match: "格式转换|markdown.*docx|docx.*latex|docx.*epub"
    tools: [formatforge.*]

  - match: "修改|编辑|替换|删除|插入|添加|批注|注释|comment|track.change"
    tools: [docx-mcp.*]

  - match: "检查|审计|验证|audit|validate|lint"
    tools: [manuscript-lint.*, citation-lint.*, docx-mcp.audit_document]

  - match: "修订模式|track.change|接受修订|拒绝修订|accept.*change|reject.*change"
    tools: [docx-mcp.accept_changes, docx-mcp.reject_changes]

  - match: "比较|对比|diff|compare.*docx"
    tools: [docx-mcp.compare_documents, docx-mcp.diff_to_text]
```

### 3.4 部署

```bash
# 将路由规则添加到 agent 配置或追加到现有指令
cat >> /home/gw/.config/opencode/instructions/docx-workflow.instructions.md << 'EOF'

## Agent Routing Rules (Academic Document Tasks)

当被要求处理文档任务时，根据以下规则选择工具：

1. **格式转换**（MD↔DOCX, DOCX→LaTeX, DOCX→EPUB）→ 始终使用 `formatforge.*`
2. **引用管理**（添加论文, 注入引用, 搜索库）→ 始终使用 `mcpzotero.*` / `zotpilot.*`
3. **直接 DOCX 编辑**（文本插入/删除, 脚注, 注释, 格式, 表格）→ 始终使用 `docx-mcp.*`
4. **修订追踪**（接受/拒绝/列出修订）→ 始终使用 `docx-mcp.*`
5. **文档审计**（结构, paraIds, 脚注交叉引用）→ 始终使用 `docx-mcp.audit_document`
6. **内容审计**（摘要质量, 引用完整性, 数字一致性）→ 始终使用 `manuscript-lint.*`

**禁止**：不要使用 formatforge 进行编辑。不要使用 docx-mcp 进行格式转换。
除非任务明确要求同时进行编辑和转换，否则不要在同一个任务中混合使用两者。
EOF
```

---

## 验证检查清单

### Step 1 验证

- [x] uvx docx-mcp-server 依赖解析成功
- [x] opencode.jsonc 中已添加 docx-mcp 条目
- [x] Skill 文件已复制到 ~/.config/opencode/skills/

### Step 2 验证（待执行）

- [ ] 指令文件已创建于 ~/.config/opencode/instructions/docx-workflow.instructions.md
- [ ] Agent 在给定了"将此合同中的 Net 30 改为 Net 60"时正确选择了 docx-mcp
- [ ] Agent 在给定了"将此 MD 转换为 DOCX"时正确选择了 formatforge
- [ ] Agent 在给定了"在 DOCX 中添加脚注然后导出为 LaTeX"时正确串联了 docx-mcp → formatforge

### Step 3 验证（待执行）

- [ ] 学术管道测试：创建论文 MD → formatforge 转换 → mcpzotero 引用注入 → docx-mcp 编辑 → manuscript-lint 审计
- [ ] Agent 不需要用户提示即可正确完成 zcite 占位符 → inject_citations → 在 Word 中刷新的完整循环

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|--------|----------|
| Agent 混淆 docx-mcp 和 formatforge 的职责 | 未跟踪的更改或格式损坏 | 在指令中明确强制分隔规则 |
| OOXML 陷阱导致文档损坏 | Word 静默"修复"文档，重写编辑 | 始终在保存前审计，始终保存到新文件 |
| 并行会话状态冲突 | 多个 agent 在同一文档上竞争 | 使用文档句柄进行会话隔离 |
| spaCy 模型文件过大 (~560MB) | 首次调用 PII 工具时长时间加载 | 延迟到首次使用时，非阻塞 |
| uvx 临时环境被清除 | 冷启动延迟 | 接受，因为 uvx 缓存持久化 |

---

## 修订日志

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-24 | 初始计划：Step 1 完成，Steps 2-3 方案 |

---

## 相关文件

- MCP 配置：`~/.config/opencode/opencode.jsonc` L1021-L1032
- Skill 文件：`~/.config/opencode/skills/docx-mcp-skill.md`
- 指令文件（待创建）：`~/.config/opencode/instructions/docx-workflow.instructions.md`
- 上游仓库：`/home/gw/opt/docx-mcp/`
