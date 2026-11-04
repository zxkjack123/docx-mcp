# Plan: #2118 剩余 158 个工具 `document_handle` 分批迁移

| 字段 | 值 |
|------|-----|
| **Status** | ✅ **COMPLETED**（Phase 1 六批迁移 + Phase 2 收尾验收全部完成；2026-11-03 归档，证据见 §13 执行日志） |
| **PM Task** | #2118（本计划完成剩余 158 工具；完成后可达 164/164） |
| **Workspace** | `/home/gw/opt/docx-mcp`（唯一允许改动仓库） |
| **计划文件** | `.github/plans/completed/remaining-handles.md`（2026-11-03 归档前位于 `.github/plans/remaining-handles.md`） |
| **生成日期** | 2026-11-03（`date` 实测；执行时重测） |
| **Scope Mode** | HOLD（缺陷收尾 / 机械迁移，不扩范围） |
| **输入** | `/tmp/opencode/deploy2118/inventory.json`（219 工具 AST inventory） |
| **目标文件** | `docx_mcp/server.py`、`tests/test_remaining_handles.py`、`docs/notes/remaining-handles-b*.md` |
| **每批约束** | ≤30 工具 / ≤20 min 墙钟；批次间**严格串行**（共享同一测试文件与 server.py） |
| **提交** | 每批 1 次 commit，message 带 `#T-2118` |

> 路径澄清：仓库内不存在根目录 `server.py`；任务语义中的 `server.py` = `docx_mcp/server.py`（已实测确认）。

---

## 1. 需求理解（CoT Stage 1）

```
REQUIREMENT（逐字）: 158 pending 来自 /tmp/opencode/deploy2118/inventory.json，
按每批≤30工具≤20min 依赖串行；每批允许文件 server.py、tests/test_remaining_handles.py、
docs/notes/remaining-handles.md（note 每批独立路径）；每批 commit #T-2118；
验收 mock 路由参数测试先 RED 后 GREEN + pytest 全量 + ruff；
用 AST inventory 确定调用与缺参数；全部函数无 varargs 无 kwargs；
所有工具通过 _resolve(document_handle)[1]；每批工具清单作为测试参数（不预放未来批次）。
完成 158 后验收 AST pending=0 及 HTTP schema + 服务重启。
2119 与 4271 为独立后续阶段，仅在拿到 AC 后实施。
↓
CONSTRAINTS: 只改 docx_mcp/server.py + tests/test_remaining_handles.py + 每批独立 note；
  批次串行；每批 ≤30 工具 ≤20 min；每批 RED→GREEN + 全量 pytest + ruff；mock 路由测试。
↓
BOUNDARY:
  IN  : 158 个「无 document_handle 且 body 调用 _require_doc()」的 @mcp.tool 函数迁移。
  OUT : compare_documents / diff_to_text（无 handle 且不调用 _require_doc，不是本批语义）；
        _require_doc() 定义本身保留（兼容 shim，删除属另一任务）；
        2119 / 4271（独立阶段，需 AC 后才实施）；
        服务重启以外的部署动作（git push / 发布 / 客户端重启）。
  RATIONALE: 仅迁移 pending 集合可被 AST 机械验证；越界改动无法在本计划内验收。
↓
ACCEPTANCE（二元）:
  A1 inventory 复算 pending == 0 且 with_handle == 217（219 工具中 2 个天然无 handle）。
  A2 tests/test_remaining_handles.py 全绿（474 参数化用例）。
  A3 uv run pytest 全量 exit 0；uv run ruff check . / ruff format --check . exit 0。
  A4 服务重启后 HTTP tools/list 显示 219 工具，且 158 个迁移工具 inputSchema 含可选
     document_handle（不在 required 内）。
```

## 2. Clarify Gate

| # | 项 | 判定 |
|---|----|------|
| 1 | 边界条件 | PASS — 工具全集由 AST inventory 固定为 158，不算「支持 X」类模糊需求 |
| 2 | 验收标准 | PASS — 已转为可执行命令与计数（见 §1 ACCEPTANCE） |
| 3 | 隐含依赖 | PASS — 无外部依赖；仅依赖仓库内 server.py 与 `.venv` |
| 4 | 多义术语 | 已消解：`server.py` = `docx_mcp/server.py`；`note` = 每批独立 `docs/notes/remaining-handles-bN.md` |
| 5 | 冲突约束 | PASS — 「≤30 工具」与「≤20 min」在脚本化迁移下兼容（见 §4 CoT Stage 3） |

`[Clarify Gate: PASS — 无未决冲突；以下假设均已在仓库实测]`

## 3. 假设与实测基线（执行前重测，禁止沿用）

| # | 假设 | 实测证据 | 若不成立 |
|---|------|---------|---------|
| H1 | 158 pending = 无 handle 且 body 含 `_require_doc()` | `inventory.py` 过滤 `not has_handle and calls_require` → 158 | 以执行时 inventory 复算为准 |
| H2 | 全部 158 函数无 `*args` / `**kwargs` / 无必需 kwonly | inventory：`has_kwargs=0`、`has_varargs=0`、`kwonly_required=[]` | 若出现，该函数移出批次单独评审 |
| H3 | 全部 158 函数体为 `doc = _require_doc()` 或 `_require_doc().<同名方法>(...)` 的单一调用 | AST walk：method 名与工具名 0 处不一致；`_require_doc()` 每函数恰 1 次 | 若某函数非平凡，改手工编辑并记录 |
| H4 | 加 `document_handle: str = ""` 到形参末尾不会破坏调用 | 全部函数无 kwonly、无 varargs，追加默认参数合法（已用 158 函数全量试跑验证） | 语法失败即停并升级 |
| H5 | 现有 3 个 priority 工具（accept_all_changes 等）已迁移，属 164 总数 | commit `0b5b9df` + inventory `with_handle=59` | — |
| H6 | note 每批独立路径可避免「已提交 note 被冻结」 | 用户指令 + priority note 已被 commit 0b5b9df 固化 | 仍冲突则改用 `docs/notes/remaining-handles-bN-<sha8>.md` |

基线复测命令（Phase 0 第一步，全部只读）：

```bash
date
git -C /home/gw/opt/docx-mcp rev-parse HEAD
git -C /home/gw/opt/docx-mcp status --porcelain
python3 /tmp/opencode/deploy2118/inventory.py   # 期望 pending=158, with_handle=59
grep -c '_require_doc()' docx_mcp/server.py     # 期望 159（158 调用 + 1 定义）
```

## 4. 方案设计（CoT Stage 3 — 关键取舍）

