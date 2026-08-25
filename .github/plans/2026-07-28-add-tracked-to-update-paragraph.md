# Plan: Add tracked parameter to update_paragraph for revision markup

| 字段 | 值 |
|------|-----|
| **GitHub Issue** | https://github.com/SecurityRonin/docx-mcp/issues/9 |
| **PM Task** | #2117 |
| **Branch** | `feat/issue-9-update-paragraph-tracked` |
| **Plan Type** | HOLD (feature — 严格控制在 update_paragraph 范围内) |
| **Generated** | 2026-07-28 |
| **Git Commit** | f5face8 (your main) |

---

## 背景与目标

- **问题**：`update_paragraph` 在 `replace_text` 失败时作为唯一的段落级替换 fallback，但它是**静默覆盖**——不产生任何 tracked-change 标记。reviewer 看不到修改内容。
- **目标**：新增 `tracked: bool = False` 和 `author: str = "Claude"` 参数。当 `tracked=True` 时，旧文本用 `w:del` 包裹，新文本用 `w:ins` 包裹，产生完整的修订标记。
- **非目标**：不跟踪 style 变更（style 是段落级别属性，非内容级）；不支持 `document_handle`（那是 #2118 的工作）；不新增 `replace_all` 参数。

---

## 修改方案

### 方案概述

在 `update_paragraph` 内部增加一个分支：当 `tracked=True` 时走修订路径，`tracked=False` 保持现有行为。

**修订路径逻辑**：
```
1. 读取段落中所有现有 w:r 元素
2. 将每个 w:r 中的 w:t 改为 w:delText，然后包裹在 w:del 中（复用同一 del_id）
3. 构建 w:ins 元素，包裹新的 w:r>w:t（新文本），追加到段落末尾
```

### 影响范围

| 层面 | 范围 |
|------|------|
| **工具签名** | `server.py:2310` — 新增 `tracked` 和 `author` 参数 |
| **核心实现** | `docx_mcp/document/formatting.py:140` — 新增 tracked 分支 |
| **已有依赖** | `_now_iso`、`_preserve`（已导入 formatting.py）；`_next_markup_id`（通过 TracksMixin 的 MRO 可用） |

### 涉及文件

| 文件 | 变更类型 |
|------|----------|
| `docx_mcp/document/formatting.py` | 新增 ~35 行 tracked 分支 |
| `docx_mcp/server.py` | 新增 2 个参数 + docstring |
| `tests/test_paragraph_crud.py` | 新增 2 个测试 |

### 行为矩阵

| 场景 | 修复前 | 修复后 `tracked=False` | 修复后 `tracked=True` |
|------|--------|------------------------|----------------------|
| 文本变更 | 静默覆盖（w:r 删除+新建） | ✅ 不变 | ✅ w:del(旧) + w:ins(新) |
| style 变更 | 静默更新 w:pStyle | ✅ 不变 | ✅ 不变（style 不跟踪） |
| 文本+style 变更 | 文本静默 + style 静默 | ✅ 不变 | ✅ w:del/w:ins 跟踪文本，style 静默 |
| 仅 style 变更 | 静默更新 | ✅ 不变 | ✅ 不变（无文本变更，无需跟踪） |

---

## 执行计划

### Phase 1: 代码修改

#### Task 1.1: 创建 feature 分支

- **目标**：从你的 `main` 创建 `feat/issue-9-update-paragraph-tracked` 分支
- **依赖**：无
- **修改内容**：
  ```bash
  git checkout -b feat/issue-9-update-paragraph-tracked main
  ```
- **验收标准**：
  - ✅ `git branch --show-current` = `feat/issue-9-update-paragraph-tracked`
  - ✅ `git merge-base HEAD main` = `f5face8`

#### Task 1.2: 修改 formatting.py — 新增 tracked 分支

- **目标**：在 `update_paragraph` 中新增 `tracked` 和 `author` 参数，实现修订标记路径
- **依赖**：T1.1
- **修改内容**：
  - 修改 `FormattingMixin.update_paragraph()` 签名，新增参数
  - 在文本变更路径中新增 `if tracked:` 分支
- **修改边界**：不得修改 style 变更路径；不得修改 `update_paragraph` 的返回值结构；不得引入新的外部依赖

**目标代码**（`formatting.py:140-171`）：

