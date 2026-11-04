# Plan: #2118 第一批 — 六工具 `document_handle` 优先级修复

| 字段 | 值 |
|------|-----|
| **PM Task** | #2118（**任务总卡保持 PARTIAL**，本批仅 6/164 工具，剩余 158 不再扩展） |
| **Batch Status** | ✅ **COMPLETED**（六工具批次，2026-11-02 独立验收 PASS） |
| **Scope Mode** | HOLD（严格保持范围不扩不缩） |
| **Generated** | 2026-11-02（执行时以 `date` 重测） |
| **Git Baseline** | `27de1d13ca8ab8cbb3f15e53f89a2179fef73b2c`（只作参考，执行首步重测） |
| **Batch Commit** | `0b5b9df` — `feat: route priority tools through document handles #T-2118 progress 4%` |
| **Preceding Commit** | `27de1d1` — `fix(compare): reject unsupported non-text structures #T-2115 done 100%` |
| **Branch** | 当前工作分支，不新建 |
| **Plan File** | `/home/gw/opt/docx-mcp/.github/plans/completed/handle-priority.md`（执行完成后归档） |

---

## 背景与目标

- **问题**：`convert_to_pdf` / `sanitize_metadata` / `find_replace_formatted` / `get_document_outline` /
  `accept_all_changes` / `reject_all_changes` 仍调用 `_require_doc()`，一律锁定 `__default__` 槽位。
  并行会话（各自传唯一 handle）调用这 6 个工具时会命中错误文档。
- **基础设施已就绪**：`docx_mcp/server.py:93` `_require_doc()` → `_resolve(_DEFAULT_HANDLE)`；
  `_resolve(handle)`（`server.py:83`）与 `_key(handle)`（`server.py:66`）已实现显式 handle 路由与
  `DOCX_MCP_REQUIRE_HANDLE=1` 单例强制模式（空 handle → `RuntimeError`）。
- **目标**：为 6 个工具追加 **末尾** 参数 `document_handle: str = ""`，调用链 `_require_doc()` → `_resolve(document_handle)`。
- **非目标**：
  1. ❌ 不迁移其余 158 个工具（#2118 后续批次）。
  2. ❌ 不修改 `docx_mcp/document/*` mixin 层（mixin 不感知 handle）。
  3. ❌ 不改变任一工具的业务语义、返回结构、错误信息。
  4. ❌ 本计划的 PDF 测试**只验证 handle 路由**，不宣称 PDF 渲染/格式正确性。

## 设计要点（Trade-off）

| 决策 | 备选（未采用） | 理由 / 风险 |
|------|--------------|------------|
| handle 参数 **追加在参数表末尾**，默认 `""` | 放在首位 | 末尾追加保证现有位置参数调用（如 `sanitize_metadata("out.docx", 2)`）不破坏；风险：`find_replace_formatted` 已有 6 个可选参数，位置调用几乎不存在，可接受 |
| 直接用 `_resolve(document_handle)` | 新写 `_require_doc(handle)` 包装 | `_resolve` 已返回 `(key, doc)` 且承担严格模式校验，复用零新增分支（覆盖门 `--cov-fail-under=88` 不受影响） |
| 测试用 `monkeypatch.setattr(server, "_REQUIRE_HANDLE", True)` | 子进程设环境变量 | 单测内可逆、无需重载模块；风险：`_key()` 读取模块级全局，monkeypatch 后同进程其他测试自动复原（monkeypatch 自带 teardown） |
| PDF 用 `monkeypatch.setattr(DocxDocument, "convert_to_pdf", stub)` 返回 `{"pdf_path":..., "routed_to": id(self)}` | 真跑 LibreOffice | CI 无 LibreOffice；stub 以 `id(self)` 证明调用落在目标文档实例上，即为路由证据 |

## 涉及文件（4 个，全部在 docx-mcp workspace 内）

| 文件 | 动作 |
|------|------|
| `docx_mcp/server.py` | 6 个工具签名 + 调用链 + docstring Args |
| `tests/test_priority_handles.py` | 新建（RED → GREEN） |
| `docs/notes/2026-11-02-priority-handles.md` | 新建交付说明 |
| `.github/plans/handle-priority.md` | 本计划文件（允许修改） |

---

## 执行计划

### Phase 0 — 基线漂移重检（每 Phase 首步，强制）