```
DECISION 1: 用 AST 引导的幂等改写脚本做批量迁移，而非逐函数手工 edit
ALTERNATIVES: (a) 158×3 次手工 edit；(b) 纯 sed 正则替换
RATIONALE: 脚本按函数 AST span 精确定位，只改签名/调用/文档串；(a) 太慢且易漏，
(b) 会误伤 _require_doc 定义与 docstring 引用。
RISK: 生成排版不合法 → 每次改完强制 `uv run ruff format docx_mcp/server.py` + `ast.parse`；
      脚本已在临时副本上对全部 158 函数试跑通过（见 H4）。

DECISION 2: 每批 30 工具（6 批：30×5 + 8），而非 20 工具 ×8 批
ALTERNATIVES: 20/批（8 批）、16/批（10 批）
RATIONALE: 脚本使单批编辑成本≈常数；全量 pytest 是每批固定开销，批数越少总墙钟越低。
RISK: 单批若超 20 min → 按 §9 降级规则就地拆半，不重跑已完成批次。

DECISION 3: 测试用「累加 CASES 列表」而非每批独立列表
ALTERNATIVES: 每批单独 CASES_BN + 独立测试函数
RATIONALE: 一个 CASES + 3 个参数化测试即可，未来批次**只 append 本批行**；
      不预放未来批次 → 不会出现「已写测试但实现未到」的红测试阻断。
RISK: 追加顺序错/重复 → 由 AST 断言与 pytest collection 数量校验兜底。

DECISION 4: 路由测试以 Mock + `_docs` 注入（沿用 priority 模式），而非真实 docx 往返
ALTERNATIVES: 每工具构造真实文档（慢、脆）
RATIONALE: 5 个既有 priority 用例已证明该模式可捕获「未迁移」与「路由串档」两类缺陷；
      RED 阶段失败原因明确为 TypeError: unexpected keyword argument 'document_handle'。
RISK: Mock 掩盖底层语义 → 底层操作由既有全量测试覆盖，本测试只断言 dispatch。
```

## 5. Canonical 迁移脚本（每批复用，勿改写）

> 把 `<name...>` 替换为该批工具名（§6 各 Task 已给出完整命令）。脚本只写 `docx_mcp/server.py`；
> 幂等：已迁移函数跳过；未知名字 exit 1。执行后**必须**跑 `uv run ruff format docx_mcp/server.py`。

```bash
python3 - docx_mcp/server.py <name1> <name2> ... <<'PY'
"""Idempotent handle migration for named @mcp.tool functions in docx_mcp/server.py."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ARGS = [a for a in sys.argv[1:] if not a.endswith(".py")]
PATH = Path(next((a for a in sys.argv[1:] if a.endswith(".py")), "docx_mcp/server.py"))
NAMES = set(ARGS)
HANDLE_LINE = 'document_handle: str = ""'
DOC_NOTE = (
    "\n\n    Args (handle):\n"
    "        document_handle: Document registry handle; empty uses the legacy default."
)


def _find_matching_paren(text: str, open_idx: int) -> int:
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("unbalanced parens")


def migrate_segment(seg: str, name: str) -> str:
    open_idx = seg.index(f"def {name}(") + len(f"def {name}(") - 1
    close_idx = _find_matching_paren(seg, open_idx)
    inner = seg[open_idx + 1 : close_idx]
    line_start = seg.rfind("\n", 0, open_idx) + 1
    line = seg[line_start : open_idx + 1]
    base_indent = line[: len(line) - len(line.lstrip())]
    param_indent = base_indent + "    "
    if inner.strip():
        if inner.rstrip().endswith(","):
            new_inner = inner.rstrip() + f"\n{param_indent}{HANDLE_LINE},\n{base_indent}"
        else:
            new_inner = inner + f", {HANDLE_LINE}"
    else:
        new_inner = HANDLE_LINE
    seg = seg[: open_idx + 1] + new_inner + seg[close_idx:]
    seg = seg.replace("_require_doc()", "_resolve(document_handle)[1]")
    if '"""' in seg and "Args (handle):" not in seg:
        first = seg.index('"""')
        second = seg.index('"""', first + 3)
        line_start = seg.rfind("\n", 0, second) + 1
        indent = seg[line_start:second]
        if indent.strip() == "":
            seg = (
                seg[:line_start]
                + f"\n{indent}Args (handle):\n{indent}    document_handle: "
                "Document registry handle; empty uses the legacy default.\n"
                + indent
                + seg[second:]
            )
        else:
            seg = seg[:second] + DOC_NOTE + seg[second:]
    return seg


def main() -> int:
    src = PATH.read_text()
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    edits: list[tuple[int, int, str]] = []
    done: list[str] = []
    skipped: list[str] = []
    found: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name not in NAMES:
            continue
        found.add(node.name)
        if "document_handle" in [a.arg for a in node.args.posonlyargs + node.args.args]:
            skipped.append(node.name)
            continue
        start, end = offsets[node.lineno - 1], offsets[node.end_lineno]
        edits.append((start, end, migrate_segment(src[start:end], node.name)))
        done.append(node.name)
    for s, e, rep in sorted(edits, key=lambda t: t[0], reverse=True):
        src = src[:s] + rep + src[e:]
    missing = NAMES - found
    if skipped:
        print(f"already migrated (no-op): {sorted(skipped)}", file=sys.stderr)
    if missing:
        print(f"UNKNOWN names: {sorted(missing)}", file=sys.stderr)
    ast.parse(src)  # validate before any write: never leave a corrupt server.py
    if src != PATH.read_text():
        PATH.write_text(src)
    print(f"migrated {len(done)}: {sorted(done)}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
uv run ruff format docx_mcp/server.py
```

## 6. 测试文件设计（`tests/test_remaining_handles.py`，T1.1 创建后各批只 append）

结构（与 `tests/test_priority_handles.py` 同构，便于复用既有审查结论）：

```python
"""Handle routing regression tests for the remaining singleton tools."""

import json
from unittest.mock import Mock

import pytest

from docx_mcp import server

# 每批只 append 本批工具行；禁止预放未来批次（会引入红测试阻断）
CASES = [
    # <batch N rows>
]


@pytest.mark.parametrize("name,kwargs", CASES)
def test_remaining_handle_isolation(monkeypatch, name, kwargs):
    a, b = Mock(), Mock()
    getattr(b, name).return_value = {"selected": "B"}
    monkeypatch.setattr(server, "_docs", {"A": a, "B": b})
    monkeypatch.setattr(server, "_REQUIRE_HANDLE", True)
    result = getattr(server, name)(**kwargs, document_handle="B")
    assert json.loads(result) == {"selected": "B"}
    getattr(b, name).assert_called_once()
    assert not a.mock_calls
    with pytest.raises(RuntimeError, match="'C'"):
        getattr(server, name)(**kwargs, document_handle="C")


@pytest.mark.parametrize("name,kwargs", CASES)
def test_remaining_required_handle(monkeypatch, name, kwargs):
    monkeypatch.setattr(server, "_REQUIRE_HANDLE", True)
    with pytest.raises(RuntimeError, match="document_handle is required"):
        getattr(server, name)(**kwargs)


@pytest.mark.parametrize("name,kwargs", CASES)
def test_remaining_legacy_default(monkeypatch, name, kwargs):
    doc = Mock()
    getattr(doc, name).return_value = {"selected": "default"}
    monkeypatch.setattr(server, "_docs", {server._DEFAULT_HANDLE: doc})
    monkeypatch.setattr(server, "_REQUIRE_HANDLE", False)
    assert json.loads(getattr(server, name)(**kwargs)) == {"selected": "default"}
    assert json.loads(getattr(server, name)(**kwargs, document_handle="")) == {
        "selected": "default"
    }
```