```python
def update_paragraph(
    self,
    para_id: str,
    text: str | None = None,
    style: str | None = None,
    tracked: bool = False,
    author: str = "Claude",
) -> dict:
    doc = self._require("word/document.xml")
    para = self._find_para(doc, para_id)
    if para is None:
        raise ValueError(f"Paragraph '{para_id}' not found")

    if text is not None:
        if tracked:
            # ── Tracked: wrap existing runs in w:del, append w:ins ──────
            cid = self._next_markup_id(doc)
            now = _now_iso()

            # Wrap each existing w:r in w:del
            for run in list(para.findall(f"{W}r")):
                para.remove(run)
                # Convert w:t → w:delText inside runs
                for t_el in run.iter(f"{W}t"):
                    t_el.tag = f"{W}delText"
                del_el = etree.Element(f"{W}del")
                del_el.set(f"{W}id", str(cid))
                del_el.set(f"{W}author", author)
                del_el.set(f"{W}date", now)
                del_el.append(run)
                para.append(del_el)

            # Append w:ins with new text
            ins_cid = self._next_markup_id(doc)
            ins_el = etree.Element(f"{W}ins")
            ins_el.set(f"{W}id", str(ins_cid))
            ins_el.set(f"{W}author", author)
            ins_el.set(f"{W}date", now)
            new_run = etree.SubElement(ins_el, f"{W}r")
            new_t = etree.SubElement(new_run, f"{W}t")
            _preserve(new_t, text)
            para.append(ins_el)
        else:
            # ── Silent: existing behavior ───────────────────────────────
            for run in list(para.findall(f"{W}r")):
                para.remove(run)
            run = etree.SubElement(para, f"{W}r")
            t_el = etree.SubElement(run, f"{W}t")
            _preserve(t_el, text)

    if style is not None:
        ppr = para.find(f"{W}pPr")
        if ppr is None:
            ppr = etree.Element(f"{W}pPr")
            para.insert(0, ppr)
        pstyle = ppr.find(f"{W}pStyle")
        if pstyle is None:
            pstyle = etree.Element(f"{W}pStyle")
            ppr.insert(0, pstyle)
        pstyle.set(f"{W}val", style)

    if text is not None or style is not None:
        self._mark("word/document.xml")
    return {"para_id": para_id}
```

- **验收标准**：
  - ✅ 当 `tracked=False` 时行为与 main 分支完全一致
  - ✅ 当 `tracked=True` 时段落 XML 包含 `w:del>w:r>w:delText`（旧文本）+ `w:ins>w:r>w:t`（新文本）
  - ✅ `del_id` 跨多个旧 w:r 元素复用（同一 del 操作）

#### Task 1.3: 修改 server.py — 新增参数

- **目标**：在工具签名中暴露 `tracked` 和 `author` 参数
- **依赖**：T1.2
- **修改内容**：
  ```python
  @mcp.tool()
  def update_paragraph(
      para_id: str,
      text: str = "",
      style: str = "",
      tracked: bool = False,
      author: str = "Claude",
  ) -> str:
      """Update the text and/or style of an existing paragraph.

      Args:
          para_id: paraId of the paragraph to update.
          text: New text content. Empty string leaves text unchanged.
          style: New paragraph style name. Empty string leaves style unchanged.
          tracked: If True, wrap old runs in w:del and new text in w:ins.
          author: Author name shown in Word's review pane (tracked=True only).
      """
      return _js(
          _require_doc().update_paragraph(
              para_id,
              text=text or None,
              style=style or None,
              tracked=tracked,
              author=author,
          )
      )
  ```
- **验收标准**：
  - ✅ MCP 工具签名包含 `tracked` 和 `author` 参数
  - ✅ `update_paragraph("x", text=None, style=None)` 仍然兼容（无参数破坏性变更）

### Phase 2: 测试

#### Task 2.1: 新增测试 — tracked=True 产生修订标记

- **目标**：验证 `tracked=True` 在 OOXML 中产生正确的 w:del 和 w:ins
- **依赖**：T1.3
- **修改内容**：在 `tests/test_paragraph_crud.py` 中新增两个测试：

  **测试 2.1a** `test_update_paragraph_tracked_produces_del_and_ins`
  ```python
  def test_update_paragraph_tracked_produces_del_and_ins(test_docx: Path) -> None:
      """tracked=True wraps old text in w:del and new text in w:ins."""
      server.open_document(str(test_docx))
      server.update_paragraph("00000002", text="Tracked replacement", tracked=True)
      # Verify via get_tracked_changes
      changes = json.loads(server.get_tracked_changes())
      assert len(changes) >= 2  # at least one deletion + one insertion
      assert any(c["type"] == "deletion" for c in changes)
      assert any(c["type"] == "insertion" for c in changes)
  ```

  **测试 2.1b** `test_update_paragraph_tracked_false_unchanged`
  ```python
  def test_update_paragraph_tracked_false_unchanged(test_docx: Path) -> None:
      """tracked=False (default) behaves same as before — no tracked changes."""
      server.open_document(str(test_docx))
      server.update_paragraph("00000002", text="Silent replacement")
      changes = json.loads(server.get_tracked_changes())
      assert len(changes) == 0  # no tracked changes produced
      # But the text IS replaced
      body = json.loads(server.get_body_text())["body"]
      assert "Silent replacement" in body
  ```

- **验收标准**：
  - ✅ `test_update_paragraph_tracked_produces_del_and_ins` 通过
  - ✅ `test_update_paragraph_tracked_false_unchanged` 通过

#### Task 2.2: 回归测试

- **目标**：确认已有 update_paragraph 测试仍通过
- **依赖**：T2.1
- **修改内容**：无代码修改
- **质量检查方式**：
  ```bash
  python3 -m pytest tests/test_paragraph_crud.py -xvs
  ```