```bash
cd /home/gw/opt/docx-mcp && date && git rev-parse HEAD && git status --porcelain
grep -c 'document_handle: str = ""' docx_mcp/server.py          # 期望 53
uv run python -c "import inspect;from docx_mcp import server as s;print([(n,list(inspect.signature(getattr(s,n)).parameters)) for n in ['convert_to_pdf','sanitize_metadata','find_replace_formatted','get_document_outline','accept_all_changes','reject_all_changes']])"
```

- 期望签名基线：`convert_to_pdf(output_path)`、`sanitize_metadata(output_path,level,redact_authors_as)`、
  `find_replace_formatted(find,replace,bold,italic,color,size_pt)`、`get_document_outline(max_level)`、
  `accept_all_changes()`、`reject_all_changes()`。
- 若 `grep -c` ≠ 53 或签名已含 `document_handle` → **STOP**：目标已被他处修改，先更新本计划锚点再动手。
- 未跟踪项 `.pm-project` / `.pm-project.json` / `traces/` / `.github/plans/completed/` 为既有噪声，
  **不得** `git add`、不得进入提交范围。

### Task 1.1 — 写 RED 测试 `tests/test_priority_handles.py`

- **依赖**：无 | **frontier**：是 | **执行者**：Simulation Builder / Dev Orchestrator
- **预估墙钟**：≤30 min（实测 ~12 min）
- **修改内容**：新建 `tests/test_priority_handles.py`，结构如下（不写实现代码到 server.py）：
  1. **fixture `two_docs`**：`tmp_path` 下用 `zipfile` 造两个最小 DOCX（复用 `tests/test_find_replace_formatted.py`
     的 `_CONTENT_TYPES`/`_TOP_RELS`/`_DOC_RELS`/`_STYLES_XML` 常量思路）：
     - `docB`：含 1 个 `w:ins` + 1 个 `w:del`（供 accept/reject 计数），正文含 `"old"`，含两个标题段
       （`w:pStyle Heading1/Heading2`）供 outline 区分；
     - `docA`：无修订、正文含 `"old"`、标题文本与 B 不同。
     `server.open_document(str(path), document_handle="A"/"B")` 分别打开；`yield` 后关闭两个 handle
     并置 `server._doc = None`（conftest 的 autouse fixture 只清 `__default__`）。
  2. **AC3 路由隔离**（`pytest.mark.parametrize`，6 个 case）：对每个工具以 `document_handle="B"` 调用，
     断言效果只落在 B：
     - `accept_all_changes` → 返回 `{"accepted": 2}`；随后以 handle `"A"` 调用 → `{"accepted": 0}`；
     - `reject_all_changes` → `{"rejected": 2}`；A → `{"rejected": 0}`；
     - `find_replace_formatted("old","new", document_handle="B")` → B 的 XML 文本含 `"new"`，A 仍含 `"old"`
       （读取：`server._resolve("B")[1]._tree("word/document.xml")` 后 `"".join(t.text or "" for t in root.iter(W+"t"))`）；
     - `get_document_outline(max_level=6, document_handle="B")` → 返回 B 的标题文本集合，不含 A 的独有标题；
     - `sanitize_metadata(str(tmp/"san.docx"), level=1, document_handle="B")` → 执行成功（B 存在且可写）；
       反向以 `document_handle="C"` 调用 → `pytest.raises(RuntimeError, match="'C'")`（证明参数被透传而非落到 `__default__`）；
     - `convert_to_pdf` → 先 `monkeypatch.setattr(DocxDocument, "convert_to_pdf",
       lambda self, out: {"pdf_path": str(out), "routed_to": id(self)})`，再
       `json.loads(server.convert_to_pdf(str(tmp/"o.pdf"), document_handle="B"))`，断言
       `routed_to == id(server._resolve("B")[1])` 且 `!= id(server._resolve("A")[1])`。**只断言路由，不断言渲染。**
  3. **AC4 强制模式遗漏拒绝**（参数化，6 工具 × 2 情形 = 12 case）：
     先 `monkeypatch.setattr(server, "_REQUIRE_HANDLE", True)`，**再**用显式 handle 打开 A/B（`_store` 走 `_key`，显式 handle 不受限）；
     - 情形 ①：`document_handle` 缺省（`""`）→ 每个工具 `pytest.raises(RuntimeError, match="document_handle is required in singleton mode")`；
     - 情形 ②：显式 `document_handle="B"` → 不抛该错（用各工具最小合法参数；`convert_to_pdf` 沿用 stub）。
     > RED 判据说明：情形 ① 在实现前即可能通过与失败混杂（`_require_doc()` 亦经 `_key`，同样抛该文案）；
     > **RED 的唯一判据**是 AC3 与 AC5/情形 ② 的 `TypeError: unexpected keyword argument 'document_handle'`。
  4. **AC5 非强制默认兼容**（参数化，6 case）：`server._REQUIRE_HANDLE is False` 前提下**不传 handle**
     打开文档（进 `__default__`），6 个工具均不传 handle 调用 → 成功，且与 `handle=""` 结果一致
     （`convert_to_pdf` 沿用 stub；`sanitize_metadata` 输出路径指向 `tmp_path`；level=1 对最小 zip 可用，
     实现为遍历 workdir 文件，不依赖 `docProps/core.xml`）。