参数行生成规则（已按 inventory 预生成，见各批 `CASES 追加行`）：对工具的全部**必填**位置参数取
`"<param>": None`；默认参数不传。`None` 仅作占位——Mock 文档对象不会校验取值，且 `_resolve` 在触碰
文档方法前完成路由。

## 7. 批次任务（Phase 1）

> 共同前置（每批第一步，强制）：`date`、`git rev-parse HEAD`、`git status --porcelain`
> （必须只有下列 3 个文件处于本批改动）；若 `docx_mcp/server.py` 出现计划外漂移 → 先更新锚点再动手。
> 共同边界：每批**只**允许写 `docx_mcp/server.py`、`tests/test_remaining_handles.py`、
> `docs/notes/remaining-handles-b<N>.md`；⛔ 不得改 `_require_doc()` 定义、不得改 `compare_documents`
> / `diff_to_text`、不得动其他测试文件、不得 `git push`。

批次按 T1.1 → T1.6 **严格串行**；每批先观察 RED，再用 §5 脚本实现，再跑 GREEN。
T1.2–T1.6 未重复的字段（修改边界 / 质量检查方式 / 验收标准模板 / 回滚 / 潜在风险）与 T1.1 相同，
仅「本批 names、CASES 行、RED/GREEN 数字、note 路径、commit message」不同。
T1.1 的**预留歧义标注**：`[ ] 无歧义——所有命令、路径、期望计数均已逐字给出`。

### Task 1.1 — Batch 1/6：30 工具迁移（表格 / 样式 / 自定义属性 / 图片）

- **目标**：创建测试文件并完成首批 30 工具的 `document_handle` 路由迁移。
- **依赖**：无
- **frontier**：是
- **执行者**：Dev Orchestrator（可直接实施；脚本已给定）
- **预估墙钟**：≤20 min（脚本编辑 ≈1 min；测试 append ≈3 min；RED/GREEN/全量/ruff ≈6–10 min）
- **修改内容**：
  1. 新建 `tests/test_remaining_handles.py`（逐字用 §6 结构）。
  2. `tests/test_remaining_handles.py` 的 `CASES` 初始化为本批 30 行（**只放本批**）：

```python
CASES = [
    ("merge_cells", {"table_index": None, "start_row": None, "start_col": None, "end_row": None, "end_col": None}),
    ("set_header_row", {"table_index": None}),
    ("set_column_widths", {"table_index": None, "widths_cm": None}),
    ("csv_to_table", {"para_id": None, "csv_text": None}),
    ("table_to_csv", {"table_index": None}),
    ("delete_table", {"table_idx": None}),
    ("add_column_to_table", {"table_idx": None}),
    ("delete_column_from_table", {"table_idx": None, "col_idx": None}),
    ("set_cell_width", {"table_idx": None, "row_idx": None, "col_idx": None, "width_mm": None}),
    ("set_cell_vertical_alignment", {"table_idx": None, "row_idx": None, "col_idx": None, "alignment": None}),
    ("set_row_height", {"table_idx": None, "row_idx": None, "height_mm": None}),
    ("set_table_alignment", {"table_idx": None, "alignment": None}),
    ("set_table_borders", {"table_idx": None}),
    ("set_cell_shading", {"table_idx": None, "row_idx": None, "col_idx": None, "fill_color": None}),
    ("set_table_style", {"table_idx": None, "style_name": None}),
    ("create_style", {"name": None, "style_type": None}),
    ("update_style", {"name": None}),
    ("delete_style", {"name": None}),
    ("get_style", {"name_or_id": None}),
    ("copy_style", {"source_name_or_id": None, "new_name": None}),
    ("apply_style_to_range", {"para_ids": None, "style_name_or_id": None}),
    ("delete_header", {}),
    ("delete_footer", {}),
    ("get_custom_properties", {}),
    ("set_custom_property", {"name": None, "value": None}),
    ("delete_custom_property", {"name": None}),
    ("insert_floating_image", {"para_id": None, "image_path": None, "width_cm": None, "height_cm": None}),
    ("delete_image", {"rId": None}),
    ("set_image_size", {"rId": None, "width_cm": None, "height_cm": None}),
    ("set_image_alt_text", {"rId": None, "alt_text": None}),
]
```

  3. **RED**：`uv run pytest tests/test_remaining_handles.py -q`
     → 期望 `60 failed, 30 passed`；失败全部为 `TypeError: ... unexpected keyword argument 'document_handle'`（isolation 30 + legacy 30；required 30 本就通过）。
  4. 用 §5 脚本迁移本批工具：把下面 **names 行**逐字接在 `python3 - docx_mcp/server.py` 之后，再接 §5 的 `<<'PY' … PY` 脚本正文；随后 `uv run ruff format docx_mcp/server.py`。

**本批 names（逐字）**：
`merge_cells set_header_row set_column_widths csv_to_table table_to_csv delete_table add_column_to_table delete_column_from_table set_cell_width set_cell_vertical_alignment set_row_height set_table_alignment set_table_borders set_cell_shading set_table_style create_style update_style delete_style get_style copy_style apply_style_to_range delete_header delete_footer get_custom_properties set_custom_property delete_custom_property insert_floating_image delete_image set_image_size set_image_alt_text`
  5. **GREEN**：`uv run pytest tests/test_remaining_handles.py -q` → exit 0，`90 passed`。
  6. 全量：`uv run pytest -q` → exit 0；`uv run ruff check . && uv run ruff format --check .` → exit 0。
  7. 新建 `docs/notes/remaining-handles-b1.md`：批次范围、30 工具名、RED/GREEN 实测数字、命令与结论。
  8. commit：`feat(handles): route 30 remaining tools through document_handle #T-2118 progress 22%`
- **修改边界**：⛔ 不改 `_require_doc()` 定义；⛔ 不改 `compare_documents` / `diff_to_text`；⛔ 不预放 B2+ 测试行；⛔ 不 `git push`。
- **质量检查方式**：AST 断言（本批 30 名均有 `document_handle` 参数且函数体无 `_require_doc()`）；测试收集数 = 90。
- **验收标准**：
  - ✅ `[T-A]` `uv run pytest tests/test_remaining_handles.py -q` → exit 0 且 `90 passed`
  - ✅ `[T-A]` `uv run pytest -q` → exit 0
  - ✅ `[T-A]` `uv run ruff check . && uv run ruff format --check .` → exit 0
  - ✅ `[T-B]` AST 断言：`assert all('document_handle' in args for batch)` 且 `assert '_require_doc()' not in body for batch`（脚本见 §8 V2）
  - ✅ `[T-C]` `git status --porcelain` 仅含 `docx_mcp/server.py`、`tests/test_remaining_handles.py`、`docs/notes/remaining-handles-b1.md`
  - **能失败证明（实现回退法）**：RED 步骤失败原因必须逐条为 `unexpected keyword argument 'document_handle'`；若某行在 RED 阶段就通过，说明该工具已被迁移或测试未覆盖 → 停并核查。
