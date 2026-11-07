# Plan: Add document_handle support to copy_document and update_image

| 字段 | 值 |
|------|-----|
| **GitHub Issue** | https://github.com/SecurityRonin/docx-mcp/issues/8 |
| **PM Task** | #2116 |
| **Branch** | `fix/issue-8-copy-document-and-update-image-handle` |
| **Plan Type** | HOLD (bug fix — 严格保持范围不扩不缩) |
| **Generated** | 2026-07-28 |
| **Git Commit** | 3a944d0 (your main) |

---

## 背景与目标

- **问题**：`copy_document` 和 `update_image` 使用 `_require_doc()`（锁定 `__default__` slot），在多文档并行会话场景下，这两个工具只能操作默认文档而非调用方指定的 handle。
- **根本原因**：PR #2 引入 `_resolve(handle)` 基础设施后，这两个工具未被迁移到新模式。
- **目标**：为 `copy_document` 和 `update_image` 增加 `document_handle: str = ""` 参数，将调用链从 `_require_doc()` 改为 `_resolve(document_handle)`。
- **非目标**：不修改 `ReadingMixin` 或 `ImagesMixin` 中的方法签名（mixin 层不了解 handle）；不迁移其他工具（那是 #2118 的工作）；不改变 `copy_document` 的语义（不自动 open 新 handle）。

---

## 修改方案

### 方案概述

纯 server.py 级修改：两个工具的 MCP 装饰器从 `_require_doc()` 改为 `_resolve(document_handle)`，新增 `document_handle` 参数。底层 mixin 方法（`ReadingMixin.copy_document`、`ImagesMixin.update_image`）**无需任何修改**——handle 解析由 server.py 完成。

### 参考模板（已有 `document_handle` 的工具）

```python
@mcp.tool()
def accept_changes(author: str = "", document_handle: str = "") -> str:
    """Accept tracked changes — keep insertions, remove deletions. Empty author = all."""
    _, doc = _resolve(document_handle)
    return _js(doc.accept_changes(author=author or None))
```

### 影响范围

| 层面 | 范围 |
|------|------|
| **工具签名** | `server.py:719` (update_image), `server.py:2943` (copy_document) |
| **调用链** | `_require_doc()` → `_resolve(document_handle)` |
| **不受影响** | `ReadingMixin.copy_document` (reading.py:146), `ImagesMixin.update_image` (images.py:202) |

### 修改后的工具签名

```python
@mcp.tool()
def copy_document(output_path: str, document_handle: str = "") -> str:
    """Save a complete snapshot of the open document to a new path.

    The active session and source path are unchanged.

    Args:
        output_path: Destination file path (must end in .docx).
        document_handle: Optional handle for concurrent session isolation.
            Empty string uses the shared __default__ slot.

    Returns:
        {"copied_to": output_path}
    """
    _, doc = _resolve(document_handle)
    return _js(doc.copy_document(output_path))


@mcp.tool()
def update_image(rId: str, new_image_path: str, document_handle: str = "") -> str:
    """Replace the binary for an existing image in-place.

    The image dimensions and position in the document are preserved.

    Args:
        rId: The relationship ID of the image to replace.
        new_image_path: Absolute path to the new image file on disk.
        document_handle: Optional handle for concurrent session isolation.
            Empty string uses the shared __default__ slot.
    """
    _, doc = _resolve(document_handle)
    return _js(doc.update_image(rId, new_image_path))
```

### 行为矩阵

| 调用方式 | 修复前 | 修复后 |
|----------|--------|--------|
| `copy_document(out)` | 始终操作 `__default__` | ✅ `__default__`（空 handle → `__default__`） |
| `copy_document(out, document_handle="h1")` | ❌ 不支持 | ✅ 操作 "h1" slot 的文档 |
| `update_image(rId, png)` | 始终操作 `__default__` | ✅ `__default__` |
| `update_image(rId, png, document_handle="h1")` | ❌ 不支持 | ✅ 操作 "h1" slot 的文档 |

---

## 执行计划

### Phase 1: 代码修改

#### Task 1.1: 创建 feature 分支

