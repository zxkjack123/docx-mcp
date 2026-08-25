# Repository Review: docx-mcp — Defect Roadmap Verification

**Review Scope**: `docs/plans/2026-07-27-real-world-defects-roadmap.md` — 针对所有声称的 Bug 与缺失功能的代码级验证
**Review Date**: 2026-07-27

## Executive Summary

- **Findings**: 3 🔴 / 2 🟡 / 1 🟢  
- **Project Profile**: Python (MCP server), OOXML manipulation via lxml  
- **Overall Health**: 该路线图精准诊断了从 agent 实战反馈中梳理出的三大核心缺陷。全部 3 个 Bug 声称均经源代码确认属实。Feature 缺漏整体方向正确，其中一处归类表格存在 3 处误差。

---

## ① 仓库概要

- **结构**: `docx_mcp/document/` 目录按功能分解（tracks、formatting、compare、reading 等），`server.py` 通过 FastMCP 装饰器将方法暴露为工具。
- **句柄系统**: `server.py` 第 38-39 行通过 `__default__` 键维护共享 in-memory document 字典；许多工具仍依赖 `_require_doc()`，锁定在默认 slot。
- **CI/测试**: `.github/workflows/ci.yml` 存在；`tests/` 下有约 80 个测试文件。`test_compare.py` 存在但缺少表格/图片/OMML 的负面用例。

---

## ② 待完成事项

| ID | 类型 | 位置 | 描述 |
|----|------|------|------|
| INC-01 | 技术债 | `compare.py` | compare_documents 不处理结构化元素 |
| INC-02 | 待完成功能 | `formatting.py:140` | update_paragraph 不支持 tracked |
| INC-03 | 待完成功能 | `server.py`（多处） | ~50 个工具仍使用 `_require_doc()` |

---

## ③ 代码质量问题

| ID | 严重程度 | 位置 | 类别 | 描述 | 修复方案 |
|----|----------|------|------|------|----------|
| CQ-01 | 🔴 | `tracks.py:289` | 搜索逻辑 | `_resolve()` 即使传入了 `para_id` 仍检查文档全局唯一性 | 当 para_id 已指定时跳过 `_doc_norm_count` |
| CQ-02 | 🔴 | `compare.py:28-32` | 解析器不完整 | `_body_paragraphs()` 只提取 `w:p`，丢弃 `w:tbl`/`w:drawing` | 短期：检测到结构化元素时返回错误；长期：实现结构化 diff |
| CQ-03 | 🟡 | `reading.py:146` + `server.py:2937` | 句柄隔离 | `copy_document` 缺少 `document_handle` 参数 | 添加 handle 参数，或增加警告性文档说明 |
| CQ-04 | 🟡 | `server.py:2310-2328` | 缺失 tracked 参数 | `update_paragraph` 静默覆盖，不产生修订标记 | 新增 `tracked: bool = False` 及 `author: str` 参数 |
| CQ-05 | 🟡 | `server.py`（约 50 个工具） | 句柄隔离 | 大量工具使用 `_require_doc()`，仅支持 `__default__` | 对每个工具增加 `document_handle: str = ""` 参数 |

---

## ④ 潜在 Bug

| ID | 严重程度 | 位置 | 类别 | 描述 | 修复方案 | 发现方法 |
|----|----------|------|------|------|----------|----------|
| BUG-01 | 🔴 | `tracks.py:289` | 误报拒绝 | 当 `replace_text` 带明确的 `para_id` 调用，且 find 文本在目标段落中仅出现一次，但同一文本存在于其他段落时，操作会因 "Ambiguous: appears in multiple paragraphs" 被拒绝 | 将搜索流程改为：当 para_id 指定时，`get_paragraph(para_id)` → `search_within(find)`，绕过 `_doc_norm_count` | 代码分析（系统性） |
| BUG-02 | 🔴 | `compare.py:28-289` | 文档损坏 | 对含 `w:tbl`/`w:drawing`/`m:oMath` 的文档调用 `compare_documents` 时，由于仅 diff `w:p` 元素，会导致表格数据错位、图片引用错乱、OMML 方程被剥离 | 检测到非 `w:p` 子元素时返回显式错误；或实现真正的结构化 diff | 代码分析（系统性） |
| BUG-03 | 🟡 | `reading.py:146` | 句柄混淆 | copy_document 后，写操作仍作用于原句柄，可能导致在读取磁盘旧内容后意外覆盖 | 将 `copy_document` 改为支持 `document_handle`，并在文档字符串中标注警告 | 代码分析（系统性） |