- **潜在风险**：脚本把过长签名留给 ruff format 折叠（已验证）；若某工具方法名与工具名不一致，isolation 断言会失败 → 以 §8 V2 的 method-name AST 断言提前拦截（当前实测 0 不一致）。
- **回滚**：`git checkout -- docx_mcp/server.py tests/test_remaining_handles.py`（本批未提交前）；已提交则 `git revert <sha>`。

### Task 1.2 — Batch 2/6：30 工具（图片边框 / 脚注尾注 / 页面 / 修订评论 / parts / 书签超链接）

- **依赖**：T1.1
- **frontier**：否
- **执行者**：Dev Orchestrator
- **预估墙钟**：≤20 min
- **修改内容**：追加本批 30 行到 `tests/test_remaining_handles.py` 的 `CASES` 末尾（**不预放 B3+**）：

```python
    ("set_image_border", {"rId": None, "border_pt": None}),
    ("update_footnote", {"footnote_id": None, "text": None}),
    ("delete_footnote", {"footnote_id": None}),
    ("update_endnote", {"endnote_id": None, "text": None}),
    ("delete_endnote", {"endnote_id": None}),
    ("set_page_size", {"width_mm": None, "height_mm": None}),
    ("set_page_margins", {}),
    ("set_page_orientation", {"orientation": None}),
    ("get_sections", {}),
    ("set_section_columns", {"section_index": None, "num_columns": None}),
    ("delete_section_break", {"para_id": None}),
    ("set_different_first_page", {"section_index": None, "enabled": None}),
    ("set_odd_even_headers", {"enabled": None}),
    ("accept_change", {"change_id": None}),
    ("reject_change", {"change_id": None}),
    ("update_comment", {"comment_id": None, "text": None}),
    ("delete_comment", {"comment_id": None}),
    ("resolve_comment", {"comment_id": None}),
    ("list_comment_threads", {}),
    ("scrub_pii", {}),
    ("list_parts", {}),
    ("read_part", {"part_path": None}),
    ("write_part", {"part_path": None, "xml": None}),
    ("xpath_query", {"xpath": None}),
    ("list_bookmarks", {}),
    ("add_bookmark", {"para_id": None, "name": None}),
    ("remove_bookmark", {"name": None}),
    ("get_bookmarked_text", {"name": None}),
    ("list_hyperlinks", {}),
    ("add_hyperlink", {"para_id": None, "text": None, "url": None}),
```

- **步骤**：同 T1.1（RED → §5 脚本迁移本批 → `ruff format` → GREEN → 全量 → ruff → note）。
- **本批 names（逐字接在 `python3 - docx_mcp/server.py` 之后）**：
`set_image_border update_footnote delete_footnote update_endnote delete_endnote set_page_size set_page_margins set_page_orientation get_sections set_section_columns delete_section_break set_different_first_page set_odd_even_headers accept_change reject_change update_comment delete_comment resolve_comment list_comment_threads scrub_pii list_parts read_part write_part xpath_query list_bookmarks add_bookmark remove_bookmark get_bookmarked_text list_hyperlinks add_hyperlink`
- **RED 期望**：`uv run pytest tests/test_remaining_handles.py -q` → `60 failed, 120 passed`（新增 60 失败；B1 的 90 已绿）。
- **GREEN 期望**：`180 passed`；`uv run pytest -q` exit 0。
- **note**：`docs/notes/remaining-handles-b2.md`
- **commit**：`feat(handles): route 30 remaining tools through document_handle #T-2118 progress 40%`
- **修改边界**：同 T1.1；⛔ 不预放 B3+ 行。
- **验收标准**：同 T1.1 模板（T-A 三条 + T-B AST + T-C 三文件），RED/GREEN 数字替换为本批值。

### Task 1.3 — Batch 3/6：30 工具（域 / 超链接 / 内容控件 / 模板 / 多级列表）

- **依赖**：T1.2
- **frontier**：否
- **执行者**：Dev Orchestrator
- **预估墙钟**：≤20 min
- **修改内容**：追加本批 30 行到 `CASES`：

```python
    ("add_internal_link", {"para_id": None, "text": None, "bookmark": None}),
    ("remove_hyperlink", {"para_id": None, "url_or_anchor": None}),
    ("update_hyperlink", {"r_id": None, "new_url": None}),
    ("add_field", {"para_id": None, "field_code": None}),
    ("update_fields", {}),
    ("list_fields", {}),
    ("get_field", {"field_id": None}),
    ("delete_field", {"field_id": None}),
    ("insert_date_field", {"para_id": None}),
    ("insert_page_number_field", {"para_id": None}),
    ("insert_if_field", {"para_id": None, "condition": None, "true_text": None, "false_text": None}),
    ("insert_sequence_field", {"para_id": None, "seq_name": None}),
    ("insert_merge_field", {"para_id": None, "field_name": None}),
    ("generate_toc", {}),
    ("update_toc", {}),
    ("generate_list_of_figures", {}),
    ("generate_list_of_tables", {}),
    ("generate_tof", {"para_id": None}),
    ("generate_tot", {"para_id": None}),
    ("add_content_control", {"para_id": None, "tag": None, "control_type": None}),
    ("get_content_controls", {}),
    ("set_content_control_value", {"tag": None, "value": None}),
    ("lock_content_control", {"tag": None}),
    ("delete_content_control", {"control_id": None}),
    ("get_content_control", {"control_id": None}),
    ("update_content_control", {"control_id": None}),
    ("fill_template", {"data": None}),
    ("list_template_fields", {}),
    ("validate_template_data", {"data": None}),
    ("create_multilevel_list", {"name": None, "levels": None}),
```

- **步骤 / 边界 / 验收**：同 T1.1 模板。
- **本批 names（逐字接在 `python3 - docx_mcp/server.py` 之后）**：
`add_internal_link remove_hyperlink update_hyperlink add_field update_fields list_fields get_field delete_field insert_date_field insert_page_number_field insert_if_field insert_sequence_field insert_merge_field generate_toc update_toc generate_list_of_figures generate_list_of_tables generate_tof generate_tot add_content_control get_content_controls set_content_control_value lock_content_control delete_content_control get_content_control update_content_control fill_template list_template_fields validate_template_data create_multilevel_list`
- **RED 期望**：`60 failed, 210 passed`。**GREEN 期望**：`270 passed`；全量 pytest + ruff exit 0。
- **note**：`docs/notes/remaining-handles-b3.md`
- **commit**：`feat(handles): route 30 remaining tools through document_handle #T-2118 progress 59%`

