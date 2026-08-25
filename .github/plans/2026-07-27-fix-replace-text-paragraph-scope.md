# Plan: Remove document-global uniqueness guard from _resolve() in replace_text/delete_text/insert_text

| 字段 | 值 |
|------|-----|
| **GitHub Issue** | https://github.com/SecurityRonin/docx-mcp/issues/6 |
| **PM Task** | #2114 |
| **Branch** | `fix/issue-6-replace-text-paragraph-scope` |
| **Plan Type** | HOLD (bug fix — 严格保持范围不扩不缩) |
| **Generated** | 2026-07-27 |
| **Git Commit** | b141be8 |
| **Files SHA256** | `tracks.py`: 待变更后更新 |

---

## 背景与目标

- **问题**：`replace_text(para_id="...", find="...", replace="...")` 即使调用者提供了明确的 `para_id` 且目标段内文本唯一，仍因 `_resolve()` 中的 `_doc_norm_count()` 全局检查而抛出 `"Ambiguous: ... appears in multiple paragraphs"`。
- **根因**：`_resolve(doc, para, find, ...)` 接收已由 `_find_para(doc, para_id)` 解析出的具体段落 `para`，但在 Strategy 4 分支中额外调用 `_doc_norm_count(doc, norm_find)` 扫描全文，重写了调用方已缩小的范围。
- **目标**：删除 `_resolve()` 中的跨文档模糊度门禁（`tracks.py` 第 288-293 行），同时保留段落内模糊度检查及全部四种上下文锚定策略。
- **非目标**：不修改 `_doc_norm_count` 函数本身（后续可被 `search_text` 复用）；不改变 `_resolve` 的函数签名；不在本次修改中重构其他调用方。

---

## 修改方案

### 方案概述

对一个函数的内部实现做**纯减法操作**（删除 4 行），不新增任何逻辑路径：

```diff
-    # Unique in this paragraph — verify document-global uniqueness
-    if _doc_norm_count(doc, norm_find, ignore_case=ignore_case) > 1:
-        raise ValueError(
-            f"Ambiguous: {find!r} appears in multiple paragraphs; "
-            "provide context_before or context_after"
-        )
     match = m[0]
```

### 影响范围

| 层面 | 范围 |
|------|------|
| **函数** | `_resolve()` 中 Strategy 4 分支（`tracks.py:288-293`） |
| **受影响调用方** | `replace_text`、`delete_text`、`insert_text`（全部三个均受益，因为全部三个在调用 `_resolve` 前都已解析 `para_id`） |
| **不受影响** | 四种上下文锚定策略、段落内模糊度检查（同一段落内重复出现且无上下文 → 仍会出错） |
| **保留** | `_doc_norm_count` 函数不删除，以备 `search_text` 将来使用 |

### 行为矩阵

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| 段落内唯一 + 文档内重复 | ❌ `ValueError: appears in multiple paragraphs` | ✅ 成功 |
| 段落内多次出现 + 无上下文 | ❌ `ValueError: found N times in paragraph` | ❌ 不变 |
| 目标段落不存在 | ❌ `ValueError: paragraph not found` | ❌ 不变 |
| 段落内唯一 + 文档内唯一 | ✅ 成功 | ✅ 不变 |

---

## 执行计划

### Phase 1: 分支创建与代码修改

#### Task 1.1: 创建 feature 分支

- **目标**：从 `upstream/main` 创建 `fix/issue-6-replace-text-paragraph-scope` 分支
- **依赖**：无
- **执行者**：Developer
- **修改内容**：
  - 执行 `git checkout -b fix/issue-6-replace-text-paragraph-scope upstream/main`
- **修改边界**：不修改任何文件
- **验收标准**：
  - ✅ `git branch --show-current` 输出 `fix/issue-6-replace-text-paragraph-scope`
  - ✅ `git merge-base HEAD upstream/main` 等于 `b141be8`

#### Task 1.2: 删除 _resolve() 中的 _doc_norm_count 门禁

- **目标**：从 `_resolve()` Strategy 4 分支移除跨文档模糊度检查
- **依赖**：T1.1
- **执行者**：Developer
- **修改内容**：
  - 文件 `docx_mcp/document/tracks.py`：删除第 288-293 行（从 `# Unique in this paragraph` 注释到 `match = m[0]` 之前一行）