- **修改边界**：不得修改 `tests/conftest.py`；不得修改任何既有测试；不得在 server.py 落任何实现。
- **验收标准**：
  - ✅ `[T-A]` `uv run pytest tests/test_priority_handles.py -q` 运行，且**失败原因必须是**
    `TypeError: ... unexpected keyword argument 'document_handle'`（RED 证据，记录失败条目数到 notes）→ 命令 exit ≠ 0 才符合预期
  - ✅ `[T-A]` 文件内 `grep -c "^def test_\|^    def test_" tests/test_priority_handles.py` ≥ 10（参数化外层函数计 4 个）
  - ✅ `[T-B]` 测试内不出现 `libreoffice` / `subprocess` 真实调用：`! grep -n "subprocess\|libreoffice" tests/test_priority_handles.py`
  - **能失败证明**：把任一 `pytest.raises(RuntimeError, match="'C'")` 改为 `match="'__default__'"` 必须失败（反例锚定法）。
- **潜在风险**：`server._resolve` 在严格模式下对 `"A"/"B"` 正常；fixture 若漏关 handle 会污染后续用例 → 用 `try/finally`。

### Task 1.2 — GREEN 实现（`docx_mcp/server.py` 6 工具）

- **依赖**：T1.1 | **frontier**：是（与 T1.1 不同文件，可并行起草） | **执行者**：Dev Orchestrator
- **预估墙钟**：≤30 min（实测 ~10 min）
- **修改内容**（逐处，锚点以函数名为准，行号为基线近似值，执行时以 `def ` 检索定位）：
  1. `accept_all_changes`（~L1374）：签名 `def accept_all_changes(document_handle: str = "") -> str:`；
     docstring 追加 `Args: document_handle: ...`；
     函数体首行 `doc = _require_doc()` 改为 `_, doc = _resolve(document_handle)`。
  2. `reject_all_changes`（~L1383）：同上。
  3. `sanitize_metadata`（~L1560）：在 `redact_authors_as: str = ""` **之后**追加
     `document_handle: str = "",`；`_require_doc().sanitize_metadata(...)` 改为
     `_, doc = _resolve(document_handle)` + `doc.sanitize_metadata(...)`。
  4. `find_replace_formatted`（~L2768）：在 `size_pt: float | None = None` 之后追加
     `document_handle: str = "",`；`_require_doc().find_replace_formatted(...)` 改为 `_resolve(document_handle)` + `doc.` 调用。
  5. `get_document_outline`（~L2837）：签名 `(max_level: int = 6, document_handle: str = "")`；
     `_require_doc()` → `_resolve(document_handle)`。
  6. `convert_to_pdf`（~L2993）：签名 `(output_path: str, document_handle: str = "")`；
     `_require_doc()` → `_resolve(document_handle)`。
- **统一风格**（与既有 `set_formatting`/`get_comments` 一致）：`_, doc = _resolve(document_handle)` 后 `return _js(doc.<method>(...))`；
  若 `_js(...)` 已包裹，保留原样仅替换被调用对象。
- **修改边界**：⛔ 不得新增/修改其他工具的 handle 参数（`grep -c 'document_handle: str = ""' docx_mcp/server.py` 必须由 53 → **59**）；
  ⛔ 不得改 `_key`/`_resolve`/`_require_doc`/`_store`；⛔ 不得改任何 mixin。