### Task 1.4 — Batch 4/6：30 工具（编号 / 图表 / 段落格式 / 会话）

- **依赖**：T1.3
- **frontier**：否
- **执行者**：Dev Orchestrator
- **预估墙钟**：≤20 min
- **修改内容**：追加本批 30 行到 `CASES`：

```python
    ("restart_numbering", {"para_id": None}),
    ("suppress_numbering", {"para_id": None}),
    ("get_lists", {}),
    ("promote_list_item", {"para_id": None}),
    ("demote_list_item", {"para_id": None}),
    ("bates_number", {"prefix": None}),
    ("redact_text", {}),
    ("generate_redaction_log", {}),
    ("generate_privilege_log", {}),
    ("add_equation", {"para_id": None, "latex": None}),
    ("get_equations", {}),
    ("insert_bar_chart", {"para_id": None, "title": None, "series": None, "categories": None}),
    ("insert_line_chart", {"para_id": None, "title": None, "series": None, "categories": None}),
    ("insert_pie_chart", {"para_id": None, "title": None, "series": None, "categories": None}),
    ("update_chart_data", {"chart_id": None, "series": None}),
    ("merge_review_rounds", {"reviewer_paths": None}),
    ("compare_contracts", {"other_path": None}),
    ("get_session_log", {}),
    ("export_session_script", {"output_path": None}),
    ("insert_paragraph", {"after_para_id": None, "text": None}),
    ("update_paragraph", {"para_id": None}),
    ("delete_paragraph", {"para_id": None}),
    ("set_paragraph_border", {"para_id": None, "sides": None}),
    ("set_paragraph_shading", {"para_id": None, "fill_color": None}),
    ("set_paragraph_indentation", {"para_id": None}),
    ("set_keep_with_next", {"para_id": None, "enabled": None}),
    ("set_keep_lines_together", {"para_id": None, "enabled": None}),
    ("set_page_break_before", {"para_id": None, "enabled": None}),
    ("set_widow_control", {"para_id": None, "enabled": None}),
    ("insert_blockquote", {"para_id": None, "text": None}),
```

- **步骤 / 边界 / 验收**：同 T1.1 模板。
- **本批 names（逐字接在 `python3 - docx_mcp/server.py` 之后）**：
`restart_numbering suppress_numbering get_lists promote_list_item demote_list_item bates_number redact_text generate_redaction_log generate_privilege_log add_equation get_equations insert_bar_chart insert_line_chart insert_pie_chart update_chart_data merge_review_rounds compare_contracts get_session_log export_session_script insert_paragraph update_paragraph delete_paragraph set_paragraph_border set_paragraph_shading set_paragraph_indentation set_keep_with_next set_keep_lines_together set_page_break_before set_widow_control insert_blockquote`
- **RED 期望**：`60 failed, 300 passed`。**GREEN 期望**：`360 passed`；全量 pytest + ruff exit 0。
- **note**：`docs/notes/remaining-handles-b4.md`
- **commit**：`feat(handles): route 30 remaining tools through document_handle #T-2118 progress 77%`

### Task 1.5 — Batch 5/6：30 工具（代码块 / run 级格式 / 主题 / 文档级 / 表格）

- **依赖**：T1.4
- **frontier**：否
- **执行者**：Dev Orchestrator
- **预估墙钟**：≤20 min
- **修改内容**：追加本批 30 行到 `CASES`：

```python
    ("insert_code_block", {"para_id": None, "text": None}),
    ("set_line_spacing", {"para_id": None}),
    ("get_paragraph_format", {"para_id": None}),
    ("get_runs", {"para_id": None}),
    ("set_run_font", {"para_id": None, "run_idx": None, "font_name": None}),
    ("set_run_color", {"para_id": None, "run_idx": None, "color": None}),
    ("set_run_size", {"para_id": None, "run_idx": None, "size_pt": None}),
    ("set_character_spacing", {"para_id": None, "run_idx": None, "spacing_pt": None}),
    ("set_character_position", {"para_id": None, "run_idx": None, "position_pt": None}),
    ("set_run_highlight", {"para_id": None, "run_idx": None, "color": None}),
    ("set_run_strikethrough", {"para_id": None, "run_idx": None}),
    ("set_run_superscript", {"para_id": None, "run_idx": None}),
    ("set_run_subscript", {"para_id": None, "run_idx": None}),
    ("set_run_underline", {"para_id": None, "run_idx": None}),
    ("clear_run_formatting", {"para_id": None, "run_idx": None}),
    ("set_run_language", {"para_id": None, "run_idx": None, "language_code": None}),
    ("set_text_case", {"para_id": None, "run_idx": None, "case": None}),
    ("export_markdown", {}),
    ("get_theme_colors", {}),
    ("set_theme_color", {"slot": None, "hex_color": None}),
    ("insert_caption", {"after_para_id": None, "text": None}),
    ("split_document", {}),
    ("get_word_count", {}),
    ("get_statistics", {}),
    ("set_document_language", {"language_code": None}),
    ("set_track_changes", {"enabled": None}),
    ("split_table", {"table_idx": None, "at_row_index": None}),
    ("duplicate_table_row", {"table_idx": None, "row_index": None}),
    ("sort_table", {"table_idx": None, "column_index": None}),
    ("get_table", {"table_idx": None}),
```

- **步骤 / 边界 / 验收**：同 T1.1 模板。
- **本批 names（逐字接在 `python3 - docx_mcp/server.py` 之后）**：
`insert_code_block set_line_spacing get_paragraph_format get_runs set_run_font set_run_color set_run_size set_character_spacing set_character_position set_run_highlight set_run_strikethrough set_run_superscript set_run_subscript set_run_underline clear_run_formatting set_run_language set_text_case export_markdown get_theme_colors set_theme_color insert_caption split_document get_word_count get_statistics set_document_language set_track_changes split_table duplicate_table_row sort_table get_table`
- **RED 期望**：`60 failed, 390 passed`。**GREEN 期望**：`450 passed`；全量 pytest + ruff exit 0。
- **note**：`docs/notes/remaining-handles-b5.md`
- **commit**：`feat(handles): route 30 remaining tools through document_handle #T-2118 progress 95%`

### Task 1.6 — Batch 6/6：最后 8 工具

- **依赖**：T1.5
- **frontier**：否
- **执行者**：Dev Orchestrator
- **预估墙钟**：≤10 min（本批仅 8 工具）
- **修改内容**：追加本批 8 行到 `CASES`：

```python
    ("get_cell_text", {"table_idx": None, "row_idx": None, "col_idx": None}),
    ("copy_table", {"table_idx": None}),
    ("flatten_document", {}),
    ("get_reading_time", {}),
    ("set_alt_text", {"image_index": None, "alt_text": None}),
    ("get_alt_text", {"image_index": None}),
    ("check_accessibility", {}),
    ("insert_text_box", {"para_id": None, "text": None}),
```

