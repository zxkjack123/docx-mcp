# 执行计划：docx-mcp 文档跟进（D2–D5）

**Status**: COMPLETED

**计划文件路径**：`/home/gw/opt/docx-mcp/.github/plans/completed/docs-followup.md`
**仓库**：`/home/gw/opt/docx-mcp`（归属校验：cwd == workspace root，非跨仓任务）
**生成日期**：2026-11-02（执行时以 `date` 实测复核）
**来源任务**：#5167(D2) / #5168(D3) / #5169(D4) / #5170(D5) — 用户声明已授权实施（D2/D3/D4/D5 授权由父代理 prompt 传入，范围仅限本计划列出的文件）
**Rigid 声明**：四个任务的集合与语义由父代理 prompt 逐字给定，本计划只做「最小化落地 + 机械验收」，不扩展范围、不新增任务。

---

## 1. 目标与非目标

### 目标
1. **D2 (#5167)** — `README.md` 的 `## Requirements` 与 `pyproject.toml` 对齐：补上 MCP Python SDK 约束 `mcp>=2,<3`。
2. **D3 (#5168)** — `README.md` 说明 `save_document` 前自动修复（pre-save auto-repair）对注释的处理语义：**保留**三种 Word 结构性 note type 与 `settings.xml` pinned ids，**未知 type 的 orphan 仍删除**。
3. **D4 (#5169)** — `README.md` 说明 PDF 导出：LibreOffice/PATH 前置条件、**90 s 默认超时**、`DOCX_MCP_PDF_TIMEOUT` 的**实际解析规则**；并明确 `convert_to_pdf` 缺 `document_handle` → **singleton 模式（`DOCX_MCP_REQUIRE_HANDLE=1`）下当前不可用**。
4. **D5 (#5170)** — 依据**当前代码 / git 证据**更新两份过期文档的状态：`docs/plans/2026-07-27-real-world-defects-roadmap.md` 与 `.github/reviews/defect-roadmap-verification-2026-07-27.md`。**不盲信过期 PM 状态**。

### 非目标（硬边界）
- ❌ 不改任何 `docx_mcp/**` 源码、不改 `tests/**`、不改 `pyproject.toml`（只读引用作为对齐基准）。
- ❌ 不新增/重命名工具、不改行为、不提版本号、不动 `uv.lock`。
- ❌ 不为 D5 的未完成项（Bug 2、Feature 2 残余、Feature 3、Design 1–3）生成新实现计划——只更新**状态标记**。
- ❌ 不采用上一轮 explore 的错误映射（**D3 ≠ version reporting（版本上报）**；**D4 ≠ lock 文件检查**）。D3 只谈 note 保留语义，D4 只谈 PDF 导出链路。

---

## 2. 已核实事实（事实基线，含仓内锚点）

以下均为本计划生成时**实测**结果；**执行时必须重测**（见 §3 基线漂移重检）。行号为生成时值，**执行时按符号 grep 重锚**，禁止直接按行号定位。

| 事实 | 证据锚点（符号优先） | 值 |
|---|---|---|
| F1 | `pyproject.toml` `[project].dependencies` | `"mcp>=2,<3"`（`docx-mcp-server` 版本 0.7.4） |
| F2 | `README.md` → `## Requirements` | 仅 `- Python 3.10+` / `- Works on macOS, Linux, and Windows`，**未提 mcp 依赖** |
| F3 | `docx_mcp/document/base.py` → `_STRUCTURAL_NOTE_TYPES` | `frozenset({"separator", "continuationSeparator", "continuationNotice"})` |
| F4 | `base.py` → `_settings_note_ids(kind)` | 从 `word/settings.xml` 的 `w:footnotePr`/`w:endnotePr` 下取 `w:footnote`/`w:endnote` 的 `w:id` |
| F5 | `base.py` → `_pre_save_repair()` 删除条件 | 删除需**同时**满足：非结构性 note **且** 不在 pinned ids **且** 未被 body 引用（`w:footnoteReference`/`w:endnoteReference`）；footnote 另需 `id >= 2`，endnote 需 `id not in (0, -1)` |
| F6 | `docx_mcp/document/pdfexport.py` → `DEFAULT_TIMEOUT` | `90.0` 秒 |
| F7 | `pdfexport.py` → `_resolve_timeout()` | 实际解析规则：env 为**空/未设** → 90.0；`float(raw)` 抛 `ValueError`（非数值）→ 90.0；数值 **≤ 0** → 90.0；否则用该数值 |
| F8 | `pdfexport.py` → `PdfExportMixin.convert_to_pdf` | `shutil.which("libreoffice") or shutil.which("soffice")`；两者皆无 → `RuntimeError("LibreOffice not found...")`；`subprocess.run(..., stdin=DEVNULL, timeout=...)`；超时 → `RuntimeError("LibreOffice conversion timed out after {timeout:g}s ...")`；非零退出 → `RuntimeError`；产物按输入 stem 命名后 rename 到 `output_path` |
| F9 | `docx_mcp/server.py` → `def convert_to_pdf(output_path: str) -> str` | **无 `document_handle` 参数**，内部 `_require_doc()` → `_resolve(_DEFAULT_HANDLE)` |
| F10 | `server.py` → `_key(handle)` + `_REQUIRE_HANDLE` | `DOCX_MCP_REQUIRE_HANDLE` ∈ {`1`,`true`,`yes`,`on`}（小写比较）时，`__default__` 槽位被禁用 → 抛 `RuntimeError("document_handle is required in singleton mode ...")` ⇒ **singleton 模式下 `convert_to_pdf` 不可用** |
| F11 | `git merge-base --is-ancestor 8fb3fa0 HEAD` | **YES** — `8fb3fa0 fix(server): [PM#2116] add document_handle to copy_document and update_image`（经 `5b362d8` 合入 main）；现状 `server.py` 中 `def copy_document(output_path, document_handle="")`、`def update_image(rId, new_image_path, document_handle="")` 均有 handle |
| F12 | `git log --oneline --since=2026-07-27` 相关提交 | `6d393a5 fix(tracks): [PM#2114] remove document-global uniqueness guard from _resolve()`（经 `f5face8` 合入）；`71438c8 feat(formatting): [PM#2117] add tracked parameter to update_paragraph`（经 `3a944d0` 合入）；`61d390c feat(server): env-gated DOCX_MCP_REQUIRE_HANDLE`；`6706fe0 fix(repair): preserve structural and pinned notes during save`；`ec5fcd7 fix(pdfexport): isolate LibreOffice stdin and bound conversion time` |
| F13 | `docx_mcp/document/compare.py` | `compare_documents` 仍只经 `_body_paragraphs()` 取 `w:p`；文件内 `grep -c raise` == **0**，无 `w:tbl`/`w:drawing`/`m:oMath` 检测 ⇒ **Bug 2 未修复** |
| F14 | `server.py` 工具签名 | 仍缺 `document_handle`：`accept_all_changes`、`reject_all_changes`、`sanitize_metadata`、`find_replace_formatted`、`get_document_outline`、`convert_to_pdf` ⇒ Feature 2 部分完成 |
| F15 | `docx_mcp/**` grep | `sanitize_level` / `replace_all` / `extract_image` **零命中** ⇒ Feature 3、Design 1–3 未实现 |

### D5 目标状态表（写文档时直接采用）

| 项 | 现状（实测） | 状态标记 | 证据 |
|---|---|---|---|
| Bug 1 `replace_text` 全文档搜索 | `replace_text` 先 `_find_para(para_id)` 再 `_resolve(doc, para, ...)`；文档级唯一性守卫已移除 | **FIXED** | F12 `6d393a5` / `f5face8` |
| Bug 2 `compare_documents` 结构化元素 | 仍只 diff `w:p`，无检测/报错 | **OPEN** | F13 |
| Bug 3 `copy_document`/`update_image` handle | 两工具均已含 `document_handle` | **FIXED** | F11 `8fb3fa0` |
| Feature 1 `update_paragraph(tracked=)` | 签名含 `tracked: bool = False, author: str = "Claude"` | **FIXED** | F12 `71438c8` |
| Feature 2 handle 覆盖率 | 6 个工具仍缺 handle；`copy_document`/`update_image` 已补齐（原表未列） | **PARTIAL** | F14 / F11 |
| Feature 3 `save_document` 集成 sanitize | 无 `sanitize_level` 参数 | **OPEN** | F15 |
| Design 1 `replace_all` / Design 2 `extract_image` / Design 3 重命名 | 均无 | **OPEN** | F15 |
| 路线图外新增（需回写） | `DOCX_MCP_REQUIRE_HANDLE` 环境门控；save 保留 structural/pinned notes；PDF 超时与 stdin 隔离 | NEW | F12 / F9 / F10 / F6–F8 |

> 复核提示：原 review 报告中的行号（`tracks.py:289`、`compare.py:28-32`、`formatting.py:140`、`server.py:2937/2952` 等）**已漂移**，D5 必须按**符号名**重锚，禁止沿用旧行号。

---

## 3. 全局执行规则（四任务共同约束）

1. **基线漂移重检（每任务第一步，强制）**
   ```bash
   cd /home/gw/opt/docx-mcp && git rev-parse HEAD && git status --porcelain
   git merge-base --is-ancestor 8fb3fa0 HEAD && echo "F11 OK"
   grep -n '_STRUCTURAL_NOTE_TYPES' docx_mcp/document/base.py
   grep -n 'DEFAULT_TIMEOUT\|TIMEOUT_ENV' docx_mcp/document/pdfexport.py
   grep -n 'mcp>=' pyproject.toml
   ```
   若 HEAD 变动或上述符号缺失 → **先更新本计划 §2 锚点再动手**；本计划不硬编码行号与 commit 之外的基线。
2. **写入范围**：每个任务只允许写其 `修改内容` 声明的文件；`git diff --stat` 必须**只含声明文件**（AGENTS.md 硬规则 9）。
3. **每任务独立 commit**（一个 task = 一个 commit，禁止合并提交）；commit message 末尾带 `#T-<PM id>`，完成词用 `done 100%`（触发 PM 自动置 done；`fix` 不算完成词）。PM 写操作经 `pm-coordinator`。
4. **串行写 README**：D2 → D3 → D4 串行（同一文件，避免冲突）。D5 文件与 README 不重叠，**可并行起草**，但 **commit 必须串行**（单写者，避免 git index 竞争）。
5. **验收命令为只读断言**：全部用 `python3 - <<'PY'` 只读读取文件并断言，**不写文件、不跑网络**。每条 AC 标注类型（T-A 命令型 / T-B 断言型 / T-C 结构型）及**能失败证明**手法。
6. **不许「顺带修」**：README 其他章节、路线图其他条目、代码注释一律不动。发现额外问题 → 记入计划末尾「执行期发现（回写）」区，不就地修。

---

## 4. 任务清单

### W1 — D2 (#5167)：README Requirements 对齐 pyproject

- **依赖**：无 ｜ **frontier**：是（可与 D5 并行起草，commit 串行）
- **执行者**：Technical Writer（或 Dev Orchestrator 直接执行）
- **预估墙钟**：≤ 10 min
- **修改内容**
  - 文件：`/home/gw/opt/docx-mcp/README.md`
  - 定位锚点：`## Requirements` 小节（该标题在 README 中唯一）
  - 动作：在该小节的 bullet 列表中，于 `- Python 3.10+` **之后**插入一行（措辞可微调，但必须含规范字符串 `mcp>=2,<3` 与「自动安装」语义）：
    ```markdown
    - MCP Python SDK `mcp>=2,<3` (installed automatically by `uvx docx-mcp-server` / `pip install docx-mcp-server`)
    ```
  - 依据：F1（pyproject `dependencies` 为 `"mcp>=2,<3"`）与 F2（README 现无该约束）。
- **修改边界**
  - ⛔ 不得修改 `pyproject.toml`（只读对齐基准）。
  - ⛔ 不得改动 `## Requirements` 之外的任何 README 段落；不得删除 `Python 3.10+` / `Works on macOS, Linux, and Windows` 两条。
  - ⛔ 不得写入 `mcp>=1.28,<2` 等历史约束（已被 `2d1abf2` 的 SDK v2 迁移取代，见 F12）。
- **质量检查方式**
  - 约束字符串与 pyproject **同源**（由脚本从 pyproject 提取，非人工转抄）。
  - 该行仍在 `## Requirements` 标题与下一个 `##`/`---` 之间的区间内。
- **验收标准**（可执行只读断言，`cd /home/gw/opt/docx-mcp &&`）
  - ✅ **[T-B] 约束值与 pyproject 一致**
    ```bash
    python3 - <<'PY'
    import re, pathlib
    root = pathlib.Path('/home/gw/opt/docx-mcp')
    py = (root/'pyproject.toml').read_text()
    spec = re.search(r'^\s*"mcp([^"]*)"', py, re.M).group(1)   # 期望 ">=2,<3"
    rd = (root/'README.md').read_text()
    sec = rd.split('## Requirements',1)[1].split('\n## ',1)[0]
    assert f'mcp{spec}' in sec, f'README Requirements missing mcp{spec}'
    assert 'Python 3.10+' in sec and 'macOS' in sec
    print('OK', f'mcp{spec}')
    PY
    ```
    exit 0。**能失败证明（实现回退法）**：`git stash` 掉 README 改动或把插入行改回 `mcp>=1.28,<2` → 脚本抛 `AssertionError`。
  - ✅ **[T-C] 只含声明文件**：`git diff --stat --name-only` 输出恰为 `README.md`（无其他路径）。
- **潜在风险**：README 中若已存在描述「mcp 版本」的别处文字 → 只补 Requirements 一处，重复表述留给后续（记入回写区）。
- **Commit**：`docs(readme): align Requirements with pyproject mcp>=2,<3 — done 100% #T-5167`

---

### W2 — D3 (#5168)：README 说明 save 的 note 保留语义

- **依赖**：D2（同一文件，串行） ｜ **frontier**：否
- **执行者**：Technical Writer
- **预估墙钟**：≤ 15 min
- **修改内容**
  - 文件：`/home/gw/opt/docx-mcp/README.md`
  - 定位锚点：`### Footnotes & Endnotes` 小节（该标题唯一，位于 `## How It Works` 下）
  - 动作：在该小节表格**之后**追加一段说明（标题/措辞自定，内容必须覆盖以下 4 点，其中三个 type 名与 `settings.xml pinned ids` 为**必须逐字出现**的关键字）：
    1. `save_document` 前会运行 pre-save auto-repair，清理未引用的 orphan footnote/endnote；
    2. **保留** Word 结构性注释类型：`separator`、`continuationSeparator`、`continuationNotice`（一字不差）；
    3. **保留**由 `word/settings.xml`（`w:footnotePr` / `w:endnotePr`）**pinned** 的 note id；
    4. **未识别的 note type（unknown type）且未被正文引用的 orphan 仍会被删除**——即「保留」只覆盖上述两类。
  - 依据：F3（`_STRUCTURAL_NOTE_TYPES`）、F4（`_settings_note_ids`）、F5（删除条件为三者同时满足）。
- **修改边界**
  - ⛔ 不改 `docx_mcp/document/base.py`；⛔ 不改 README 其他小节。
  - ⛔ 禁止把它写成「所有 orphan 都保留」或「所有未引用 note 都删除」——两者都与 F5 不符。
  - ⛔ **不得**写成版本上报 / version reporting 内容（上一轮 explore 的错误映射，明确排除）。
- **质量检查方式**
  - 三个 type 名与源码 frozenset **同源比对**（脚本解析 base.py，不靠人工转抄）。
- **验收标准**
  - ✅ **[T-B] 三个 type 名与源码完全一致 + pinned 语义在位**
    ```bash
    python3 - <<'PY'
    import re, pathlib
    root = pathlib.Path('/home/gw/opt/docx-mcp')
    src = (root/'docx_mcp/document/base.py').read_text()
    m = re.search(r'_STRUCTURAL_NOTE_TYPES\s*=\s*frozenset\(\{([^}]*)\}\)', src)
    types = re.findall(r'"([^"]+)"', m.group(1))
    assert len(types) == 3, types
    rd = (root/'README.md').read_text()
    for t in types:
        assert t in rd, f'README missing structural note type {t}'
    assert 'settings.xml' in rd and re.search(r'pinned', rd, re.I)
    assert re.search(r'(unknown|unrecognis|unrecogniz|未识别)', rd, re.I)
    print('OK', types)
    PY
    ```
    exit 0。**能失败证明（变异法）**：把 README 中 `continuationNotice` 改回 `continuation` → 脚本抛 `AssertionError`；删掉 pinned 句 → `assert` 失败。
  - ✅ **[T-A] 语义反向锚定**：`grep -n 'unknown' README.md` 命中行的上下文必须与「仍删除」同句（人工 5 秒复核，记录在 commit body）。
  - ✅ **[T-C] 只含声明文件**：`git diff --stat --name-only` 恰为 `README.md`。
- **潜在风险**：README 篇幅膨胀 → 段落控制在 ≤ 8 行。
- **Commit**：`docs(readme): document save-time note repair (structural types + pinned ids retained) — done 100% #T-5168`

---

### W3 — D4 (#5169)：README 说明 PDF 导出（前提 / 超时规则 / singleton 限制）

- **依赖**：D3（同一文件，串行） ｜ **frontier**：否
- **执行者**：Technical Writer
- **预估墙钟**：≤ 20 min
- **修改内容**
  - 文件：`/home/gw/opt/docx-mcp/README.md`
  - 定位锚点：`## Requirements`（插入点 = 该标题**之前**），新增小节标题 `### PDF Export`
  - 动作：新增 `### PDF Export` 小节（属于 `## How It Works` 的最后一个子节），必须覆盖：
    1. **前提**：需要本机安装 LibreOffice，且 `libreoffice` 或 `soffice` 在 `PATH` 上（`shutil.which` 二者取先命中）；找不到时抛 `RuntimeError: LibreOffice not found...`。
    2. **默认超时 90 秒**（`DEFAULT_TIMEOUT = 90.0`）。
    3. **`DOCX_MCP_PDF_TIMEOUT` 实际解析规则**（逐条写，禁止含糊）：未设 / 空字符串 → 90 s；非数值（`float()` 失败）→ 90 s；数值 **≤ 0** → 90 s；正数值 → 采用该值。
    4. **为什么是 90**：必须明显低于部署侧客户端硬上限（`mcp.timeout.execution` = 120000 ms = 120 s），否则客户端先放弃、挂起不会以显式错误暴露。
    5. **超时/失败行为**：超时抛 `RuntimeError: ... timed out after Ns (set DOCX_MCP_PDF_TIMEOUT to change the limit)`；非零退出抛含 `exit <code>` 与 stderr 的 `RuntimeError`。
    6. **singleton 限制（关键）**：`convert_to_pdf` **没有 `document_handle` 参数**，内部走 `__default__` 槽位；因此当设了 `DOCX_MCP_REQUIRE_HANDLE=1`（singleton 模式）时，该工具**当前不可用**，调用会抛 `RuntimeError: document_handle is required in singleton mode ...`。需多会话隔离时改用 `save_document(output_path=..., document_handle=...)` 保存 DOCX 后自行转换。
  - 依据：F6、F7、F8、F9、F10。
- **修改边界**
  - ⛔ 不改 `docx_mcp/document/pdfexport.py` / `docx_mcp/server.py`；⛔ 不承诺「已支持 handle」（事实相反，见 F9/F14）。
  - ⛔ **不得**写成 lock 文件检查 / 依赖锁内容（上一轮 explore 的错误映射，明确排除）。
  - ⛔ 不写未验证的平台细节（如 Windows 下 soffice.exe 路径猜测）。
- **质量检查方式**
  - 90 与解析规则由脚本从 `pdfexport.py` 解析比对，README 不得出现与源码不一致的数值。
- **验收标准**
  - ✅ **[T-B] 数值与源码一致 + singleton 限制在位**
    ```bash
    python3 - <<'PY'
    import re, pathlib
    root = pathlib.Path('/home/gw/opt/docx-mcp')
    pdf = (root/'docx_mcp/document/pdfexport.py').read_text()
    default = float(re.search(r'DEFAULT_TIMEOUT\s*=\s*([0-9.]+)', pdf).group(1))
    assert default == 90.0
    rd = (root/'README.md').read_text()
    sec = rd.split('### PDF Export',1)[1].split('\n## ',1)[0]
    assert 'DOCX_MCP_PDF_TIMEOUT' in sec
    assert re.search(r'\b90\b', sec), 'default timeout 90 not stated'
    assert 'libreoffice' in sec.lower() and 'soffice' in sec.lower() and 'PATH' in sec
    assert re.search(r'(≤|<=|小于等于)\s*0|non-positive|non-numeric|非数值', sec), 'parsing rules incomplete'
    assert 'DOCX_MCP_REQUIRE_HANDLE' in sec and re.search(r'no\s+document_handle|没有\s*`?document_handle`?|缺\s*`?document_handle`?', sec), 'singleton limitation missing'
    print('OK default=%s' % default)
    PY
    ```
    exit 0。**能失败证明（反例锚定）**：把 README 的 90 改成 120，或删掉 singleton 段落 → 对应 `assert` 失败；把 `DOCX_MCP_PDF_TIMEOUT` 解析规则写成「任意值直接采用」→ 规则行 `assert` 失败。
  - ✅ **[T-A] 事实一致性（文档不得与代码相反）**
    ```bash
    cd /home/gw/opt/docx-mcp
    grep -n 'def convert_to_pdf' -A 1 docx_mcp/server.py | grep -q 'document_handle' && echo 'INCONSISTENT: handle now exists — README claim must be revised' || echo 'OK: no handle, README claim true'
    ```
    期望输出 `OK: no handle, README claim true`（若代码已加 handle，则本任务须改为描述新行为并回写本计划）。
  - ✅ **[T-C] 只含声明文件**：`git diff --stat --name-only` 恰为 `README.md`。
- **潜在风险**：小节位置若插到 `## Requirements` 之外（例如文件末尾）会使文本脱离 `## How It Works` → 由锚点约束避免；`f` 字符串中的 `{timeout:g}` 在 README 里勿原样粘贴为未渲染变量对外观的影响（可接受）。
- **Commit**：`docs(readme): document PDF export prerequisites, timeout rules, singleton limitation — done 100% #T-5169`

---

### W4 — D5 (#5170)：按当前代码/git 证据刷新路线图与验证报告状态

- **依赖**：无（文件与 README 不重叠；**可并行起草**，commit 串行） ｜ **frontier**：是
- **执行者**：Dev Orchestrator / Technical Writer
- **预估墙钟**：≤ 25 min（两个文件，可拆为 2×≤15 min：先 roadmap，后 review）
- **修改内容**（两个文件；**追加式**，不删原文）
  - 文件 A：`/home/gw/opt/docx-mcp/docs/plans/2026-07-27-real-world-defects-roadmap.md`
    - 在每个 `### Bug N` / `### Feature N` / `### Design N` 标题后**新增一行状态**，格式统一：
      `**状态（2026-11-02 复核）**：✅ FIXED — commit \`<hash>\`（合入 \`<merge-hash>\`）` 或 `🟡 PARTIAL — 残余：<工具名列表>` 或 `⬜ OPEN — 未实现（证据：<符号名>）`
    - 取值严格按 §2「D5 目标状态表」：Bug 1 FIXED(`6d393a5`/`f5face8`)、Bug 2 OPEN(`compare.py::_body_paragraphs` 仅 `w:p`)、Bug 3 FIXED(`8fb3fa0`)、Feature 1 FIXED(`71438c8`/`3a944d0`)、Feature 2 PARTIAL(6 个工具)、Feature 3 OPEN、Design 1–3 OPEN。
    - 「优先级总览」表新增一列 `状态`（值同上），并在表下加一行 note 指向本次复核日期与「新增条目」（`DOCX_MCP_REQUIRE_HANDLE` / note 保留 / PDF 超时）。
  - 文件 B：`/home/gw/opt/docx-mcp/.github/reviews/defect-roadmap-verification-2026-07-27.md`
    - 在**文件末尾追加** `## 状态更新（2026-11-02 复核）` 小节，含：
      1. 状态表（INC-/CQ-/BUG-/OPT- id → 现状 FIXED/PARTIAL/OPEN → 证据 commit 或符号）；
      2. 明确标注 **行号漂移**：原文引用的 `tracks.py:289`、`compare.py:28-32`、`formatting.py:140`、`server.py:2937/2952` 等**已失效**，一律改用符号锚（`tracks.py::_resolve`、`compare.py::_body_paragraphs`、`formatting.py::update_paragraph`、`server.py::convert_to_pdf`）；
      3. 修正 Feature 2 勘误表的**当前**事实：已支持 handle 者含 `accept_changes`/`reject_changes`/`generate_change_summary` **+ 原表未列的 `copy_document`/`update_image`**（F11）；仍缺 handle 者 6 个（F14）。
    - **禁止**改动该报告原有章节正文（保留原始审阅记录以便追溯）；只追加。
- **修改边界**
  - ⛔ 不得修改除上述两个文件外的任何文件（尤其不得改 `docx_mcp/**`、`tests/**`）。
  - ⛔ 不得引用未实测的 commit；每个 hash 必须可 `git cat-file -e <hash>` 通过且为 HEAD 祖先。
  - ⛔ 不得把 Bug 2 / Feature 3 / Design 1–3 标为 FIXED；不得把 Bug 1 / Bug 3 / Feature 1 标为 OPEN。
  - ⛔ 不得在本计划之外新建实现计划或 PM 任务。
- **质量检查方式**
  - 文档内所有引用的 commit hash 做「存在 + 祖先」机械校验；
  - 文档状态与代码事实做交叉校验（handle 覆盖率、结构性检测缺失）。
- **验收标准**
  - ✅ **[T-B] 引用 commit 全部可验证且为 HEAD 祖先**
    ```bash
    cd /home/gw/opt/docx-mcp
    python3 - <<'PY'
    import re, subprocess, pathlib
    root = pathlib.Path('/home/gw/opt/docx-mcp')
    docs = [root/'docs/plans/2026-07-27-real-world-defects-roadmap.md',
            root/'.github/reviews/defect-roadmap-verification-2026-07-27.md']
    hashes = set()
    for d in docs:
        hashes |= set(re.findall(r'\b([0-9a-f]{7,40})\b', d.read_text()))
    assert hashes, 'no commit hashes cited'
    for h in sorted(hashes):
        subprocess.run(['git','cat-file','-e',h+'^{commit}'], check=True, cwd=root)
        assert subprocess.run(['git','merge-base','--is-ancestor',h,'HEAD'], cwd=root).returncode == 0, h
    print('OK verified', len(hashes), 'hashes')
    PY
    ```
    exit 0。**能失败证明（变异法）**：把任一 hash 改成 `deadbee` → `check=True` 抛 `CalledProcessError`；填一个存在但非祖先的 hash → 第二个断言失败。
  - ✅ **[T-B] 状态标记与代码事实交叉一致**
    ```bash
    cd /home/gw/opt/docx-mcp
    python3 - <<'PY'
    import re, pathlib
    root = pathlib.Path('/home/gw/opt/docx-mcp')
    rd = (root/'docs/plans/2026-07-27-real-world-defects-roadmap.md').read_text()
    rv = (root/'.github/reviews/defect-roadmap-verification-2026-07-27.md').read_text()
    srv = (root/'docx_mcp/server.py').read_text()
    cmp_ = (root/'docx_mcp/document/compare.py').read_text()
    # 1) Bug2 仍未修复 -> 文档不得称 FIXED
    assert 'w:tbl' not in cmp_ and 'graphicData' not in cmp_
    bug2 = rd.split('Bug 2',1)[1].split('### Bug 3',1)[0]
    assert not re.search(r'FIXED', bug2), 'Bug 2 must not be marked FIXED'
    assert re.search(r'OPEN', bug2)
    # 2) Bug1 / Bug3 / Feature1 已修复
    assert re.search(r'FIXED', rd.split('Bug 1',1)[1].split('### Bug 2',1)[0])
    assert re.search(r'FIXED', rd.split('Bug 3',1)[1].split('## Phase 2',1)[0])
    assert re.search(r'FIXED', rd.split('Feature 1',1)[1].split('### Feature 2',1)[0])
    # 3) handle 覆盖率与源码一致（6 缺 / 2 已补）
    for fn, has in [('def copy_document(', True), ('def update_image(', True),
                    ('def convert_to_pdf(', False), ('def sanitize_metadata(', False),
                    ('def find_replace_formatted(', False), ('def get_document_outline(', False),
                    ('def accept_all_changes(', False), ('def reject_all_changes(', False)]:
        blk = srv.split(fn,1)[1][:200]
        got = 'document_handle' in blk
        assert got == has, (fn, got, has)
    # 4) 复核小节存在 + 行号漂移说明存在
    assert '2026-11-02' in rv and re.search(r'(行号|锚点).{0,20}(漂移|失效)', rv)
    print('OK cross-check')
    PY
    ```
    exit 0。**能失败证明（实现回退法）**：把 Bug 2 段改为 `FIXED` → 断言失败；把 `convert_to_pdf` 的 handle 事实写反 → 第 3 组断言失败。
  - ✅ **[T-C] 只含声明文件**：`git diff --stat --name-only` 恰为这两个文件。
- **潜在风险**：路线图原文较长，追加行位置易错 → 用 `### Bug N` / `### Feature N` 标题锚（各出现一次）；若标题被改动则先 STOP 并回写。
- **Commit**：`docs(roadmap): refresh defect roadmap + verification review against current code — done 100% #T-5170`
- **拆分（可选，若单项 >15 min）**：5a = 仅 roadmap（产物 = roadmap 状态行 + 总览列，验收 = 上面 T-B 的第 1/2 组断言）；5b = 仅 review（产物 = 追加小节，验收 = 第 4 组断言 + hash 校验）。两子任务共用同一 commit 或拆两 commit 均可，但 commit message 均带 `#T-5170`。

---

## 5. Execution Wave（并行与串行）

| Wave | 任务 | Frontier | 依赖已完成 | 说明 |
|------|------|----------|-----------|------|
| W1 | D2 (#5167) ∥ D5 起草 (#5170) | 是 / 是 | — | 文件不重叠；**commit 串行**（单写者） |
| W2 | D3 (#5168) | 否 | D2 committed | 同一 README，必须串行 |
| W3 | D4 (#5169) | 否 | D3 committed | 同一 README，必须串行 |
| W4 | D5 commit（若 W1 未提交） | 是 | — | 收尾 |

顺序理由：D2→D3→D4 均写 `README.md`，并发会互相覆盖 → 强制串行（CoT：唯一冲突资源是 README 文件；D5 与 README 无重叠故可并行编辑，但 git index 为共享资源，提交必须串行）。

---

## 6. Post-Execution Verification

### Automated（Dev Orchestrator 自动执行）

> **区间口径修正（2026-11-02 14:09 CST，收尾时实测）**：V1/V3 原写 `HEAD~4..HEAD`，**与实际不符**——D2–D5 实际产生 **5** 个文档 commit（`976f415` D2 · `1f45138` D3 · `e5f0053` D4 主体 · `5a1351e` D5 · `56fec9e` D4 follow-up，见 §8 #5 / §9.1），`HEAD~4` 会漏掉 `976f415`（D2）。**正确区间为 `ec5fcd7..HEAD`**（`ec5fcd7` = 上一轮 T2 整合提交，不含）。下表已按修正口径更新。

| ID | 描述 | 命令 | 期望 |
|----|------|------|------|
| V1 | 四任务 diff 范围收敛 | `git diff --stat --name-only ec5fcd7..HEAD` | 恰为 `README.md`、`docs/plans/2026-07-27-real-world-defects-roadmap.md`、`.github/reviews/defect-roadmap-verification-2026-07-27.md` |
| V2 | README 与源码一致性（D2/D4） | §4 W1/W3 的 T-B 脚本 | 全部 exit 0 |
| V3 | 无源码/测试改动 | `git diff --stat ec5fcd7..HEAD -- docx_mcp tests pyproject.toml uv.lock` | 空输出 |
| V4 | 文档引用 commit 可验证 | §4 W4 T-B 脚本 1 | exit 0 |
| V5 | 文档状态 vs 代码事实 | §4 W4 T-B 脚本 2 | exit 0 |
| V6 | 链接/标题结构完整性 | `python3 - <<'PY'`：assert README 中 `## Requirements`、`### Footnotes & Endnotes`、`### PDF Export` 各出现恰 1 次 | exit 0 |

### Manual（仅真正需要人工判断）

- [ ] M1: 通读 README 新增三段，确认**没有**承诺未实现的能力（尤其 PDF + handle、note 全保留）。
- [ ] M2: 确认路线图/报告的原文章节未被删除（`git diff` 应只见新增行，`git diff --stat` 的删除行数应为 0 或仅格式空白）。

---

## 7. 审查日志

| 轮次 | 聚焦 | 发现问题数 | 已修正 | 剩余 |
|------|------|-----------|--------|------|
| R1 | 结构完整性 / 任务-需求一一对应（D2–D5 全覆盖，无越界） | 2 | 2 | 0 |
| R1.5 | 外部引用事实核查（F1–F15 全部仓内实测；commit 祖先性已验） | 3 | 3 | 0 |
| R2 | 可执行性（AC 脚本干跑语义、只读、无网络） | 2 | 2 | 0 |
| R2.8 | LLM 可执行性（锚点唯一性、插入点无歧义、禁止项显式） | 2 | 2 | 0 |
| R3 | 风险与边缘（粒度门 / 基线漂移 / 跨任务一致性） | 2 | 2 | 0 |
| **终止** | **T2 — issue 清零（11 项全部修正，无残留）** | | | **0** |

**R1.5 修正记录**：
- 剔除上一轮 explore 的错误映射（D3=version reporting、D4=lock 检查）→ 改写为 note 保留语义 / PDF 导出链路。
- 按实测事实修正 D5 状态：Bug 3 已由 `8fb3fa0` 修复（原 issue 表可能标 OPEN）；Feature 2 增补 `copy_document`/`update_image` 已支持。
- 明确 `server.py` 行号已漂移 → 文档改用符号锚。

**R3 粒度门**：D2 ≤10 min，D3 ≤15 min，D4 ≤20 min，D5 ≤25 min（可拆 2×≤15 min）→ 全部 ≤30 min，无需用户额外授权。

---

## 8. 执行期发现（回写区）

| # | 任务 | 发现 | 处理 |
|---|------|------|------|
| 1 | D4 | README 现有文本无其他「mcp 版本」表述；`### Footnotes & Endnotes` 位于 `<details>`（Full tool inventory）折叠块内，D3 追加段落随之落在该折叠块内 | 按计划锚点执行，未越界；后续可将 note 保留语义移出折叠块（不在本范围） |
| 2 | D5 | 「优先级总览」表按计划新增 `状态` 列 → 该表 9 行被重写（内容不变 + 新列），故 roadmap `--numstat` 显示 9 处删除（非内容删除，M2 判定可接受） | 保留；原文正文零删除 |
| 3 | D5 | 计划 §2 F12 未列 `5b362d8`（Bug 3 的 merge commit） | 本次复核已补充引用 |
| 4 | — | AC 脚本 `\b([0-9a-f]{7,40})\b` 会误匹配 7+ 位全 hex 单词（如 `defaced`）或紧凑日期 `20261102` | 新增文本经扫描无此类误匹配（AC1 报 9 hashes 全为真实 commit） |
| 5 | D4 | `_resolve_timeout` 对超大正数值不做上限裁剪（仅 `>0` 即采用）；`NaN` 与 `inf` 边界未在 README 说明 | **已跟进**：追加 1 句 edge-case 说明（commit `56fec9e`），见 §9 追加验收反馈 |
| 6 | D4 followup | 实测 `_resolve_timeout`：`nan/NaN` → 90.0；`inf/+inf/Infinity/1e400` → `inf`（被采用）；`-inf` → 90.0。实测 `subprocess.run(timeout=float('inf'))` 在本机（Linux / CPython 3.12.3）**立即抛 `OverflowError: cannot convert float infinity to integer`**（并非无界等待） | 按用户措辞保守表述为 “may fail in subprocess/platform handling”，不承诺必然无界等待 |

---

## 9. Execution Log（执行记录，2026-11-02）

**执行环境**：`/home/gw/opt/docx-mcp`，起始 HEAD `ec5fcd7`（与计划 §2 一致，无基线漂移）；`F11 OK`；起始未跟踪项仅 `.github/plans/completed/`、`.github/plans/docs-followup.md`、`.pm-project`、`.pm-project.json`、`traces/`，执行期未触碰。

| 任务 | 状态 | RED 证据 | GREEN 证据 | commit | diff 范围 |
|------|------|---------|-----------|--------|-----------|
| W1 D2 #5167 | ✅ done | `AssertionError: README Requirements missing mcp>=2,<3`（exit 1） | exit 0，`mcp>=2,<3` 与 pyproject 同源 | `976f415` | `README.md` |
| W2 D3 #5168 | ✅ done | `AssertionError: README missing structural note type separator`（exit 1） | exit 0，3 个 type 名与 `base.py` frozenset 一致 | `1f45138` | `README.md` |
| W3 D4 #5169 | ✅ done | `IndexError: list index out of range`（exit 1，`### PDF Export` 不存在） | exit 0，default=90.0；T-A `OK: no handle, README claim true` | `e5f0053` | `README.md` |
| W4 D5 #5170 | ✅ done | AC1 `AssertionError: no commit hashes cited`（exit 1）；AC2 `AssertionError`（exit 1） | AC1 exit 0（9 hashes 全为 HEAD 祖先）；AC2 exit 0 | `5a1351e` | roadmap + review |

**变异（能失败证明）复测**：D2 改回 `mcp>=1.28,<2` → 失败；D3 `continuationNotice`→`continuation` → 失败；D4 删除 singleton 限制 → 失败；D5 Bug 2 改 `FIXED` → 失败；D5 hash 改 `deadbee` → `CalledProcessError`。全部按预期失败。

**Post-Execution Verification**：
- V1 ✅ `git diff --stat --name-only ec5fcd7..HEAD` = `README.md`、`docs/plans/2026-07-27-real-world-defects-roadmap.md`、`.github/reviews/defect-roadmap-verification-2026-07-27.md`。（原写 `HEAD~4..HEAD`，口径已按 §6 注记修正）
- V2 ✅ D2/D3/D4 T-B 脚本全部 exit 0。
- V3 ✅ `git diff ec5fcd7..HEAD -- docx_mcp tests pyproject.toml uv.lock` 空输出。（同上修正）
- V4 ✅ D5 引用 commit 全部可验证且为 HEAD 祖先（9 个）。
- V5 ✅ D5 状态标记与代码事实交叉一致。
- V6 ✅ `## Requirements` / `### Footnotes & Endnotes` / `### PDF Export` 各恰 1 次。

**scope 负向验证**：四次 commit 均单任务单 commit；`git diff --stat` 每次仅含声明文件；未 push；未操作 PM（仅 commit trailer 带 `#T-<id>`）。

### 9.1 追加验收反馈（D4 PARTIAL → follow-up，2026-11-02）

**反馈**：D2/D3 PASS；D4 PARTIAL（无 blocking，仅 README 缺非有限值边界说明）。要求仅 README 补 1 句、禁止代码改动、单独 `#T-5169` follow-up commit。

**实测 nan/inf 解析**（真源 `docx_mcp/document/pdfexport.py::_resolve_timeout`）：

| env 值 | 解析结果 |
|---|---|
| `nan` / `NaN` | `90.0`（NaN > 0 为 False → 回落） |
| `inf` / `+inf` / `Infinity` / `1e400` | `inf`（`> 0` → 被采用） |
| `-inf` / `1e-400` / `0` / `-5` | `90.0` |
| `120` | `120.0` |

**实测 subprocess 处理**：`subprocess.run(timeout=float('inf'))` 在 Linux / CPython 3.12.3 下**立即抛** `OverflowError: cannot convert float infinity to integer`（示例 `true` 与 `sleep 1` 均如此）→ 非无界等待，故文档保守写 “may fail in subprocess/platform handling”。

**RED/GREEN**：RED = `AssertionError: NaN edge case not documented`（exit 1）；GREEN = exit 0（NaN / inf / support-disclaimer / finite-guidance 四项断言通过，断言前做 markdown 强调归一化）。变异复测（删 NaN / 删 disclaimer / 删 finite 指引）全部按预期失败。原 D4 T-B AC 复跑仍 exit 0（无回归）。

**产物**：commit `56fec9e`（`README.md` 单文件，追加 1 句 `**Edge cases** — …`）。未改代码；未 push。

---

## 10. 发布记录与最终状态（2026-11-02 14:09 CST 追加）

> 本节为**追加记录**。日期取自 `date` 实测：`2026-11-02 14:09:41 CST`。

### 10.1 发布结果

| 项 | 实测 |
|---|---|
| `main` | `56fec9ef3ff870c4327d0eebf161143a2f4a7c08` |
| `origin/main` | `56fec9ef3ff870c4327d0eebf161143a2f4a7c08`（**与 main 一致**） |
| ahead / behind | **0 / 0**（`git rev-list --count` 双向） |
| push 方式 | **普通 `git push`（非 force）**，成功 |
| `ec5fcd7..HEAD` | **5** commit / **3** 文件：`README.md`、`docs/plans/2026-07-27-real-world-defects-roadmap.md`、`.github/reviews/defect-roadmap-verification-2026-07-27.md` |

§9 末「未 push」为该时点事实；现已被本节覆盖——**文档 commit 已推送至 `origin/main`**。

### 10.2 Post-Execution Verification 复跑（按修正区间 `ec5fcd7..HEAD`）

| ID | 结果 |
|---|---|
| V1 | ✅ 恰 3 文件（见上表） |
| V2 | ✅ `D2 OK mcp>=2,<3`；`D3 OK ['separator','continuationSeparator','continuationNotice']`；`D4 OK default=90.0` |
| V3 | ✅ `docx_mcp tests pyproject.toml uv.lock` 改动为空 |
| V4 | ✅ `checked 9 hashes; bad: []` |
| V5 | ✅ `D5 AC2 OK`（Bug 2 非 FIXED；handle 覆盖率 2 补 / 6 缺与源码一致） |
| V6 | ✅ `## Requirements`=1 · `### Footnotes & Endnotes`=1 · `### PDF Export`=1 |

> V1/V3 原写 `HEAD~4..HEAD`，已按 §6 顶部注记修正为 `ec5fcd7..HEAD`（实际 5 个文档 commit，`HEAD~4` 会漏 `976f415`）。

### 10.3 D2–D5 独立验收

| 任务 | PM | progress | 独立复跑 |
|---|---|---|---|
| D2 #5167 | `done` | 100% | **PASS** |
| D3 #5168 | `done` | 100% | **PASS** |
| D4 #5169 | `done` | 100% | **PASS**（含 follow-up `56fec9e`） |
| D5 #5170 | `done` | 100% | **PASS** |

### 10.4 偏差登记（不得静默升级）

1. **D4 补充提交偏差**：D4 原计划单 commit，实际 **2 个**（`e5f0053` 主体 + `56fec9e` NaN/inf follow-up，均 `#T-5169`、均仅改 `README.md`）。D4 首轮 verdict 为 **PARTIAL**（无 blocking），追加说明后 PASS。
2. **D1 边界**：仅**后端** systemd 重启 HTTP 服务后 `open`/`save`/`close` 成功；**未重启 OpenCode 客户端**，客户端侧未验证。
3. **M1 边界**：仅 **LibreOffice** 打开样本验证；**Word 原生**未执行，M1 记 **PARTIAL**。
4. **PDF singleton 缺 handle 遗留**：`convert_to_pdf` 仍无 `document_handle`，`DOCX_MCP_REQUIRE_HANDLE=1` 下不可用 → **known issue，未修复**。

### 10.5 最终状态

**状态：COMPLETED** — D2–D5 全部 PASS 并已随普通 push 同步至 `origin/main`（`56fec9e`）；PM 四任务 done 100%；上列 4 项偏差为已登记的证据边界，不属未完成项。

**归档**：本计划移至 `.github/plans/completed/docs-followup.md`（全部任务 ✅ 完成，符合归档判据）。