- **修改边界**：不得改动文件中的任何其他行；不得修改 `_doc_norm_count` 函数；不得改动 `_resolve` 函数签名
- **质量检查方式**：
  - `python3 -c "from docx_mcp.document.tracks import _doc_norm_count; print('OK')"` — 确认函数仍存在
  - `python3 -c "from docx_mcp.document.tracks import _resolve; print('OK')"` — 确认函数可导入
  - `grep -c "_doc_norm_count" docx_mcp/document/tracks.py` — 预期输出 `2`（函数定义一行 + 所有可能在注释中的一处引用）
- **验收标准**：
  - ✅ 代码 diff 仅涉及 `tracks.py`，且仅含 4 行删除
  - ✅ `_doc_norm_count` 导入仍成功（后续使用不受影响）

### Phase 2: 测试

#### Task 2.1: 新增测试：多段落重复文本 + para_id 仍可成功替换

- **目标**：验证当同一文本在文档中出现 N 次、但调用方指定了唯一 `para_id` 时，`replace_text` 不再拒绝
- **依赖**：T1.2
- **执行者**：Developer
- **修改内容**：
  - 在 `tests/test_mike_integration.py` 末尾新增 `test_replace_text_same_phrase_multiple_paras_with_para_id_succeeds` 函数
  - 测试逻辑：
    1. 使用 `mike_corpus_docx` fixture（已知其中多个段落含 `"twelve months"`——参见 `test_replace_with_context_disambiguates` 第 175 行）
    2. `open_document` → 调用 `replace_text(para_id="00000104", find="twelve months", replace="eighteen months")`（**不传** context_before/context_after）
    3. 断言成功（不抛出 ValueError）
    4. 重新打开验证：目标段落已被替换，其他含有 `"twelve months"` 的段落不受影响
- **修改边界**：仅新增测试函数；不修改 fixture；不修改已有测试
- **验收标准**：
  - ✅ `python3 -m pytest tests/test_mike_integration.py::test_replace_text_same_phrase_multiple_paras_with_para_id_succeeds -xvs` 通过
  - ✅ 测试失败时（未应用补丁）抛出 `ValueError` 且包含 `"appears in multiple paragraphs"`

#### Task 2.2: 回归测试——运行全部已有测试

- **目标**：确认删除门禁不出破已有行为
- **依赖**：T2.1
- **执行者**：Developer
- **修改内容**：无代码修改——纯运行测试
- **修改边界**：N/A
- **质量检查方式**：
  ```bash
  python3 -m pytest tests/ -x --timeout=60 -k "not hypothesis" 2>&1 | tail -3
  ```
  预期 `passed` 数 ≥ 850（仅 hypothesis 相关测试可能跳过）
- **验收标准**：
  - ✅ 所有测试通过（0 failures），且通过数与 main 分支基线一致
  - ✅ `tests/test_mike_integration.py` 中所有已有测试通过（含 `test_replace_with_context_disambiguates`，该测试本就要求段落间无交叉污染）

### Phase 3: 提交与 PR

#### Task 3.1: 提交并推送分支

- **目标**：提交包含补丁和测试的 commit 并推送分支
- **依赖**：T2.2
- **执行者**：Developer
- **修改内容**：
  ```bash
  git add docx_mcp/document/tracks.py tests/test_mike_integration.py
  git commit -m "fix: remove document-global uniqueness guard from _resolve()

  When para_id is explicitly provided, _resolve() no longer rejects
  the operation because the same text appears in other paragraphs.
  The paragraph-level dedup (multiple matches within one paragraph
  without context) is preserved.

  Closes #6"
  git push origin fix/issue-6-replace-text-paragraph-scope
  ```
- **验收标准**：
  - ✅ Commit 信息中包含 `Closes #6`
  - ✅ `git log --oneline -1` 显示正确的 commit 信息格式
  - ✅ 分支已推送至 `origin` 远程仓库

#### Task 3.2: 创建 Pull Request