- **步骤**：RED → §5 脚本迁移本批 → `ruff format` → GREEN → 全量 → ruff → note。
- **本批 names（逐字接在 `python3 - docx_mcp/server.py` 之后）**：
`get_cell_text copy_table flatten_document get_reading_time set_alt_text get_alt_text check_accessibility insert_text_box`
- **RED 期望**：`16 failed, 458 passed`。**GREEN 期望**：`474 passed`；全量 pytest + ruff exit 0。
- **note**：`docs/notes/remaining-handles-b6.md`
- **commit**：`feat(handles): route final 8 tools through document_handle #T-2118 progress 100%`
  （**不带 `done` 关键字**——`done` 保留到 Phase 2 验收通过后的 T2.4 提交；`progress 100%` 只设置进度）
- **修改边界**：同 T1.1；完成后 `grep -c '_require_doc()' docx_mcp/server.py` 应为 1（仅定义）。

## 8. 完成后验收（Phase 2）

### Task 2.1 — AST pending=0 与 schema 静态核对

- **依赖**：T1.6
- **frontier**：是（A1/A2 只读；A4 需串行重启）
- **预估墙钟**：≤10 min
- **步骤与验收**：

```bash
# V2 — 本地 AST 断言（T-A）
python3 - <<'PY'
import ast, json
from pathlib import Path
src = Path("docx_mcp/server.py").read_text()
tree = ast.parse(src)
rows = []
for n in tree.body:
    if not isinstance(n, ast.FunctionDef):
        continue
    dec = any(
        (getattr(d.func if isinstance(d, ast.Call) else d, "attr", None) == "tool")
        or (getattr(d.func if isinstance(d, ast.Call) else d, "id", None) == "tool")
        for d in n.decorator_list
    )
    if not dec:
        continue
    args = [a.arg for a in n.args.posonlyargs + n.args.args]
    seg = ast.get_source_segment(src, n)
    rows.append((n.name, "document_handle" in args, "_require_doc()" in seg))
pending = [r for r in rows if not r[1] and r[2]]
assert not pending, f"pending left: {pending}"
assert sum(r[1] for r in rows) == 217, "expected 217 handle-accepting tools"
assert not any(r[2] for r in rows), "_require_doc left in tools"
print(f"AST OK: tools={len(rows)} with_handle=217 pending=0")
PY
grep -c 'document_handle: str = ""' docx_mcp/server.py   # 期望 217
grep -c '_require_doc()' docx_mcp/server.py              # 期望 1（定义行）
```

  - ✅ `[T-A]` 上述 python 块 exit 0 且打印 `pending=0`（AST 复算，等价 inventory）
  - ✅ `[T-B]` `assert sum(with_handle) == 217 and no_tool_calls_require_doc`
- **边界**：只读；⛔ 不改任何文件。

### Task 2.2 — 全量测试与 lint（CI 等价）

- **依赖**：T1.6
- **frontier**：是
- **预估墙钟**：≤10 min
- **步骤/验收**：
  - ✅ `[T-A]` `uv run pytest -q` → exit 0（全量，含 `tests/test_remaining_handles.py` 474 用例）
  - ✅ `[T-A]` `uv run pytest --cov=docx_mcp --cov-report=term-missing --cov-fail-under=88 -q` → exit 0（CI 门）
  - ✅ `[T-A]` `uv run ruff check . && uv run ruff format --check .` → exit 0
- **能失败证明（反例锚定）**：`tests/test_remaining_handles.py` 的 `CASES` 行数必须 == 158（`assert len(CASES) == 158` 由收集数 474 间接证明）；若有人把 `_resolve(document_handle)[1]` 换回 `_require_doc()`，isolation 用例会因 `A`/`B` 槽位串档而失败。

### Task 2.3 — 服务重启 + HTTP schema 探针

- **依赖**：T2.2
- **frontier**：否（需在 T2.2 绿后执行）
- **预估墙钟**：≤10 min
- **步骤**：

```bash
systemctl --user restart docx-mcp.service
for i in $(seq 1 30); do systemctl --user is-active --quiet docx-mcp.service && break; sleep 1; done
systemctl --user is-active docx-mcp.service      # 期望 active
# 若 30s 内未 active → 停手排查（不得继续探针）：
systemctl --user status --no-pager docx-mcp.service | tail -20
tail -n 40 /home/gw/.local/state/docx-mcp.log
python3 - <<'PY'
import json, urllib.request
URL = "http://127.0.0.1:8083/mcp"
H = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
def post(payload):
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers=H, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())
post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
      "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                 "clientInfo": {"name": "acceptance-probe", "version": "0"}}})
tools = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})["result"]["tools"]
assert len(tools) == 219, f"tool count {len(tools)}"
migrated = {t["name"] for t in tools if "document_handle" in t.get("inputSchema", {}).get("properties", {})}
assert len(migrated) == 217, f"handle tools {len(migrated)}"
for t in tools:
    props = t.get("inputSchema", {}).get("properties", {})
    required = set(t.get("inputSchema", {}).get("required", []) or [])
    if t["name"] in migrated:
        assert "document_handle" not in required, f"{t['name']} requires handle"
print(f"HTTP schema OK: tools={len(tools)} with_handle={len(migrated)}")
PY
```

  - ✅ `[T-A]` `systemctl --user is-active docx-mcp.service` → `active`
  - ✅ `[T-A]` 探针 exit 0 且打印 `tools=219 with_handle=217`
  - ✅ `[T-B]` `assert len(migrated) == 217 and document_handle not in required`
  - **能失败证明**：若未重启（旧进程），`with_handle` 仍为 59 → 断言失败；若 158 中任一漏迁移，`with_handle < 217` → 失败。
- **边界**：⛔ 不 push、不发布、不改 `~/.config/systemd/user/docx-mcp.service`。

### Task 2.4 — 验收记录与收尾提交

- **依赖**：T2.1、T2.2、T2.3
- **frontier**：否
- **预估墙钟**：≤10 min
- **修改内容**：新建 `docs/notes/remaining-handles-acceptance.md`，记录：AST 输出、全量 pytest 摘要（passed/skipped/覆盖率）、ruff 输出、HTTP 探针输出、服务重启时间、commit 列表。
- **验收标准**：
  - ✅ `[T-A]` `git log --oneline -7` 含 T1.1–T1.6 六条 `#T-2118` 提交 + T2.4 收尾提交
  - ✅ `[T-C]` `git status --porcelain` 仅含 `docs/notes/remaining-handles-acceptance.md`（若 note 已提交则为空）
  - ✅ `[T-B]` 接受门：仅当 T2.1/T2.2/T2.3 全绿才允许 commit message 用 `done 100%`
- **commit**：`docs(handles): record 158-tool migration acceptance #T-2118 done 100%`
  （若任一验收未通过 → 提交改为 `... #T-2118 progress 99%` 并在 note 列出阻塞项，**不得**写 done）