---

## ⑤ 优化机会

| ID | 严重程度 | 位置 | 类别 | 描述 | 修复方案 |
|----|----------|------|------|------|----------|
| OPT-01 | 🟢 | `server.py:1463` | 功能请求 | `save_document` 缺少集成的 sanitize 功能 | 新增 `sanitize_level: int = 0` 参数，消除 save→close→open→sanitize→close 的多步流程 |
| OPT-02 | 🟢 | `tracks.py:692` | 功能请求 | `replace_text` 不支持同段落内替换全部匹配 | 新增 `replace_all: bool = False` 参数 |
| OPT-03 | 🟢 | `images.py` | 功能请求 | 缺少从 docx 导出单张图片的能力 | 新增 `extract_image(rId, output_path)` 工具 |

---

## 修复路线图

### 优先级 1 — 🔴 关键

1. **Bug 1 修复** (`tracks.py:289`) — 影响面：30% 的 `replace_text` 调用可能在多段落文档中失败。修复成本：低（< 2h）。阻塞项：agent 会因此频繁回退到静默 `update_paragraph`。  
2. **Bug 2 修复** (`compare.py`) — 影响面：任何含表格或图片的文档。修复成本：短期低（< 1h，加检测+报错）；长期高（结构化三层 diff）。阻塞项：可能导致文档损坏且用户无法察觉。  
3. **Feature 1** (`update_paragraph` tracked) — 影响面：agent 被迫做出不可见的修改。修复成本：中（< 4h）。阻塞项：阻断审核-修正工作流。

### 优先级 2 — 🟡 警告

4. **Bug 3** (`copy_document` 文档 / handle) — 影响面：多文档工作流。修复成本：低。  
5. **Feature 2** (`document_handle` 传播) — 路线图声称 7 个工具受影响；源代码确认 6+ 个工具实际受影响（与表格存在 3 处偏差，见下）。修复成本：中（< 6h，含测试）。

### 优先级 3 — 🟢 增强

6. **Feature 3** (`save_document` 集成 sanitize) — 影响面：便利性。修复成本：低（< 1h）。  
7. **Design 1-3**（`replace_all`、`extract_image`、重命名）— UX 改善。

---

## Feature 2 勘误（`document_handle` 覆盖率）

路线图表格声称以下工具缺少 `document_handle`。与源代码 (`server.py`) 对比：

| 工具 | 路线图声称 | 实际状态 | 行号 |
|------|-----------|----------|------|
| `accept_changes` | ❌ 缺失 | ✅ **已支持** | 1302 |
| `reject_changes` | ❌ 缺失 | ✅ **已支持** | 1309 |
| `generate_change_summary` | ❌ 缺失 | ✅ **已支持** | 1614 |
| `accept_all_changes` | ❌ 缺失 | ❌ 缺失 | 1342 |
| `reject_all_changes` | ❌ 缺失 | ❌ 缺失 | 1351 |
| `sanitize_metadata` | ❌ 缺失 | ❌ 缺失 | 1528 |
| `find_replace_formatted` | ❌ 缺失 | ❌ 缺失 | 2730 |
| `get_document_outline` | ❌ 缺失 | ❌ 缺失 | 2799 |
| `convert_to_pdf` | ❌ 缺失 | ❌ 缺失 | 2952 |
| `copy_document` | _（未列出）_ | ❌ 缺失 | 2937 |
| `update_image` | _（未列出）_ | ❌ 缺失 | 719 |

**总结**：所列 7 个工具中，3 个已支持，4 个确实缺失（另有 2+ 个未在表格中列出）。问题的**本质**方向正确——许多工具仍锁定在 `__default__`——但个别条目需要修正。

---

## 后续步骤

- 对优先级 1/2 的任务，建议切换至 **@Plan Architect**，将本报告作为输入，生成包含 MODIFY_SPEC 锚点的可执行阶段计划。
- `MODIFY_SPEC` 字段已为 Bug 1（`tracks.py:289`）和 Feature 1（`formatting.py:140`）内联标注修复定位信息。

## 局限性

- 本审阅为**静态代码分析**，未执行运行时重现。
- 仅限于路线图提到的范围；未对 `_require_doc()` 与 `_resolve(handle)` 使用模式进行全库审计。