- **目标**：从你的 `main` 创建分支
- **依赖**：无
- **修改内容**：
  ```bash
  git checkout -b fix/issue-8-copy-document-and-update-image-handle main
  ```
- **验收标准**：
  - ✅ `git branch --show-current` = `fix/issue-8-copy-document-and-update-image-handle`

#### Task 1.2: 修改 copy_document — 新增 document_handle 参数

- **目标**：`copy_document` 支持 handle 解析
- **依赖**：T1.1
- **修改内容**：替换 `server.py:2942-2954`
- **目标代码**：
  ```python
  @mcp.tool()
  def copy_document(output_path: str, document_handle: str = "") -> str:
      """Save a complete snapshot of the open document to a new path.

      The active session and source path are unchanged.

      Args:
          output_path: Destination file path (must end in .docx).
          document_handle: Optional handle for concurrent session isolation.
              Empty string uses the shared __default__ slot.

      Returns:
          {"copied_to": output_path}
      """
      _, doc = _resolve(document_handle)
      return _js(doc.copy_document(output_path))
  ```
- **验收标准**：
  - ✅ 空 handle 时行为与 main 分支完全一致

#### Task 1.3: 修改 update_image — 新增 document_handle 参数

- **目标**：`update_image` 支持 handle 解析
- **依赖**：T1.1
- **修改内容**：替换 `server.py:718-728`
- **目标代码**：
  ```python
  @mcp.tool()
  def update_image(rId: str, new_image_path: str, document_handle: str = "") -> str:
      """Replace the binary for an existing image in-place.

      The image dimensions and position in the document are preserved.

      Args:
          rId: The relationship ID of the image to replace.
          new_image_path: Absolute path to the new image file on disk.
          document_handle: Optional handle for concurrent session isolation.
              Empty string uses the shared __default__ slot.
      """
      _, doc = _resolve(document_handle)
      return _js(doc.update_image(rId, new_image_path))
  ```
- **验收标准**：
  - ✅ 空 handle 时行为与 main 分支完全一致

### Phase 2: 测试

#### Task 2.1: 新增测试 — copy_document 多 handle 场景

- **目标**：验证 `copy_document` 在指定 handle 下操作正确文档
- **依赖**：T1.2
- **修改内容**：在 `tests/test_document_operations.py` 末尾新增测试函数
- **目标测试**：
  ```python
  def test_copy_document_with_explicit_handle(tmp_path):
      """copy_document can read from a non-default handle."""
      import uuid
      h1 = str(uuid.uuid4())
      h2 = str(uuid.uuid4())
      # Open two documents under different handles
      from .conftest import _build_fixture
      path1 = tmp_path / "doc1.docx"
      path2 = tmp_path / "doc2.docx"
      _build_fixture(path1)
      _build_fixture(path2)
      server.open_document(str(path1), document_handle=h1)
      server.open_document(str(path2), document_handle=h2)
      # Copy from h1
      out = tmp_path / "copy_of_h1.docx"
      result = json.loads(
          server.copy_document(str(out), document_handle=h1)
      )
      assert result["copied_to"] == str(out)
      assert out.exists()
      # h2 should be unaffected
      server.close_document(document_handle=h1)
      server.close_document(document_handle=h2)
  ```
- **验收标准**：
  - ✅ 测试通过

#### Task 2.2: 新增测试 — update_image 多 handle 场景

- **目标**：验证 `update_image` 在指定 handle 下替换正确文档的图片
- **依赖**：T1.3
- **修改内容**：在 `tests/test_image_management.py` 末尾新增测试函数
- **目标测试**：
  ```python
  def test_update_image_with_explicit_handle(test_docx, tmp_path):
      """update_image can target a non-default handle."""
      import uuid
      h1 = str(uuid.uuid4())
      doc = server.open_document(str(test_docx), document_handle=h1)
      # Get image rId
      images = json.loads(server.get_images(document_handle=h1))
      assert len(images) > 0, "test document must have an image"
      rId = images[0]["rId"]
      # Create a replacement image
      new_img = tmp_path / "replacement.png"
      from PIL import Image
      Image.new("RGB", (10, 10), "blue").save(new_img)
      # Update via explicit handle
      result = json.loads(
          server.update_image(rId, str(new_img), document_handle=h1)
      )
      assert result["rId"] == rId
      server.close_document(document_handle=h1)
  ```