## 9. Execution Wave（并行度与降级）

| Wave | 可并行 Task | Frontier | 依赖已完成 |
|------|------------|----------|-----------|
| W1 | T1.1 | T1.1 | — |
| W2 | T1.2 | T1.2 | W1 |
| W3 | T1.3 | T1.3 | W2 |
| W4 | T1.4 | T1.4 | W3 |
| W5 | T1.5 | T1.5 | W4 |
| W6 | T1.6 | T1.6 | W5 |
| W7 | T2.1、T2.2 | T2.1、T2.2 可并行 | W6 |
| W8 | T2.3 → T2.4 | T2.3 串行于 T2.2 | W7 |

- 说明：T1.1–T1.6 **必须串行**（同改 `docx_mcp/server.py` 与同一测试文件；并行会互相覆盖）。
- 并行上限：本计划实际并行度 2（W7 T2.1/T2.2），无资源竞争。
- **超时降级**：任一批在 20 min 内未完成 → 立即停手，把该批剩余工具按 ≤15 个拆成子批（仍用 §5 脚本 + 同一 CASES 追加），不重跑已绿批次；连续两批超时 → `↑ ESCALATE: dev-orchestrator`。
- **回滚/修复前推**：单批失败优先在该批内修复前推（脚本幂等可重跑）；无法修复 → `git revert` 该批 commit 后再拆小批。

## 10. Post-Execution Verification

### Automated Verification

| ID | Description | Command | Expected |
|----|-------------|---------|----------|
| V1 | 迁移测试文件全绿 | `uv run pytest tests/test_remaining_handles.py -q` | exit 0，`474 passed` |
| V2 | 本地 AST pending=0 | Task 2.1 的 python 块 | exit 0，`pending=0` |
| V3 | 全量 pytest（CI 等价） | `uv run pytest --cov=docx_mcp --cov-fail-under=88 -q` | exit 0 |
| V4 | ruff | `uv run ruff check . && uv run ruff format --check .` | exit 0 |
| V5 | HTTP tools/list schema | Task 2.3 探针 | `tools=219 with_handle=217` |
| V6 | v1 特性计数 | `grep -c 'document_handle: str = ""' docx_mcp/server.py` | 217 |

### Deferred (needs restart / deployment)

- [ ] D1: `systemctl --user restart docx-mcp.service` → `is-active` 为 `active`（Task 2.3；这是本计划唯一的运行态变更）

### Probe (best-effort, run if available)

- [ ] P1: `curl -sS -m 5 -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8083/mcp -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"p","version":"0"}}}'` → `200`
- [ ] P2: `python3 /tmp/opencode/deploy2118/inventory.py` → `pending=0, with_handle=217`（需该脚本存在；不存在则用 V2 代替）

### Manual（真正需要人工判断）

- [ ] M1: 人工阅读 `docs/notes/remaining-handles-b1.md … b6.md`，确认每批 RED/GREEN 数字与 commit 一一对应，且未记录未来批次内容
- [ ] M2: 人工确认「2119 / 4271 未在本计划中实施」——`git log --oneline -10` 无相关改动

## 11. 风险矩阵

| Risk | Impact | Mitigation |
|------|--------|------------|
| 脚本排版破坏 / 语法错误 | 整仓 CI 红 | 每批强制 `ruff format` + `ast.parse`；RED 阶段先验证脚本只改签名不破坏 import |
| 某函数方法名 ≠ 工具名 → isolation 用例失败 | 单批卡住 | 已有 AST 断言（0 不一致）；失败即该工具改手工编辑并记录 |
| 测试 CASES 误预放未来批次 | 未来工具红测试阻断本批 | §6 规则 + T-C 文件范围检查；只 append 本批行 |
| 全量 pytest 慢导致批超 20 min | 违反粒度门 | §9 超时降级：拆子批；必要时把全量 pytest 挪到每两批一次（须用户在实施时确认） |
| 服务重启影响其他会话 | 运行态中断 | 仅在 Phase 2 最后执行；重启前确认无并发写会话（`_REQUIRE_HANDLE=1` 已隔离） |
| note 路径被冻结 | 无法追加记录 | 每批独立 `docs/notes/remaining-handles-bN.md`（H6） |

## 12. 后续阶段（本计划**不**实施，仅登记门槛）

| Task | 内容 | 启动条件 |
|------|------|---------|
| #2119 | 独立后续阶段 | **仅在拿到 AC 后**实施；本计划不为其创建 task、不改其文件 |
| #4271 | 独立后续阶段 | 同上 |

`→ handoff: dev-orchestrator`（Phase 1 执行）；Phase 2 验收后 `→ handoff: pm-coordinator`（更新 #2118 状态）。

## 审查日志

| 轮次 | 聚焦 | 发现问题数 | 已修正 | 剩余 |
|------|------|-----------|--------|------|
| R1 | 结构完整性 | 4 | 4 | 0 |
| R1.5 | 外部引用事实核查 | 1 | 1 | 0 |
| R2 | 可执行性（脚本干跑） | 2 | 2 | 0 |
| R2.8 | LLM 可执行性审查 | 2 | 2 | 0 |
| R3 | 风险与边缘 | 2 | 2 | 0 |
| **终止** | **[T1] — 五轮 issue 全清零** | | | **0** |

### R1（结构完整性）
1. 每批仅说「用 §5 脚本迁移本批」而无逐字 names → 已为 T1.1–T1.6 各补 `本批 names（逐字）` 行。
2. T1.6 commit 写 `progress 99%`，与「158/158 迁移完成」不符 → 改为 `progress 100%`，并注明不带 `done` 关键字（`done` 留 T2.4）。
3. 正文出现未定义的「A5 提交」→ 统一为 `T2.4 提交`。
4. §7 遗留占位符「（见文件后半部分）」→ 已由正文替换。

### R1.5（外部引用事实核查）
1. `uv` 存在（`/home/gw/.local/bin/uv`，0.12.0）、`docx-mcp.service` unit 存在且 `active running`（127.0.0.1:8083）、HTTP `initialize`→`tools/list` 实测返回 219 工具 → 全部引用为真。新增风险：`/tmp/opencode/deploy2118/inventory.py` 位于易失目录 → 已在 H1 设「以执行时 inventory 复算为准」、P2 给 V2 本地 AST fallback。
   - 追加核查：§5 脚本与已在临时副本验证的脚本**功能等价**（唯一差异为文档串注释）；CASES 参数名与 `docx_mcp/server.py` 签名逐工具一致（158/158，0 mismatch）；6 批 names 并集 == inventory pending 158，无重复无遗漏。