- **目标**：向上游 `SecurityRonin/docx-mcp:main` 创建 PR
- **依赖**：T3.1
- **执行者**：Developer
- **修改内容**：
  ```bash
  gh pr create \
    --repo SecurityRonin/docx-mcp \
    --head zxkjack123:fix/issue-6-replace-text-paragraph-scope \
    --base main \
    --title "fix: remove document-global uniqueness guard from _resolve()" \
    --body "## Problem

  When \`replace_text\` is called with an explicit \`para_id\`, the \`_resolve()\` function
  still performs a document-wide uniqueness check via \`_doc_norm_count()\`. If the same
  text appears in any other paragraph, the operation is rejected with:

  \`\`\`
  ValueError: Ambiguous: '<text>' appears in multiple paragraphs;
  provide context_before or context_after
  \`\`\`

  The caller already disambiguated by specifying \`para_id\` — the document-wide check
  overrides this explicit scoping.

  ## Fix

  Remove the \`_doc_norm_count\` guard from \`_resolve()\` Strategy 4.
  The paragraph-internal dedup (\"found N times in paragraph\") and all four context-anchoring
  strategies are preserved. The \`_doc_norm_count\` function itself is not deleted — it may
  serve \`search_text\` or other global-search tools in the future.

  ## Behavior change

  | Scenario | Before | After |
  |----------|--------|-------|
  | Same text in multiple paragraphs, para_id specified | ❌ rejected | ✅ succeeds |
  | Same text multiple times in one paragraph, no context | ❌ rejected | ❌ unchanged |

  Closes #6"
  ```
- **验收标准**：
  - ✅ PR 已创建并可在 `https://github.com/SecurityRonin/docx-mcp/pull/N` 访问
  - ✅ PR body 包含 `Closes #6`
  - ✅ 返回 PR URL

---

## Execution Wave

| Wave | 可并行 Task | 依赖 |
|------|------------|------|
| W1 | T1.1 | — |
| W2 | T1.2 | W1 |
| W3 | T2.1 | W2 |
| W4 | T2.2 | W3 |
| W5 | T3.1 | W4 |
| W6 | T3.2 | W5 |

（单线程 bug 修复——每一步都以来上一步的产出）

---

## Post-Execution Verification

### Automated Verification（Developer 自动执行）

| ID | Description | Command | Expected |
|----|-------------|---------|----------|
| V1 | 全部测试通过 | `python3 -m pytest tests/ -x -k "not hypothesis"` | exit 0，~850 passed |
| V2 | 新增测试覆盖多段落场景 | `python3 -m pytest tests/test_mike_integration.py::test_replace_text_same_phrase_multiple_paras_with_para_id_succeeds -xvs` | PASSED |
| V3 | _doc_norm_count 仍可导入 | `python3 -c "from docx_mcp.document.tracks import _doc_norm_count"` | exit 0（不报错） |

### Manual Verification

- [ ] M1：在 Microsoft Word 中打开含重复文本的 DOCX，验证 `replace_text` 调用后仅目标段落被替换（修订模式下可见 track changes），其他段落不受影响。

---

## 审查日志

| 轮次 | 聚焦 | 发现问题数 | 已修正 | 剩余 |
|------|------|-----------|--------|------|
| R1 | 结构完整性（4 个 tasks，明确的依赖关系） | 0 | — | 0 |
| R1.5 | 外部引用（行号 288-293 = 验证，fixture = mike_corpus_docx 已存在） | 0 | — | 0 |
| R2 | 可执行性（纯减法，零新逻辑，现有测试基线 850+ 通过） | 0 | — | 0 |
| R2.8 | LLM 可执行性（range 精确，diff 单文件，命令可直接复制粘贴） | 0 | — | 0 |
| R3 | 风险与边缘（caller 均以 para_id 开始，无回滚需求） | 0 | — | 0 |
| **终止** | **T5 — 全部 issue 清零，输出最终计划** | | | **0** |

---

## Rollback / Fix-Forward

- 修复可逆方案：revert 该 commit 即可恢复 4 行代码
- 如果 `test_replace_with_context_disambiguates`（第 157 行）在删除后失败：`_doc_norm_count` 从未断言过该测试；该测试本就是验证对特定段落的锁定，不受影响
- 如果 V2（新增测试）在未应用补丁时失败：符合预期——应抛出包含 `"appears in multiple paragraphs"` 的 `ValueError`