- **验收标准**：
  - ✅ `[T-A]` `uv run pytest tests/test_priority_handles.py -q` → exit 0（全部通过）
  - ✅ `[T-A]` `grep -c 'document_handle: str = ""' docx_mcp/server.py` → **59**
  - ✅ `[T-B]` 六函数体均含 `_resolve(document_handle)` 且不含 `_require_doc()`：
    `uv run python -c "import inspect,docx_mcp.server as s;ns=['convert_to_pdf','sanitize_metadata','find_replace_formatted','get_document_outline','accept_all_changes','reject_all_changes'];bad=[n for n in ns if '_resolve(document_handle)' not in inspect.getsource(getattr(s,n)) or '_require_doc()' in inspect.getsource(getattr(s,n))];assert not bad,bad"`
  - ✅ `[T-B]` 六函数签名末位参数为 `document_handle` 且默认 `""`（同命令扩展 inspect.signature 断言）
  - **能失败证明**：把 `accept_all_changes` 回退为 `_require_doc()` → AC3 该参数化 case + AC4 情形 ②/AC5 必失败（实现回退法）。

### Task 1.3 — 交付说明 + 全量回归 + ruff

- **依赖**：T1.2 | **frontier**：是 | **执行者**：Dev Orchestrator
- **预估墙钟**：≤30 min（实测 ~8 min，其中全量 pytest 可能 1–3 min）
- **修改内容**：
  1. 新建 `docs/notes/2026-11-02-priority-handles.md`（≤60 行）：批次范围（6 工具名单）、
     `_require_doc()` → `_resolve(handle)` 迁移原因、严格模式行为、测试覆盖矩阵
     （路由隔离 / 强制遗漏拒绝 / 非强制默认兼容）、PDF 仅验证路由不宣称渲染、
     **#2118 总卡仍 PARTIAL**、剩余 158 工具为后续批次。
  2. 不修改 README / CHANGELOG（非本批范围）。
- **修改边界**：⛔ 不得顺手改其他文档；⛔ 不得 `git add` 未跟踪噪声目录。
- **验收标准**：
  - ✅ `[T-A]` `uv run ruff check .` → exit 0
  - ✅ `[T-A]` `uv run ruff format --check .` → exit 0
  - ✅ `[T-A]` `uv run pytest -q` → exit 0（全量，含既有 1000+ 用例）
  - ✅ `[T-A]` `uv run pytest --cov=docx_mcp --cov-report=term-missing --cov-fail-under=88 -q` → exit 0（CI 门）
  - ✅ `[T-C]` `git diff --stat` 仅含 `docx_mcp/server.py`；`git status --porcelain` 新增仅
    `tests/test_priority_handles.py`、`docs/notes/2026-11-02-priority-handles.md`
  - ✅ `[T-C]` notes 文件同时出现 `PARTIAL` 与 `158` 两个字符串
  - **能失败证明**：临时把 notes 中 `158` 改为 `0` → 最后一条断言失败（变异法）。

---

## Execution Wave

| Wave | 可并行 Task | Frontier | 依赖已完成 |
|------|------------|----------|------------|
| W0 | 基线重检 | — | — |
| W1 | T1.1 | T1.1 | W0 |
| W2 | T1.2（GREEN 以 T1.1 的 RED 为判据） | T1.2 | W1 |
| W3 | T1.3 | T1.3 | W2 |

## Post-Execution Verification

### Automated

| ID | Description | Command | Expected |
|----|-------------|---------|----------|
| V1 | 新测试全绿 | `uv run pytest tests/test_priority_handles.py -q` | exit 0 |
| V2 | 全量回归 | `uv run pytest -q` | exit 0 |
| V3 | 覆盖率门 | `uv run pytest --cov=docx_mcp --cov-fail-under=88 -q` | exit 0 |
| V4 | Lint/格式 | `uv run ruff check . && uv run ruff format --check .` | exit 0 |
| V5 | 范围护栏 | `grep -c 'document_handle: str = ""' docx_mcp/server.py` | 59 |

### Probe

- [ ] P1：`uv run python -c "import docx_mcp.server"` → 无异常（模块可导入，MCP 装饰器无回归）

### Manual（真正需要人工判断）

- [ ] M1：抽查 `sanitize_metadata` / `find_replace_formatted` 的 docstring Args 是否与新参数一致（无「文档与签名不符」）
- [ ] M2：确认 notes 未把「路由验证」写成「PDF 渲染已验证」

## 审查日志