- **验收标准**：
  - ✅ 测试通过

#### Task 2.3: 回归测试

- **目标**：确认全量测试套件无回归
- **依赖**：T2.1, T2.2
- **质量检查方式**：
  ```bash
  python3 -m pytest tests/ -x --timeout=60 --ignore=tests/test_security_guards.py --ignore=tests/test_pii.py -k "not hypothesis"
  ```
- **验收标准**：
  - ✅ 通过数 ≥ 1106（与本次修复前基线一致）

### Phase 3: 提交与 PR

#### Task 3.1: 提交、推送、合并到 main

- **目标**：提交并推送，合并到 main
- **依赖**：T2.3
- **修改内容**：
  ```bash
  git add docx_mcp/server.py tests/
  git commit -m "fix(server): [PM#2116] add document_handle to copy_document and update_image

  Both tools now accept document_handle: str = '' for concurrent
  session isolation. Empty string continues to use __default__ slot.

  Closes #8"
  git push origin fix/issue-8-copy-document-and-update-image-handle
  git checkout main
  git merge fix/issue-8-copy-document-and-update-image-handle --no-ff -m "merge: fix/issue-8-copy-document-and-update-image-handle"
  git push origin main
  ```
- **验收标准**：
  - ✅ `main` 包含修复
  - ✅ 分支保留用于 upstream PR

#### Task 3.2: 创建 upstream PR

- **目标**：向上游提交 PR
- **依赖**：T3.1
- **修改内容**：
  ```bash
  gh pr create \
    --repo SecurityRonin/docx-mcp \
    --head zxkjack123:fix/issue-8-copy-document-and-update-image-handle \
    --base main \
    --title "fix: add document_handle to copy_document and update_image" \
    --body "## Problem

  \`copy_document\` and \`update_image\` use \`_require_doc()\` which
  always resolves to the \`__default__\` slot. This prevents
  parallel-session workflows from using these tools on non-default
  handles.

  ## Fix

  Both tools now accept \`document_handle: str = \"\"\` and resolve
  via \`_resolve(document_handle)\` instead of \`_require_doc()\`.
  Empty string = \`__default__\` (fully backward compatible).

  Closes #8"
  ```
- **验收标准**：
  - ✅ PR 已创建

---

## Execution Wave

| Wave | 可并行 Task | 依赖 |
|------|------------|------|
| W1 | T1.1 | — |
| W2 | T1.2, T1.3 | W1 |
| W3 | T2.1, T2.2 | W2 |
| W4 | T2.3 | W3 |
| W5 | T3.1 | W4 |
| W6 | T3.2 | W5 |

---

## Post-Execution Verification

| ID | Description | Command | Expected |
|----|-------------|---------|----------|
| V1 | 全量测试 | `pytest tests/ --ignore=tests/test_security_guards.py --ignore=tests/test_pii.py -k "not hypothesis"` | ≥1106 passed |
| V2 | 空 handle 兼容 | `copy_document(out)` 仍然工作 | 行为与修复前一致 |

---

## 审查日志

| 轮次 | 聚焦 | 发现问题数 | 已修正 | 剩余 |
|------|------|-----------|--------|------|
| R1 | 结构完整性（2 个工具，3 个 Phase，依赖明确） | 0 | — | 0 |
| R1.5 | 外部引用（`_resolve` = server.py:51，`get_images` = 已有 handle 支持的模板，mixin 方法无需修改） | 0 | — | 0 |
| R2 | 可执行性（纯签名变更，零逻辑新增，每个 task 可独立验证） | 0 | — | 0 |
| R2.8 | LLM 可执行性（文件路径 + 行号精确，diff 可直接复制，命令无歧义） | 0 | — | 0 |
| R3 | 风险与边缘（空 handle → `__default__` = 完全向后兼容；仅 server.py 变更 = mixin 层不受影响） | 0 | — | 0 |
| **终止** | **T5 — 全部 issue 清零，输出最终计划** | | | **0** |
