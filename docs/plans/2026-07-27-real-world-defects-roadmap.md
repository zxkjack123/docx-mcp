# Real-World Defects & Improvement Roadmap

> **来源**：FDR agent 在「一种非匹配网格守恒映射方法」专利说明书修订中的实战反馈
> **日期**：2026-07-27
> **涉及工具**：`replace_text` ×30、`update_paragraph` ×20、`insert_paragraph` ×20、`update_image` ×15、`sanitize_metadata` ×8、`accept_changes` ×3、`compare_documents` ×1、`delete_paragraph` ×15

---

## Phase 1：Bug 修复（建议 v0.x.0）

### Bug 1 — `replace_text` 忽略 `para_id` 做全文档搜索 [P0]

**状态（2026-11-02 复核）**：✅ FIXED — commit `6d393a5`（合入 `f5face8`）

**现象**：
```python
replace_text(para_id="71A454C5", find="【定义上式中的所有参数】", replace="...")
# → Error: Ambiguous: appears in multiple paragraphs
```
即使提供了唯一 `para_id`，工具仍先全文档搜索 `find`，再过滤 `para_id`。当多个段落包含相同文本时，全部报 `Ambiguous`。

**根本原因**：搜索顺序是 `grep(document, find)` → `filter(para_id)` 而非 `get_paragraph(para_id)` → `search_within(find)`。

**影响**：本次修订中约 15 次调用因此失败，被迫改用静默的 `update_paragraph`。

**修复**：当 `para_id` 非空时，先从 `document.xml` 定位该段落，再在其中搜索。需改动 `docx_mcp/document/` 中的搜索逻辑。

**测试**：新增 `test_security_search.py::test_replace_text_scoped_to_para_id`——创建两个不同 `para_id` 但内容完全相同的段落，验证 `replace_text` 只替换指定段落。

**工作量**：小（< 2h）

---

### Bug 2 — `compare_documents` 对含表格/图片/OMML 的文档产生损坏输出 [P0]

**状态（2026-11-02 复核）**：⬜ OPEN — 未实现（证据：`compare.py::_body_paragraphs` 仅提取 `w:p`，无 `w:tbl`/`w:drawing`/`m:oMath` 检测）

**现象**：输入代理原稿（374 段、8 图、7 表、OMML 公式），输出中表格数据散落在正文开头、图片引用错位、OMML 公式变空白段落。

**根本原因**：`compare_documents` 是纯文本段落级 LCS diff，不知道 `w:tbl`、`w:drawing`、`m:oMath` 是结构化对象。

**修复（短期）**：在 diff 前扫描文档，检测到表格(`w:tbl`)或图片(`w:drawing`)时，返回 error 提示用户用 Word 内置「审阅→比较」功能。

**修复（长期）**：实现三层 diff——表格按行列、图片按 rId、段落按文本。

**测试**：`test_compare.py::test_compare_with_tables_raises_error`

**工作量**：短期小（加检测+报错，< 1h），长期大

---

### Bug 3 — `copy_document` 后 `update_image` 写入错误 handle [P1]

**状态（2026-11-02 复核）**：✅ FIXED — commit `8fb3fa0`（合入 `5b362d8`）

**现象**：
```
open(v3) → __default__
copy_document(v4)     # __default__ 仍在 v3
update_image(rId, png) # 更新了 v3 的图片
save(v4)              # 存到 v4，但如果 sanitize_metadata 先读了磁盘 v4（旧图），就会覆盖
```

**根本原因**：`copy_document` 明确说 "The active session and source path are unchanged"，但 `update_image` 等写工具只作用于当前 handle。

**修复**：在 `copy_document` 文档中增加警告："After copying, close current handle and re-open the copy if you need to modify it." 或让 `copy_document` 返回一个新 handle。

**测试**：文档级别改进，无需测试。

**工作量**：小

---

## Phase 2：Feature 补充（建议 v0.x.0+1）

### Feature 1 — `update_paragraph` 支持 `tracked` 参数 [P0]

**状态（2026-11-02 复核）**：✅ FIXED — commit `71438c8`（合入 `3a944d0`）

**动机**：当 `replace_text` 因 Bug 1 无法使用时，`update_paragraph` 是唯一替代方案。但它是静默覆盖，代理看不到修改。

**新增签名**：
```python
def update_paragraph(
    para_id: str,
    text: str = "",
    style: str = "",
    tracked: bool = False,   # NEW
    author: str = "Claude",   # NEW
):
```
当 `tracked=True` 时：
1. 读取段落当前文本
2. 用 `tracked=True` 的 `delete_text` 逻辑删除旧文本
3. 用 `tracked=True` 的 `insert_text` 逻辑插入新文本