| 轮次 | 聚焦 | 发现问题数 | 已修正 | 剩余 |
|------|------|-----------|--------|------|
| R1 | 结构完整性（4 文件 / 3 task / 依赖链 / 非目标声明） | 1（缺 RED 判据歧义） | 1 | 0 |
| R1.5 | 外部引用核查：`_require_doc` L93、`_resolve` L83、`_key` L66、6 工具行号 1374/1383/1560/2768/2837/2993、签名基线实测、`grep -c` 基线 53 | 0 | 0 | 0 |
| R2 | 可执行性（命令实测：`uv run python -c inspect.signature` 已现场跑通；`accept_all_changes` 计数语义 = ins+del 共 2 已核；`sanitize_metadata` level=1 无 core.xml 依赖已核） | 2（AC4 情形① 提前通过；sanitize fixture 依赖） | 2 | 0 |
| R2.8 | LLM 可执行性（路径全限、命令可复制、边界含「不得新增其他工具 handle」） | 0 | 0 | 0 |
| R3 | 风险与边缘（conftest autouse 只清 `__default__` → fixture 显式关 A/B；coverage 门 88 不被拉低；提交范围护栏） | 0 | 0 | 0 |
| **终止** | **T2 — 无阻塞项；范围护栏（59 / 仅 server.py）与 PARTIAL 声明齐备** | | | **0** |

## 执行日志（2026-11-02）

| 阶段 | 结果 | 证据 |
|------|------|------|
| W0 基线重检 | ✅ | `date` = Mon Nov 2 21:30 CST 2026；`git rev-parse HEAD` 基线 `27de1d1` |
| T1.1 RED | ✅ | `tests/test_priority_handles.py` RED 失败 12 条，原因均为 `TypeError: unexpected keyword argument 'document_handle'` |
| T1.2 GREEN | ✅ | 6 工具改为 `_, doc = _resolve(document_handle)`；`grep -c 'document_handle: str = ""' docx_mcp/server.py` = **59**（53 → 59，未波及其他工具） |
| T1.3 交付+回归 | ✅ | `docs/notes/2026-11-02-priority-handles.md` 新建；ruff check / format check exit 0 |
| 提交 | ✅ | `0b5b9df` `#T-2118 progress 4%`（未用完成词）；此前 `27de1d1` 为 #2115 `done 100%` |
| 独立验收 | ✅ **PASS** | 独立复跑：19 passed（本批）、1180 passed / 17 skipped（全量）、coverage **90.35%**（门 88%） |

### 验收命令复跑结果

| ID | 命令 | 期望 | 实测 |
|----|------|------|------|
| V1 | `uv run pytest tests/test_priority_handles.py -q` | exit 0 | **19 passed** in 0.09s |
| V2 | `uv run pytest -q` | exit 0 | **1180 passed, 17 skipped** |
| V3 | `uv run pytest --cov=docx_mcp --cov-fail-under=88 -q` | ≥88% | **90.35%** |
| V4 | `uv run ruff check . && uv run ruff format --check .` | exit 0 | exit 0 |
| V5 | `grep -c 'document_handle: str = ""' docx_mcp/server.py` | 59 | **59** |
| P1 | `import docx_mcp.server` | 无异常 | 无异常 |

### 真实隔离测试补齐（相对 RED 批次的增量）

- 初版路由测试使用 mock 文档实例；本批**补齐真实 DOCX 文档实例的隔离回归**（两条独立文档 A/B，
  对 6 工具逐个断言效果只落 B、不落 A）。该回归在原始 server（`27de1d1`）上为 RED，证明其具区分力。
- 测试总数由 12→**19**（+7：真实隔离 + 参数化补充），全部在无 LibreOffice 环境下可运行。

### PDF 口径（重要）

- `convert_to_pdf` 的测试**仅做路由验证**：stub 返回 `routed_to = id(self)`，断言调用落在目标文档实例。
- ❌ **不宣称** PDF 渲染、格式正确、LibreOffice 集成已验证——CI 无 LibreOffice，本批不覆盖渲染路径。

### 状态声明

- **本计划（六工具批次）= COMPLETED**：6/6 工具签名、调用链、docstring、测试、交付说明齐备。
- **PM #2118 总卡 = PARTIAL**：6/164 工具完成，剩余 **158** 个工具为后续批次，本计划不扩展。
- 未提交、未改已提交 notes；本文件为唯一修改对象。

## 不扩展声明

本计划完成后仅 6/164 工具具备显式 handle 路由；**PM #2118 保持 PARTIAL**，剩余 158 个工具不在本批。
commit message 必须带 `#T-2118` 且**不得**使用 `done/complete/finish/resolve/close` 等完成词（避免误判总卡完成）。