- **验收标准**：
  - ✅ 全部已有测试通过（包括 `test_update_paragraph_changes_text`、`test_update_paragraph_changes_style`、`test_update_paragraph_nonexistent_raises`）

#### Task 2.3: 全量回归

- **目标**：确认全量测试套件无回归
- **依赖**：T2.2
- **质量检查方式**：
  ```bash
  python3 -m pytest tests/ -x --timeout=60 --ignore=tests/test_security_guards.py --ignore=tests/test_pii.py -k "not hypothesis"
  ```
- **验收标准**：
  - ✅ 通过数 ≥ 1100（与本次修复前基线一致）

### Phase 3: 提交与 PR

#### Task 3.1: 提交并推送分支

- **目标**：提交并推送，然后合并到你的 main
- **依赖**：T2.3
- **修改内容**：
  ```bash
  git add docx_mcp/document/formatting.py docx_mcp/server.py tests/test_paragraph_crud.py
  git commit -m "feat(formatting): [PM#2117] add tracked parameter to update_paragraph

  When tracked=True, wraps existing w:r elements in w:del and appends
  new text in w:ins, producing proper revision markup.
  tracked=False preserves the existing silent-update behavior.

  Closes #9"
  git push origin feat/issue-9-update-paragraph-tracked
  ```
- **验收标准**：
  - ✅ 分支已推送至 origin
  - ✅ Commit 信息包含 `Closes #9`

#### Task 3.2: 合并到你的 main

- **目标**：将修复合并到你的 main 分支
- **依赖**：T3.1
- **修改内容**：
  ```bash
  git checkout main
  git merge feat/issue-9-update-paragraph-tracked --no-ff -m "merge: feat/issue-9-update-paragraph-tracked into main"
  git push origin main
  ```
- **验收标准**：
  - ✅ `main` 包含新功能
  - ✅ 分支 `feat/issue-9-update-paragraph-tracked` 保留（用于 upstream PR）

#### Task 3.3: 创建 upstream PR

- **目标**：向上游提交 PR
- **依赖**：T3.1
- **修改内容**：
  ```bash
  gh pr create \
    --repo SecurityRonin/docx-mcp \
    --head zxkjack123:feat/issue-9-update-paragraph-tracked \
    --base main \
    --title "feat: add tracked parameter to update_paragraph" \
    --body "## Summary

  Adds \`tracked: bool = False\` and \`author: str = \"Claude\"\` parameters
  to \`update_paragraph\`. When \`tracked=True\`, existing runs are wrapped
  in \`w:del\` and the new text is appended as \`w:ins\`, producing proper
  Word revision markup.

  ## Behavior

  | Scenario | Before | After | After tracked=True |
  |----------|--------|-------|-------------------|
  | Text change | Silent w:r replace | ✅ unchanged | ✅ w:del(old) + w:ins(new) |
  | Style change | Silent pStyle update | ✅ unchanged | ✅ unchanged |

  Closes #9"
  ```
- **验收标准**：
  - ✅ PR 已创建

---

## Execution Wave

| Wave | 可并行 Task | 依赖 |
|------|------------|------|
| W1 | T1.1 | — |
| W2 | T1.2, T1.3 | W1 |
| W3 | T2.1 | W2 |
| W4 | T2.2, T2.3 | W3 |
| W5 | T3.1 | W4 |
| W6 | T3.2 | W5 |
| W7 | T3.3 | W5 |

---

## Post-Execution Verification

| ID | Description | Command | Expected |
|----|-------------|---------|----------|
| V1 | 全量测试 | `pytest tests/ --ignore=tests/test_security_guards.py --ignore=tests/test_pii.py -k "not hypothesis"` | ≥1104 passed |
| V2 | tracked 变更验证 | 打开 DOCX 于 Word 中 → 修订模式下可见 w:del(旧) + w:ins(新) | 手工 |
| V3 | silent 行为不变 | `pytest tests/test_paragraph_crud.py -xvs` | 所有已有测试通过 |

---

## 审查日志

| 轮次 | 聚焦 | 发现问题数 | 已修正 | 剩余 |
|------|------|-----------|--------|------|
| R1 | 结构完整性（3 个 Phase，8 个 tasks，依赖明确） | 0 | — | 0 |
| R1.5 | 外部引用（`_next_markup_id` 通过 MRO 可用，`W`/`_now_iso`/`_preserve` 已导入，行号锚点已验证） | 0 | — | 0 |
| R2 | 可执行性（每个 task 有具体 diff、命令、验收标准） | 0 | — | 0 |
| R2.8 | LLM 可执行性（文件路径精确到行号，PYTHON diff 可直接复制，命令可粘贴执行） | 0 | — | 0 |
| R3 | 风险与边缘（style 不变更不跟踪 = 安全；仅 text=None 时不进入 tracked 分支 = 安全；MRO 中没有 `_next_markup_id` 冲突 = 安全） | 0 | — | 0 |
| **终止** | **T5 — 全部 issue 清零，输出最终计划** | | | **0** |