**测试**：`test_paragraph_crud.py::test_update_paragraph_tracked_creates_revision`

**工作量**：中（< 4h）

---

### Feature 2 — 补齐 `document_handle` 参数 [P1]

**状态（2026-11-02 复核）**：🟡 PARTIAL — 残余 6 个工具：`accept_all_changes`、`reject_all_changes`、`sanitize_metadata`、`find_replace_formatted`、`get_document_outline`、`convert_to_pdf`（`copy_document`/`update_image` 已由 `8fb3fa0` 补齐、原表未列；`accept_changes`/`reject_changes`/`generate_change_summary` 原表标注为缺失有误，实际早已支持）

**缺失工具**：

| 工具 | 现状 | 接口文件 |
|------|------|---------|
| `accept_changes` / `accept_all_changes` | 只支持 `__default__` | `docx_mcp/document/revisions.py` |
| `reject_changes` / `reject_all_changes` | 只支持 `__default__` | 同上 |
| `sanitize_metadata` | 只支持 `__default__` | `docx_mcp/document/metadata.py` |
| `find_replace_formatted` | 只支持 `__default__` | `docx_mcp/document/content.py` |
| `get_document_outline` | 只支持 `__default__` | `docx_mcp/document/structure.py` |
| `convert_to_pdf` | 只支持 `__default__` | `docx_mcp/document/` |
| `generate_change_summary` | 只支持 `__default__` | `docx_mcp/document/revisions.py` |

**修复**：每个工具增加 `document_handle: str = ""` 参数，`""` 表示 `__default__`。

**测试**：每个工具增加 `test_xxx_with_handle_parameter`

**工作量**：中（< 6h，7 个工具）

---

### Feature 3 — `save_document` 集成 sanitize [P2]

**状态（2026-11-02 复核）**：⬜ OPEN — 未实现（证据：`docx_mcp/**` 中 `sanitize_level` 零命中）

**签名扩展**：
```python
def save_document(
    output_path: str = "",
    document_handle: str = "",
    sanitize_level: int = 0,            # NEW: 0=none, 1/2/3
    redact_authors_as: str = "Anonymous" # NEW
):
```

**动机**：消除 save → close → open → sanitize → close 的四步操作。

**工作量**：小（< 1h）

---

## Phase 3：设计优化（建议 v0.x.0+2）

### Design 1 — `replace_text` 增加 `replace_all` 参数

**状态（2026-11-02 复核）**：⬜ OPEN — 未实现（证据：`docx_mcp/**` 中 `replace_all` 零命中）

当同一段落内 `find` 出现多次时支持替换全部。

### Design 2 — 新增 `extract_image` 工具

**状态（2026-11-02 复核）**：⬜ OPEN — 未实现（证据：`docx_mcp/**` 中 `extract_image` 零命中）

```python
def extract_image(rId: str, output_path: str):
```
从 docx 导出单个图片到文件，方便视觉检查。

### Design 3 — `update_paragraph` → `set_paragraph_text`

**状态（2026-11-02 复核）**：⬜ OPEN — 未实现（证据：`docx_mcp/**` 中 `set_paragraph_text` 零命中）

重命名以明确「这是覆盖而非修订」。旧名保留为 deprecated alias。

---

## 优先级总览

| 优先级 | 编号 | 类别 | 修复收益 | 状态（2026-11-02 复核） |
|--------|------|------|---------|------------------------|
| **P0** | Bug 1 | Bug | 消除 30% 的 `replace_text` 失败 | ✅ FIXED（`6d393a5`） |
| **P0** | Bug 2 | Bug | 防止文档损坏 | ⬜ OPEN |
| **P0** | Feature 1 | Feature | 消除「隐形修改」风险 | ✅ FIXED（`71438c8`） |
| **P1** | Bug 3 | Bug | 消除图片丢失 | ✅ FIXED（`8fb3fa0`） |
| **P1** | Feature 2 | Feature | 启用多文档并发 | 🟡 PARTIAL（残余 6 工具） |
| **P2** | Feature 3 | Feature | 减少操作步骤 | ⬜ OPEN |
| **P3** | Design 1-3 | Design | UX 改善 | ⬜ OPEN |

> **复核说明（2026-11-02）**：以上状态依据当前 `HEAD` 的代码与 git 证据重测，不沿用过期 PM 状态；原文引用的行号已漂移，一律改用符号锚（详见 `.github/reviews/defect-roadmap-verification-2026-07-27.md` 的「状态更新（2026-11-02 复核）」小节）。路线图外新增（待回写）：`DOCX_MCP_REQUIRE_HANDLE` 环境门控、`save_document` 保留 structural/pinned notes、PDF 导出超时与 stdin 隔离（commit `61d390c` / `6706fe0` / `ec5fcd7`）。