### R2（可执行性 / 脚本干跑）
1. 干跑验证：在 `/tmp/opencode/probe2118` 副本上对全部 158 函数执行 §5 脚本 → `ast.parse` 通过、`ruff check` All checks passed、`ruff format --check` clean、复算 `pending=0 / with_handle=217 / leftover _require_doc()=0`、二次运行幂等。
2. 干跑发现：未写 `grep -c 'document_handle: str = ""'` 期望值 → 已在 T2.1/V6 补 `217`；未写迁移后 `_require_doc()` 计数期望 → 已补 `1`（仅定义行，实测）。
3. RED 机制实测：当前 HEAD 上 `server.merge_cells(0,0,0,0,0, document_handle="B")` → `TypeError: merge_cells() got an unexpected keyword argument 'document_handle'`，与 RED 期望失败原因一致（非空洞测试）。

### R2.8（LLM 可执行性审查）
1. T2.3 无「服务 30s 未 active」的处置 → 已补 `systemctl status | tail` + `tail docx-mcp.log`。
2. note 路径/文件名、commit message、每批 RED/GREEN 数字（60/30、60/120、60/210、60/300、60/390、16/458 与 GREEN 90/180/270/360/450/474）已逐项写明，无需下游推断；`Document registry handle; empty uses the legacy default.` 文档串逐字给定。

### R3（风险与边缘 / 跨轮一致性）
1. 单批超 20 min 无降级路径 → §9 补「拆 ≤15 子批、不重跑已绿批次、连续两批超时升级」。
2. 服务重启可能影响并发写会话 → 风险矩阵标注，且重启仅放 Phase 2 末尾（`_REQUIRE_HANDLE=1` 已提供实例隔离）。
3. 跨轮一致性：6 批进度百分比（22/40/59/77/95/100）与 164 总数逐批核对一致；T2.4 的 done 门与 T1.6 的「不带 done」互不矛盾。

---

## 13. 执行日志（2026-11-03 — COMPLETED）

> 归档说明：本文件已于 2026-11-03 移入 `.github/plans/completed/`。以下数字均于归档当日实测复核
> （`date`、`git log`、AST 复算、本地 pytest、ruff、HTTP 探针），非沿用计划期预估。

### 13.1 Phase 1 — 六批句柄迁移（T1.1 → T1.6，严格串行）

| 批次 | Task | Commit | Message 摘要 | 工具数 | 累计进度 |
|------|------|--------|--------------|--------|----------|
| 1/6 | T1.1 | `006dcd4` | `feat(handles): route batch 1 through document_handle #T-2118 progress 22%` | 30 | 22% |
| 2/6 | T1.2 | `6bb6435` | `feat(handles): route batch 2 through document_handle #T-2118 progress 40%` | 30 | 40% |
| 3/6 | T1.3 | `022ef43` | `feat(handles): route batch 3 through document_handle #T-2118 progress 59%` | 30 | 59% |
| 4/6 | T1.4 | `fb69fcf` | `feat(handles): route batch 4 through document_handle #T-2118 progress 77%` | 30 | 77% |
| 5/6 | T1.5 | `74fa60c` | `feat(handles): route batch 5 through document_handle #T-2118 progress 95%` | 30 | 95% |
| 6/6 | T1.6 | `7bb503e` | `feat(handles): route final 8 tools through document_handle #T-2118 progress 100%` | 8 | 100% |
| 收尾 | T2.4 | `8426266` | `docs(handles): record #2118 completion evidence #T-2118` | — | — |

合计 30×5 + 8 = **158 工具**，与 inventory pending 集合并集一致（无重复、无遗漏）。
每批均按 T1.1 模板完成 RED → §5 脚本迁移 → `ruff format` → GREEN → 全量 pytest → ruff → 独立 note
（`docs/notes/remaining-handles-b1.md … b6.md`）；批次间严格串行，未发生超时降级。

### 13.2 Phase 2 — 收尾验收（T2.1 / T2.2 / T2.3 / T2.4）

**T2.1 AST 静态核对（V2 / A1）** — ✅ PASS

```
tools=219  with_handle=217  pending=0  require_doc_calls_in_tools=0
grep -c 'document_handle: str = ""' docx_mcp/server.py  → 217
grep -c '_require_doc()'            docx_mcp/server.py  → 1   （仅定义行，兼容 shim 按计划保留）
```

**T2.2 全量测试与 lint（V1 / V3 / V4）** — ✅ PASS

```
uv run pytest -q                                  → 1680 passed, 17 skipped, 1 warning
uv run pytest tests/test_remaining_handles.py -q  → 475 passed（CASES len == 158，见下）
uv run ruff check .                               → All checks passed!
uv run ruff format --check .                      → 148 files already formatted
```

> 计数口径澄清（归档时实测，避免与 `docs/notes/remaining-handles-summary.md` 冲突）：
> 该 note 记录的 `1655 passed` 写于收尾提交 `8426266` 当时，其后 #2119（`86e619a`）与 #4271（`eb29027`）
> 新增测试使全量达 **1680 passed**；`expected 474` 与 `475` 的差异为参数化收集口径（474 用例 + 1 条
> `get_word_count` 契约用例）。两者均非本计划失败的证据，本计划范围内 158 工具迁移全部通过。

**T2.3 服务重启 + HTTP schema 探针（V5 / D1）** — ✅ PASS

```
systemctl --user is-active docx-mcp.service → active
HTTP tools/list → tools=219  with_handle=217  handle_required=0
```

219 = 217 含 `document_handle` + 2 个路径型工具（`compare_documents` / `diff_to_text`，按 §1 BOUNDARY 有意不改）；
`handle_required=0` 证明 `document_handle` 从未进入 `required`，即全部为可选参数。

**T2.4 验收记录与收尾提交** — ✅ PASS（commit `8426266`，记录文件
`docs/notes/remaining-handles-summary.md`；实际文件名与计划 §T2.4 写的 `remaining-handles-acceptance.md` 不同，
以实际提交为准）

### 13.3 验收项终态

| ID | 项 | 结果 |
|----|----|------|
| V1 | 迁移测试文件全绿 | ✅ 475 passed |
| V2 | 本地 AST pending=0 | ✅ pending=0 / with_handle=217 |
| V3 | 全量 pytest（CI 等价） | ✅ 1680 passed, 17 skipped |
| V4 | ruff check + format --check | ✅ 均 exit 0 |
| V5 | HTTP tools/list schema | ✅ tools=219 / with_handle=217 / required=0 |
| V6 | v1 特性计数 | ✅ 217 |
| D1 | 服务重启后 active | ✅ active |
| M2 | 2119 / 4271 未在本计划内实施 | ✅ 两者为后续独立提交（`86e619a` / `eb29027`），不属本计划改动 |

### 13.4 边界遵守确认

- 仅改动 `docx_mcp/server.py`、`tests/test_remaining_handles.py`、`docs/notes/remaining-handles-b<N>.md`（+ T2.4 的 summary note）。
- `_require_doc()` 定义保留（1 处，兼容 shim）；`compare_documents` / `diff_to_text` 未改。
- 未执行 `git push`、未发布、未改 systemd unit。
- #2119 / #4271 为独立阶段，本计划未实施。

`→ handoff: pm-coordinator`（#2118 已达 164/164，可置 done 100%）。
