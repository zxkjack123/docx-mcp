# Plan: 上游 Tier 0 三项独立落地（#5128 / #5129 / #2615）

| 字段 | 值 |
|------|-----|
| **Status** | COMPLETED — 2026-10-31 23:07 CST（T1/T2/T3 三个独立 commit 已提交、未 push；独立验收 verdict = **PASS** ×3）；**2026-11-02 11:05 CST 追加整合后证据（见 §整合后阶段 A：rebase 后状态 / #2615 superseded / 全量门复跑 / 部署侧验证边界）——仍 COMPLETED，但 push 未成功、验证范围有限，见该节「证据边界」** |
| **Plan File** | `.github/plans/2026-10-30-upstream-tier0-rollout.md` |
| **PM Tasks** | #5128（endnote structural/pinned 修复）· #5129（pdfexport stdin/timeout）· #2615（mcp pin `>=1.28,<2`） |
| **Repo** | `/home/gw/opt/docx-mcp`（origin: `zxkjack123/docx-mcp`；上游 `SecurityRonin/docx-mcp`） |
| **Baseline HEAD（规划时实测）** | `4e53bc0` — 执行时**必须重测**，禁止沿用本值 |
| **Scope Mode** | HOLD（两个 bug fix + 一个依赖约束 pin；不扩不缩） |
| **Generated** | 2026-10-30 21:11 CST（`date` 实测） |
| **Plan Version** | v1.2（R5 修订：CT 第 2 轮 verdict=MINOR 的唯一 blocking NEW-B1 落地——T3 churn 集四项→三项，根 `version = "0.7.4"` 改为允许随提交（基线 stale 修正），`uv lock --check` 门禁恢复为**可通过**且已实测 exit 0；见 §审查日志 R5） |
| **预估总墙钟** | T1 ≤30 min · T2 ≤30 min · T3 ≤30 min（合计 ≤75 min，含证伪/审计开销） |
| **Commit 形态** | 3 个独立 commit，互不依赖，顺序建议 #5128 → #5129 → #2615 |
| **Push** | 禁止（`git push` 不在任何 task 范围内） |

---

## 背景与目标

三个上游 Tier 0 PR 各自独立、文件范围互不重叠，可逐个落地为独立 commit：

| PM Task | 上游 PR | 本质缺陷 | 落地文件 |
|---|---|---|---|
| #5128 | [PR #25](https://github.com/SecurityRonin/docx-mcp/pull/25) | `_pre_save_repair` 仅以「body 无 `w:endnoteReference`」为判据删 endnote，误删 Word 必需的结构性/pinned endnote → 保存后注释区丢失或 Word 报损坏 | `docx_mcp/document/base.py` + `tests/test_e2e.py` |
| #5129 | [PR #22](https://github.com/SecurityRonin/docx-mcp/pull/22) | `subprocess.run` 未设 `stdin=DEVNULL`、无 `timeout` → MCP stdio 下 soffice 可能等 stdin 挂起，挂起时客户端只看到无信息超时 | `docx_mcp/document/pdfexport.py` + `tests/test_pdf_export.py` |
| #2615 | [PR #16](https://github.com/SecurityRonin/docx-mcp/pull/16) | `pyproject.toml` 为 `mcp>=1.0.0` 无上界 → fresh install 可能拉 MCP SDK 2.x 导致导入失败 | `pyproject.toml` + `uv.lock` |

**非目标（Out of Scope）**
- 不实现 PR #16 分支上的其他改动（该分支污染，见 §风险 R-1）。
- 不改 `repairs` 返回值语义、不改 `convert_to_pdf` 公开签名、不新增 MCP 工具。
- 不修 `uv.lock` 既有工作树 churn——churn 集合**三项**：`revision = 3`、全量 `upload-time`、根项目块新增的 `provides-extras = [...]`（uv 0.12 元数据，HEAD 无；R4 实测）。**注意 ①**：pin 派生的顶层 `resolution-markers`（3 支 → 6 支）与 `exceptiongroup` / `numpy` / `pydantic-core` 版本行**属于本题语义，必须随本题提交**（见 D-1、S4 允许集）。**注意 ②**：根项目 `version = "0.7.4"` **不是 churn，必须随本题提交**——HEAD 的 `pyproject.toml:7` 已是 `0.7.4`，而 `HEAD:uv.lock` 根包仍是 `0.7.3`（基线 stale），若回退根 version 则 `uv lock --check` 必然失败（R5 实测：回退 0.7.3 → exit 1；保留 0.7.4 → exit 0）。
- 不 push、不建分支、不动 `.github/` 下既有 plan/review 文件与 `traces/`。

---

## 需求理解（CoT Stage 1 — 需求拆解）

```
REQUIREMENT: 为 3 个已登记 PM 任务（#5128/#5129/#2615）产出可直接执行计划；
             3 个独立 task、独立 commit、互不依赖；每 AC 给可执行命令与期望 exit code；
             新增测试先 RED 后 GREEN 并保留证据；#2615 必须非破坏性处理既有 uv.lock 改动。
↓
CONSTRAINTS:
  C1 文件范围硬约束：T1 = base.py + 既有测试文件；T2 = pdfexport.py + 既有测试文件；T3 = pyproject.toml + uv.lock
  C2 每 task 独立 commit，message 含 #T-<task_id>，不 push
  C3 #2615 不得 git checkout / git reset / 覆盖 uv.lock；不得提交无关 hunk
  C4 PR #16 分支污染 → 禁止整支 cherry-pick，只实现 pin 语义
  C5 每 task 预估墙钟 ≤30 min（PM #4943 粒度门）
↓
BOUNDARY（IN）: 上述 4 个源文件 + 2 个测试文件的最小改动 + 3 个 commit + 计划文件自身
BOUNDARY（OUT）: 其他任何源文件、CI 配置、依赖组、README、版本号、push
↓
ACCEPTANCE（二元）:
  A1 每个 PM 任务「原文 AC」逐条有对应可执行命令，退出码与期望一致
  A2 新增测试存在 RED 证据（未改实现时失败）与 GREEN 证据（改后通过）
  A3 三个 commit 的 `git diff --cached --name-only` / commit 内容严格落在声明文件内
  A4 #2615 完成后工作树既有 `M uv.lock` 语义保留（无 checkout/reset），提交的 lock 不含三项格式 churn（`revision`/`upload-time`/`provides-extras`）且根 version 保持 0.7.4（与 pyproject 一致）
```

---

## 假设清单（CoT Stage 2 — 含影响与验证）

| # | 假设 | 依据 | 若证伪的影响 / 处置 |
|---|---|---|---|
| A-1 | 上游 PR #25/#22 的补丁语义可直接套用到本仓（base.py L281 / pdfexport.py L43 结构一致） | 已拉取两份 `.diff` 并与本仓源码逐行比对（base.py L281-324、pdfexport.py L43-59 与补丁上下文一致） | 若执行时上下文不匹配 → 不硬套补丁，按 §Task 中「语义」实现，并记录偏差 |
| A-2 | 本仓 `tests/test_e2e.py::TestAutoRepairOnSave` 是 #5128 的合适落点，且现有 `test_strips_orphan_endnotes` 断言的正是「真孤儿仍应删除」（保留不改） | 上游 PR #25 diff 未修改该用例；本仓 L624-644 实测通过 | 若该用例因新逻辑失败 → 说明结构性判据过宽，回到实现调整（不是改测试） |
| A-3 | `mcp>=1.28,<2` 在本机可解析出 1.x 最新版（规划时实测 1.30.0），包总数不变 | `uv lock` 探针：94 packages 不变，mcp 自身依赖清单与 1.26.0 一致；**R4（CT 实测）补充**：pin 后顶层 `resolution-markers` 由 3 支派生为 **6 支**，且 `exceptiongroup` / `numpy` / `pydantic-core` 出现版本行变化（未 pin 对照组仍为 3 支、无这三处变化）→ 这些是 pin 的**语义派生**，必须提交 | 若解析出不同版本 → 版本号与包块按**实际解析结果**写入，禁止硬编码 1.30.0；若出现**允许集之外**的包名变化 → 停止并 D2 |
| A-4 | 与 #2615 无关的 churn **仅三项**：`revision = 3`、全量 `upload-time`、根项目块新增 `provides-extras = ["equations"]`；**根项目 `version` 不属于 churn 禁止集**——HEAD `pyproject.toml:7` 已是 `0.7.4`，而 `HEAD:uv.lock` 根包为 `0.7.3`（基线 stale），提交态必须保持 `0.7.4` | R5 实测（三项判据）：`git show HEAD:uv.lock` 头部为 `version = 1` 且**无** `revision` 行、无 `upload-time`、无 `provides-extras`；`git show HEAD:pyproject.toml` 第 7 行 `version = "0.7.4"`，`git show HEAD:uv.lock` 根包 `docx-mcp-server 0.7.3` → **HEAD 自身 `uv lock --check` 即 exit 1**（锁与 pyproject 不一致），故根 version 必须随提交修正为 0.7.4，否则门禁必然失败 | 若执行时发现**第四类**疑似 churn → 按「是否由 pin 或根 version 一致性引起」二分：由 pin 引起（markers/依赖版本行）或由根 version 一致性引起（`0.7.3→0.7.4`）→ 必须提交；否则 → 记录并 D2，禁止自行剥离 |
| A-5 | 既有 `M uv.lock` 属脏基线（非本次改动），本任务只允许在其之上追加，不允许还原 | PM #2615 notes「既有脏基线，禁止覆盖」+ `git status` 实测 | 若发现该 diff 含他人语义改动（非纯格式） → 停止，按 D2 上抛用户 |
| A-6 | 结构性 note 判据 = `w:type` ∈ **白名单** `{"separator","continuationSeparator","continuationNotice"}`，**或** id 被 `word/settings.xml` 的 `w:endnotePr` / `w:footnotePr` 列出 | **R4 事实修正（CT 实测）**：本仓 fixture `word/settings.xml` 实为**空** `<w:settings/>`（`tests/conftest.py::_SETTINGS_XML`），**不含** `w:endnotePr`。结构性数据在 `endnotes.xml`/`footnotes.xml`（`w:type="separator" id=-1`、`w:type="continuationSeparator" id=0`）。因此新测试中的 `w:endnotePr`/`w:footnotePr` 由 helper `_pin_in_settings` **自建** = 「模拟 Word 写法」，不依赖既有 fixture 数据 | 判据过宽/过窄 → 由 AC2 的「未知 type 孤儿仍删除」+ AC3-② 兜底；helper 静默失效（pin 未真正写入）→ 由 `_pin_in_settings` 内**回读断言**拦截（R4 新增） |

---

## 关键决策与权衡（CoT Stage 3）

**D-1（#2615）锁文件提交形态：语义最大 + churn 最小重建（选用）vs 提交整流重生成 lock**
- 备选 1（直接提交 `uv lock` 结果）：语义自洽且可被 `uv lock --check` 验证，但含三项无关 churn（`revision = 3` / 全量 `upload-time` / 根块 `provides-extras`），违反「不得提交无关 hunks」。
- 备选 2（`git add -p` 逐 hunk 挑选）：脆弱，且 staged blob 会混合 revision-1 头 + revision-3 字段，语义不自洽。
- **选用备选 3（语义最大 + churn 最小重建）**：以 S2 的 `uv lock` 产物（gen-after）为基底，**只回退三项 churn**——删除 `revision = 3`、删除全部 `upload-time`、删除根项目块新增的 `provides-extras = ["equations"]`（R4 实测：HEAD lock 无该字段，uv 0.12 才写）；**根项目 `version = "0.7.4"` 保持不动、随本题提交**（R5 修正：HEAD `pyproject.toml:7` 已是 0.7.4，锁内根包 0.7.3 属基线 stale；回退到 0.7.3 会使 `uv lock --check` 必然 exit 1，已实测）；**保留并提交全部语义派生**：mcp 包块（version/sdist/wheels）、顶层 `resolution-markers`（3 → 6 支）、`exceptiongroup` / `numpy` / `pydantic-core` 版本行、根 `requires-dist` 的 mcp specifier。用 `git hash-object -w` + `git update-index --cacheinfo` 暂存该 blob，**工作树文件零改动**。
- **门禁（R5 修正）**：形状类断言（hunk 数 / 加删行数）**不构成门禁**（`uv sync --frozen --dry-run` 对 stale lock 也 exit 0，已证伪）；可用门禁为 S4-(2) 的 `uv lock --check`（**实测可通过**：本重建形态 exit 0）+ S4-(1) 的**允许集分类器** + S4-(3) 的 PyPI sha256 回验三关并列。
- 残余风险：若执行机 uv 版本与规划时（0.12.0）不同 → 重建形态可能不再被 `uv lock --check` 接受 → 走 S4-(2b) 判别后进 S8-D2（届时以「probe（gen-after）通过而 min 失败」为证据，选项 (A) 才成立）。

**D-2（#5129）timeout 取值（R4 修正：120.0 → 90.0）**：模块级常量 `DEFAULT_TIMEOUT = 90.0` 秒，支持环境变量 `DOCX_MCP_PDF_TIMEOUT` 覆盖（非法值/≤0 回退默认）。理由：**必须显著小于部署侧 opencode `mcp.timeout.execution = 120000` ms（120 s）硬顶**——若等服务端 120 s 才动手，客户端会先超时，用户仍只看到无信息失败，本缺陷（挂起 → 明确失败）等于没修。90 s 既覆盖 LibreOffice headless 首启（profile 初始化）+ 大文档转换的数十秒量级，又给 MCP 层留约 30 s 把显式 `RuntimeError` 送达客户端。环境变量覆盖使部署侧无需改码即可调参。

**D-3（#5128）不改 `repairs` 语义**：新增 `skip` 判据只影响「哪些 note 参与孤儿清洗」，`orphan_endnotes_removed` / `orphan_footnotes_removed` 计数含义不变（仍为「真被删除的数量」），因此无需改调用方。

**D-4 任务顺序**：#5128 → #5129 → #2615。三者文件不重叠、无依赖；顺序仅出于风险递增（#2615 涉及锁文件与索引技巧，放最后，其失败不会阻塞前两项已提交成果）。

**D-5（#5128）结构性判据用白名单（fail-closed）——对上游 PR #25 的有意偏离**：
- 上游实现为 `type not in (None, "normal")`，属 **fail-open**：任何带自定义/未知 `w:type` 的孤儿 note 会被永久保留，孤儿清洗即失效。
- 本仓采用白名单 `_STRUCTURAL_NOTE_TYPES = {"separator", "continuationSeparator", "continuationNotice"}`；**未知 type 仍按孤儿处理**（fail-closed）。
- 偏离代价：Word 若新增结构性 note 类型，本仓会误删；由 `test_strips_orphan_with_unknown_type`（证明未知 type 被删）+ `test_keeps_structural_note_without_settings_entry`（证明三个已知类型被留）双向锁定。
- 归因：这是 **D1 偏差**（对上游 PR #25 的有意偏离），执行时须在 commit message 或 Execution Log 中记录，便于上游同步时复核。

**D-6（#2615）索引/工作树一致性**：本 task 的工作树 `uv.lock` 永远 ≠ 索引 `uv.lock`（索引 = 重建版）。因此：
- **禁止 `git commit -a` / `git commit -am`**（会把工作树 churn 直接卷入提交，绕过 S5 的 `update-index`）。
- 提交前以 `git write-tree` 与 S0 记录的 `git rev-parse HEAD^{tree}` 做 `diff-tree` 对照，提交后以 `git diff-tree --no-commit-id --name-only -r HEAD` 断言恰 2 文件。
- 中止路径只用 `git reset -q -- uv.lock`（仅清索引，不动工作树）。

---

## 基线快照与脏基线（执行时重测，禁止硬编码）

**每个 Task 第一步必须执行（基线漂移重检）**：

```bash
cd /home/gw/opt/docx-mcp
git rev-parse HEAD
git status --porcelain=v1
git diff --stat uv.lock
```

- 规划时实测：`HEAD = 4e53bc0`；`git status --porcelain` 输出恰为下列 **8 项**（1 项已跟踪修改 `M uv.lock` + 7 项未跟踪）。
- 执行时若出现**上表之外**的改动 → 先记录并纳入排除清单，再动手；若目标文件本身已被改 → 重新核对锚点（行号可能漂移），不得沿用本文行号。

**已知脏基线（任何 task 都不得提交、不得还原）**

| 状态 | 路径 |
|---|---|
| ` M` | `uv.lock`（uv 0.12.0 重新生成的**整体脏版本**：`revision = 3` + `upload-time` + 根块 `provides-extras` + 派生 markers + 根项目 `version = "0.7.4"`）。⚠️ 该工作树版本**整体不得提交**；T3 只提交 S3 重建版（**三项** churn 回退、根 version 保持 `0.7.4`、语义派生保留） |
| `??` | `.github/plans/`、`.github/reviews/`、`.pm-project`、`.pm-project.json`、`docs/plans/2026-07-27-real-world-defects-roadmap.md`、`docs/superpowers/docx-mcp-agent-pitfalls.md`、`traces/` |

**硬规则**：本计划自身（`.github/plans/2026-10-30-upstream-tier0-rollout.md`）为未跟踪文件，**不得**出现在任何 task 的 commit 中；所有 `git add` 必须显式列路径，**禁止 `git add -A` / `git add .`**。

**环境事实（规划时实测，执行时复核）**：`uv 0.12.0`；`.venv` 内 `mcp==1.26.0`；`tests/test_pdf_export.py` 5 passed；`tests/test_e2e.py -k endnote` 4 passed；`tests/test_footnote_endnote_crud.py` 27 passed。

---

## Phase 1 — Task T1：#5128 endnote structural/pinned 修复

| 字段 | 值 |
|---|---|
| **task_id** | #5128 |
| **依赖** | 无 |
| **frontier** | 是（文件与其他两个 task 不重叠；仅 commit 需串行） |
| **执行者** | Dev Orchestrator → 实现类 agent（后端/AI coding） |
| **预估墙钟** | 22–27 min（RED 6 + 实现 8 + GREEN/回归 6 + 提交 3）；checkpoint：10 min（RED 5 failed 取证）· 20 min（GREEN + 双回归通过） |
| **Commit message** | `fix(repair): 结构性/被 settings 固定的 footnote/endnote 不再被孤儿清洗删除 #T-5128` |

**modifications（严格限于此，共 2 个文件）**

| 文件 | 动作 |
|---|---|
| `docx_mcp/document/base.py` | 在 `_backup_if_exists` 之后、`_pre_save_repair` 之前新增 **1 个类属性 + 2 个方法**（`_STRUCTURAL_NOTE_TYPES` / `_is_structural_note` / `_settings_note_ids`）；在 `_pre_save_repair` 的 footnote/endnote 两个循环中插入 skip 判据（两处 id 比较统一为 `str(int(...))` 归一后对 `pinned` 判定） |
| `tests/test_e2e.py` | 在 `class TestAutoRepairOnSave:` 之前新增 3 个模块级 helper（含 `_pin_in_settings` 的回读断言）；在 `class TestAutoRepairOnSave` 内 `test_strips_orphan_endnotes` 之后新增 **4 个测试函数**（1 个单例 + 3 个 parametrize，共 **7 个 test id**） |

**修改边界（不得触碰）**

- ⛔ `tests/test_footnote_endnote_crud.py`（只作为回归对象，不改）
- ⛔ `docx_mcp/document/endnotes.py` / `footnotes.py` / `validation.py`
- ⛔ `repairs` 字典键名与语义、`_real_footnotes`、`get_endnotes` 的 id 过滤逻辑
- ⛔ `uv.lock`、`pyproject.toml`、以及任何未在 modifications 声明的文件
- ⛔ 不得修改既有 `test_strips_orphan_endnotes` 的断言（它守护「真孤儿仍被删除」）

### 执行步骤

**S1 基线重检**（命令见 §基线快照）→ 记录 `HEAD`、`git status --porcelain`；确认 `base.py` 仍含 `_pre_save_repair`、`tests/test_e2e.py` 仍含 `class TestAutoRepairOnSave`。

**S2 RED：先只加测试，不改实现**
在 `tests/test_e2e.py` 中 `class TestAutoRepairOnSave:` 之前插入以下 helper（与上游 PR #25 语义一致；`DocxDocument`、`etree`、`W`、`pytest` 均已在文件头导入，无需新增 import）：

```python
def _add_note(doc: DocxDocument, kind: str, note_id: str, note_type: str | None = None) -> None:
    """Append a footnote/endnote that no body text references."""
    tree = doc._tree(f"word/{kind}s.xml")
    note = etree.SubElement(tree, f"{W}{kind}")
    note.set(f"{W}id", note_id)
    if note_type:
        note.set(f"{W}type", note_type)
    t = etree.SubElement(etree.SubElement(etree.SubElement(note, f"{W}p"), f"{W}r"), f"{W}t")
    t.text = "note"
    doc._mark(f"word/{kind}s.xml")


def _pin_in_settings(doc: DocxDocument, kind: str, *note_ids: str) -> None:
    """List note ids in settings.xml <w:footnotePr>/<w:endnotePr>, as Word does.

    The fixture's settings.xml is an empty <w:settings/>, so this helper *builds* the
    element Word writes; the tests therefore simulate Word's output instead of relying
    on pre-existing fixture data.
    """
    settings = doc._tree("word/settings.xml")
    pr = etree.SubElement(settings, f"{W}{kind}Pr")
    for note_id in note_ids:
        etree.SubElement(pr, f"{W}{kind}").set(f"{W}id", note_id)
    doc._mark("word/settings.xml")
    # Anti-cheat guard: if the pin silently failed to land in settings.xml, the
    # "kept" assertions below would pass for the wrong reason. Fail loudly here.
    written = {n.get(f"{W}id") for n in settings.iter(f"{W}{kind}")}
    assert set(note_ids) <= written, f"settings pin not written for {kind}: {written}"


def _note_ids(doc: DocxDocument, kind: str) -> list[str]:
    return [n.get(f"{W}id") for n in doc._tree(f"word/{kind}s.xml").findall(f"{W}{kind}")]
```

在 `TestAutoRepairOnSave` 内、`test_strips_orphan_endnotes` 之后插入 4 个测试（前 3 个逐字照抄上游用例语义；第 4 个是本计划对上游的**有意偏离**守护，见 D-5）：

```python
    def test_keeps_continuation_notice_named_in_settings(self, test_docx: Path, tmp_path: Path):
        """The unreferenced continuationNotice endnote Word writes must survive a save."""
        server.open_document(str(test_docx))
        doc = server._doc
        _add_note(doc, "endnote", "3", note_type="continuationNotice")
        _pin_in_settings(doc, "endnote", "-1", "0", "3")

        out = tmp_path / "kept.docx"
        result = _j(server.save_document(str(out)))
        assert result["repairs"]["orphan_endnotes_removed"] == 0

        server.open_document(str(out))
        assert "3" in _note_ids(server._doc, "endnote")

    @pytest.mark.parametrize("kind", ["footnote", "endnote"])
    def test_keeps_structural_note_without_settings_entry(
        self, test_docx: Path, tmp_path: Path, kind: str
    ):
        """A typed separator/notice note is never an orphan, even beyond the reserved ids."""
        server.open_document(str(test_docx))
        _add_note(server._doc, kind, "5", note_type="continuationNotice")

        out = tmp_path / "kept.docx"
        result = _j(server.save_document(str(out)))
        assert result["repairs"][f"orphan_{kind}s_removed"] == 0

        server.open_document(str(out))
        assert "5" in _note_ids(server._doc, kind)

    @pytest.mark.parametrize("kind", ["footnote", "endnote"])
    def test_keeps_plain_note_named_in_settings(self, test_docx: Path, tmp_path: Path, kind: str):
        """A plain note is not an orphan while settings.xml lists its id."""
        server.open_document(str(test_docx))
        doc = server._doc
        _add_note(doc, kind, "7")
        _pin_in_settings(doc, kind, "7")

        out = tmp_path / "kept.docx"
        result = _j(server.save_document(str(out)))
        assert result["repairs"][f"orphan_{kind}s_removed"] == 0

        server.open_document(str(out))
        assert "7" in _note_ids(server._doc, kind)

    @pytest.mark.parametrize("kind", ["footnote", "endnote"])
    def test_strips_orphan_with_unknown_type(self, test_docx: Path, tmp_path: Path, kind: str):
        """The structural check is a whitelist: an unrecognised type is still an orphan.

        Guard for D-5: fail-open (`type not in (None, "normal")`) would keep this note
        forever, so this case must stay RED-proof against that regression.
        """
        server.open_document(str(test_docx))
        _add_note(server._doc, kind, "9", note_type="customOrphanType")

        out = tmp_path / "repaired.docx"
        result = _j(server.save_document(str(out)))
        assert result["repairs"][f"orphan_{kind}s_removed"] == 1

        server.open_document(str(out))
        assert "9" not in _note_ids(server._doc, kind)
```

运行 RED 取证并按原样保留输出：

```bash
cd /home/gw/opt/docx-mcp
.venv/bin/python -m pytest tests/test_e2e.py \
  -k "keeps_continuation_notice or keeps_structural_note or keeps_plain_note" -q
```

期望：**5 failed**（exit code 1）。若出现 `0 failed`，说明测试未真正触达缺陷，**停止并复查**（不得进入 S3）。

再单独取证 fail-closed 守护用例（它在 RED 阶段就应通过，因为它断言「未知 type 仍是孤儿」——旧代码本就删它）：

```bash
.venv/bin/python -m pytest tests/test_e2e.py -k "strips_orphan_with_unknown_type" -q
```

期望：**2 passed**（`[footnote]` / `[endnote]`）。此结果必须与上一命令**分开记录**：它证明判据是白名单而非 fail-open，不参与 RED 的 5 failed 计数。

**S3 实现（base.py）**
1) 在 `# ── Pre-save auto-repair ─────...` 注释块之后、`def _pre_save_repair` 之前新增 **1 个类属性 + 2 个方法**：

```python
    # Word's structural notes: never referenced by body text, but required to exist.
    # Deliberate D1 deviation from upstream PR #25 (`type not in (None, "normal")`):
    # a whitelist is fail-closed, so an unknown/typed orphan still gets cleaned up.
    _STRUCTURAL_NOTE_TYPES = frozenset(
        {"separator", "continuationSeparator", "continuationNotice"}
    )

    @classmethod
    def _is_structural_note(cls, note: etree._Element) -> bool:
        """True only for Word's own structural note types (fail-closed whitelist)."""
        return note.get(f"{W}type") in cls._STRUCTURAL_NOTE_TYPES

    def _settings_note_ids(self, kind: str) -> set[str]:
        """Note ids named in settings.xml <w:footnotePr>/<w:endnotePr>; Word needs them to exist."""
        settings = self._tree("word/settings.xml")
        if settings is None:
            return set()
        return {
            n.get(f"{W}id")
            for pr in settings.iter(f"{W}{kind}Pr")
            for n in pr.findall(f"{W}{kind}")
        }
```

2) footnote 分支（当前 L300-309 区域）：在 `ref_ids = ...` 之后加 `pinned = self._settings_note_ids("footnote")`，循环内 `fn_id = int(fn.get(...))` 之后加：

```python
                if self._is_structural_note(fn) or str(fn_id) in pinned:
                    continue
```

3) endnote 分支（当前 L312-324 区域）：在 `ref_ids = ...` 之后加 `pinned = self._settings_note_ids("endnote")`，并把既有的

```python
                en_id_str = en.get(f"{W}id", "0")
                if en_id_str in ("0", "-1"):
                    continue
                en_id = int(en_id_str)
```

改为（**id 口径统一**：两个分支都用 `str(int(...))` 归一后与 `pinned` 比较，避免 `"+3"` / `"03"` 之类原始字符串与 settings 写入值形态不一致）：

```python
                en_id_str = en.get(f"{W}id", "0")
                en_id = int(en_id_str)
                if en_id in (0, -1) or self._is_structural_note(en) or str(en_id) in pinned:
                    continue
```

> 行宽：上述 `if` 行超过 100 字符时按 ruff 规则折行（`ruff format` 会处理）；提交前 S5 的 `ruff format --check` 必须通过。

**S4 GREEN**：重跑 S2 的两条选择器 → 期望 **5 passed**（keeps_*）+ **2 passed**（strips_orphan_with_unknown_type），均 exit 0；保留输出作为 GREEN 证据。

**S5 回归**

```bash
.venv/bin/python -m pytest tests/test_e2e.py -k endnote -q          # 期望 7 passed（4 既有 + 3 新建 [endnote] 参数化 id）
.venv/bin/python -m pytest tests/test_footnote_endnote_crud.py -q   # 期望 27 passed
.venv/bin/python -m ruff check docx_mcp/document/base.py tests/test_e2e.py
.venv/bin/python -m ruff format --check docx_mcp/document/base.py tests/test_e2e.py
```

> 计数说明：`-k endnote` 按 node id 子串匹配。既有 4 个（`test_strips_orphan_endnotes`、`test_get_endnotes_survives_roundtrip`、`test_add_endnote_roundtrip`、`test_validate_endnotes_roundtrip`）+ 新建 3 个（`test_keeps_structural_note_without_settings_entry[endnote]`、`test_keeps_plain_note_named_in_settings[endnote]`、`test_strips_orphan_with_unknown_type[endnote]`）= 7；`test_keeps_continuation_notice_named_in_settings` 名称不含 `endnote`，不在该选择器内。判据以 **0 failed 且 ≥7 passed** 为准。

**S6 提交**

```bash
git add docx_mcp/document/base.py tests/test_e2e.py
git diff --cached --name-only          # 期望恰好 2 行
git diff --stat --cached               # 期望仅上述 2 文件
git commit -m "fix(repair): 结构性/被 settings 固定的 footnote/endnote 不再被孤儿清洗删除 #T-5128"
git status --porcelain                 # 期望回到「已知脏基线」集合（不含 base.py / test_e2e.py）
```

### 验收标准（原文 AC + 可执行命令）

| # | 原文 AC（PM #5128） | 可执行命令（`cd /home/gw/opt/docx-mcp`） | 期望 | 类型 | 能失败证明 |
|---|---|---|---|---|---|
| AC1 | `.venv/bin/python -m pytest tests/test_e2e.py -k endnote -q` → exit 0 | `.venv/bin/python -m pytest tests/test_e2e.py -k endnote -q` | exit 0，7 passed，0 failed | T-A | 实现回退法：注释掉 S3-3 的 skip 判据 → 新建 3 个 `[endnote]` 用例失败（`test_keeps_continuation_notice…` 由 AC3-① 守护） |
| AC2 | `tests/test_footnote_endnote_crud.py` 27 用例回归通过 | ① `.venv/bin/python -m pytest tests/test_footnote_endnote_crud.py -q`；② `.venv/bin/python -m pytest tests/test_e2e.py -k "strips_orphan_endnote or strips_orphan_with_unknown_type" -q` | ① exit 0，27 passed ② exit 0，3 passed（`test_strips_orphan_endnotes` 1 + 未知 type 孤儿 2，`orphan_*_removed == 1`） | T-A | 变异法 ①：把 `_is_structural_note` 改为恒 `True` → `test_strips_orphan_endnotes` 失败；变异法 ②：改回上游 fail-open（`type not in (None,"normal")`）→ `test_strips_orphan_with_unknown_type` 的 2 个 id 失败（**证明白名单是 fail-closed**） |
| AC3 | 用例须证明：含结构性 endnote（body 无引用但被 settings/`w:endnotePr` 固定）保存后仍存在；真孤儿仍被删除 | ① `-k "keeps_continuation_notice or keeps_plain_note or keeps_structural_note"`；② `-k test_strips_orphan_endnotes` | ① exit 0（5 passed）② exit 0（1 passed，`orphan_endnotes_removed == 1`） | T-B | 反例锚定：S2 的 RED 结果（5 failed）即为「未修复时失败」的证据；② 在结构性判据放宽后必须失败 |
| AC4 | `git diff --stat` 仅含声明文件，无夹带 | `git show --stat --oneline HEAD` + `git diff --cached --name-only` | 仅 `docx_mcp/document/base.py`、`tests/test_e2e.py` | T-C | 任一其他文件出现即失败（含 `uv.lock`、计划文件） |
| AC5 | 独立 commit，message 含 `#T-<task_id>`，不 push | `git log -1 --format=%s | grep -F "#T-5128"`；`git status -sb | head -1` | grep exit 0；分支无 `ahead` 变化（未 push） | T-A | 若 message 缺 `#T-5128` → grep exit 1 |

**潜在风险**

- 白名单**过窄**（Word 未来新增结构性 note 类型）→ 该 note 会被误删。当前三类型覆盖 OOXML 的 `separator` / `continuationSeparator` / `continuationNotice`；同步上游时需复核 `_STRUCTURAL_NOTE_TYPES`。缓解：`test_keeps_structural_note_without_settings_entry` 按类型参数化 + `test_footnote_endnote_crud.py` 回归。
- 有人改回上游 fail-open 判据（`type not in (None, "normal")`）→ 由 `test_strips_orphan_with_unknown_type` 拦截（未知 type 孤儿必须被删）。
- `_settings_note_ids` 每次 save 调 2 次（footnote/endnote），均为内存树遍历，无 I/O 增量。
- 若 fixture 的 `word/settings.xml` 未加载（`_tree` 返回 None），`_pin_in_settings` 会抛 `TypeError`。已实测该 part 存在且为**空** `<w:settings/>`（`tests/conftest.py::_SETTINGS_XML`），pin 由 helper 自建并回读断言；执行时若 `_tree` 返回 None → 改用 `doc._require("word/settings.xml")` 并记录偏差。
- M1 人工验收用的 `kept.docx` 由测试 helper 构造，`w:endnotePr` 追加在 `w:settings` 末尾，可能不符合 Word 的严格子元素顺序。若 Word 提示损坏，须先区分「helper 构造不合法」与「实现缺陷」，不得直接判实现失败。

**预留歧义标注（执行后回写）**
- [x] 无歧义：路径、锚点（符号名）、命令、期望退出码完备
- 歧义点：无（执行结果：commit `2b62f9b`，受控变异 RED `5 failed` → GREEN `148 passed`，见 §Execution Log T1）

---

## Phase 2 — Task T2：#5129 pdfexport stdin=DEVNULL + timeout

| 字段 | 值 |
|---|---|
| **task_id** | #5129 |
| **依赖** | 无（与前/后 task 文件不重叠） |
| **frontier** | 是 |
| **执行者** | Dev Orchestrator → 实现类 agent |
| **预估墙钟** | 15–20 min（RED 5 + 实现 5 + GREEN 4 + 提交 3） |
| **Commit message** | `fix(pdfexport): LibreOffice 子进程设 stdin=DEVNULL 与可配置 timeout，挂起转为明确失败 #T-5129` |

**modifications（严格限于此，共 2 个文件）**

| 文件 | 动作 |
|---|---|
| `docx_mcp/document/pdfexport.py` | 新增 `import os`；新增模块级 `DEFAULT_TIMEOUT = 90.0`、`TIMEOUT_ENV = "DOCX_MCP_PDF_TIMEOUT"`、`_resolve_timeout() -> float`；`subprocess.run(...)` 增加 `stdin=subprocess.DEVNULL` 与 `timeout=<resolved>`；包 `try/except subprocess.TimeoutExpired` → `RuntimeError`（消息含秒数） |
| `tests/test_pdf_export.py` | 在 `class TestConvertToPdf` 内新增 3 个用例（kwargs 断言 / 超时翻译 / 环境变量覆盖） |

**修改边界（不得触碰）**

- ⛔ `convert_to_pdf(self, output_path: str) -> dict` 签名与返回结构 `{"pdf_path": str}`
- ⛔ `LibreOffice not found` 的异常类型与消息关键字（既有用例 `match="LibreOffice"` 依赖）
- ⛔ `raise RuntimeError(f"LibreOffice conversion failed (exit ...)")` 的既有分支语义
- ⛔ 不新增对 LibreOffice 的硬依赖（不得在测试中真实调用 soffice）
- ⛔ `uv.lock` / `pyproject.toml` / `base.py` / `server.py`

### 执行步骤

**S1 基线重检**：`git status --porcelain` 应回到「已知脏基线」；确认 `pdfexport.py` 仍无 `stdin`/`timeout` 关键字（`grep -n 'DEVNULL\|timeout' docx_mcp/document/pdfexport.py` → 无输出）。

**S2 RED：先加测试**（在 `tests/test_pdf_export.py` 的 `class TestConvertToPdf` 末尾追加；文件头已导入 `subprocess`? —— 若未导入，**先**在文件头 `from pathlib import Path` 附近补 `import subprocess`，属于本文件范围内允许改动）：

```python
    def test_subprocess_gets_devnull_stdin_and_timeout(self, tmp_path: Path, monkeypatch):
        """The child must not inherit the MCP stdio pipe, and must be time-bounded."""
        from docx_mcp.document import pdfexport

        monkeypatch.delenv("DOCX_MCP_PDF_TIMEOUT", raising=False)  # test the shipped default
        doc = _make_doc(tmp_path)
        with (
            patch("shutil.which", return_value="/usr/bin/libreoffice"),
            patch("subprocess.run") as mock_run,
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.rename"),
        ):
            mock_run.return_value = MagicMock(returncode=0)
            doc.convert_to_pdf(str(tmp_path / "out.pdf"))

        kwargs = mock_run.call_args.kwargs
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert isinstance(kwargs["timeout"], (int, float))
        assert kwargs["timeout"] > 0
        # Must stay clearly below the deployment-side opencode mcp.timeout.execution
        # (120000 ms) hard cap; otherwise the client times out first and the hang never
        # surfaces as an explicit error -- i.e. the bug this task fixes.
        assert kwargs["timeout"] < 120.0
        assert pdfexport.DEFAULT_TIMEOUT < 120.0

    def test_timeout_becomes_explicit_runtime_error(self, tmp_path: Path, monkeypatch):
        """A hung conversion must surface as RuntimeError naming the timeout, not a bare timeout."""
        # Pin the shipped default: if the environment exports DOCX_MCP_PDF_TIMEOUT, the
        # resolved limit is no longer 90 and the message assertion below would be flaky.
        monkeypatch.delenv("DOCX_MCP_PDF_TIMEOUT", raising=False)
        doc = _make_doc(tmp_path)
        with (
            patch("shutil.which", return_value="/usr/bin/libreoffice"),
            patch("subprocess.run") as mock_run,
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="libreoffice", timeout=90.0)
            # The implementation reports the resolved limit (`{timeout:g}s`), so the
            # message must name 90; keep this in sync with DEFAULT_TIMEOUT.
            with pytest.raises(RuntimeError, match=r"timed out after 90"):
                doc.convert_to_pdf(str(tmp_path / "out.pdf"))

    def test_timeout_env_override(self, tmp_path: Path, monkeypatch):
        """DOCX_MCP_PDF_TIMEOUT overrides the default; invalid values fall back."""
        from docx_mcp.document import pdfexport

        monkeypatch.setenv("DOCX_MCP_PDF_TIMEOUT", "7.5")
        assert pdfexport._resolve_timeout() == 7.5
        monkeypatch.setenv("DOCX_MCP_PDF_TIMEOUT", "not-a-number")
        assert pdfexport._resolve_timeout() == pdfexport.DEFAULT_TIMEOUT
        monkeypatch.setenv("DOCX_MCP_PDF_TIMEOUT", "0")
        assert pdfexport._resolve_timeout() == pdfexport.DEFAULT_TIMEOUT
```

RED 取证：

```bash
cd /home/gw/opt/docx-mcp
.venv/bin/python -m pytest tests/test_pdf_export.py -q
```

期望：**3 failed / 5 passed**（新 3 个失败：`KeyError: 'stdin'`、`DID NOT RAISE`、`AttributeError/_resolve_timeout`）。若新用例通过 → 停止复查测试有效性。

**S3 实现（pdfexport.py）**
1) 文件头加 `import os`（置于 `import shutil` 之前，保持 ruff isort 顺序：`import os` → `import shutil` → `import subprocess`）。
2) `import` 之后、`class PdfExportMixin:` 之前加：

```python
DEFAULT_TIMEOUT = 90.0
"""Seconds to wait for a headless LibreOffice conversion before failing loudly.

Must stay clearly below the deployment-side opencode hard cap
(`mcp.timeout.execution` = 120000 ms = 120 s): a value at or above that cap means the
client gives up first and the hang never surfaces as an explicit RuntimeError. 90 s
still covers LibreOffice's first headless start (profile bootstrap) plus a large
document conversion, which are measured in tens of seconds. Override with
DOCX_MCP_PDF_TIMEOUT.
"""

TIMEOUT_ENV = "DOCX_MCP_PDF_TIMEOUT"


def _resolve_timeout() -> float:
    """Return the conversion timeout in seconds (env override, else DEFAULT_TIMEOUT)."""
    raw = os.environ.get(TIMEOUT_ENV)
    if not raw:
        return DEFAULT_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT
    return value if value > 0 else DEFAULT_TIMEOUT
```

3) 替换 `result = subprocess.run(...)` 调用：新增 `stdin=subprocess.DEVNULL`、`timeout=timeout`（局部变量 `timeout = _resolve_timeout()` 置于调用前），并用 try/except 包裹：

```python
        timeout = _resolve_timeout()
        try:
            result = subprocess.run(
                [...],  # 保持原有 argv 不变
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"LibreOffice conversion timed out after {timeout:g}s "
                f"(set {TIMEOUT_ENV} to change the limit)."
            ) from exc
```

**S4 GREEN**：`pytest tests/test_pdf_export.py -q` → 期望 **8 passed**（5 旧 + 3 新），exit 0。

**S5 回归 + 静态检查**

```bash
.venv/bin/python -m pytest tests/test_pdf_export.py tests/test_e2e.py -q
.venv/bin/python -m ruff check docx_mcp/document/pdfexport.py tests/test_pdf_export.py
.venv/bin/python -m ruff format --check docx_mcp/document/pdfexport.py tests/test_pdf_export.py
```

**S6 提交**

```bash
git add docx_mcp/document/pdfexport.py tests/test_pdf_export.py
git diff --cached --name-only     # 期望恰好 2 行
git commit -m "fix(pdfexport): LibreOffice 子进程设 stdin=DEVNULL 与可配置 timeout，挂起转为明确失败 #T-5129"
```

### 验收标准（原文 AC + 可执行命令）

| # | 原文 AC（PM #5129） | 可执行命令 | 期望 | 类型 | 能失败证明 |
|---|---|---|---|---|---|
| AC1 | `pytest tests/test_pdf_export.py -q` → exit 0 | `.venv/bin/python -m pytest tests/test_pdf_export.py -q` | exit 0，8 passed | T-A | 实现回退法：删去 `stdin=` 与 `timeout=` → 2 用例失败 |
| AC2 | 用例断言调用参数含 `stdin=subprocess.DEVNULL` 且 `timeout` 为正数（monkeypatch 捕获 kwargs） | `-k test_subprocess_gets_devnull_stdin_and_timeout` | exit 0（额外断言 `timeout < 120.0` 与 `DEFAULT_TIMEOUT < 120.0`，锁定部署侧 120 s 硬顶约束） | T-B | 把 `stdin=subprocess.DEVNULL` 改为 `stdin=None` → `KeyError`/断言失败；把 `DEFAULT_TIMEOUT` 改回 120.0 → `< 120.0` 断言失败 |
| AC3 | 模拟 `subprocess.TimeoutExpired` → 转为含 timeout 秒数的明确 `RuntimeError`，不得静默返回或吞异常 | `-k test_timeout_becomes_explicit_runtime_error` | exit 0 | T-B | 删掉 `except subprocess.TimeoutExpired` → 原异常类型泄漏，`pytest.raises(RuntimeError)` 失败 |
| AC4 | 无 LibreOffice 环境下原 skip / `RuntimeError("LibreOffice not found")` 行为不被破坏 | `-k test_raises_if_libreoffice_not_found` | exit 0（1 passed） | T-A | 变异法：把 `if lo is None: raise` 改为 `return {}` → 该用例失败 |
| AC5 | 公开签名不变：`convert_to_pdf(output_path: str) -> dict`，返回 `{"pdf_path": str}` | `.venv/bin/python -c "import inspect; from docx_mcp.document.pdfexport import PdfExportMixin as P; print(inspect.signature(P.convert_to_pdf))"` 且 `-k test_returns_pdf_path_key` | 参数名与顺序为 `self, output_path`（因 `from __future__ import annotations`，注解以字符串呈现，`'str'`/`'dict'` 带引号属正常）；test exit 0 | T-A/T-C | 改签名为 `(*, output_path)` 或改返回键 → 对应检查失败 |
| AC6 | `git diff --stat` 仅含声明文件；独立 commit 含 `#T-<task_id>`；不 push | `git show --stat --oneline HEAD`；`git log -1 --format=%s | grep -F "#T-5129"` | 仅 2 文件；grep exit 0 | T-C | 夹带 `uv.lock` 或 message 缺 tag → 失败 |

**潜在风险**

- `patch("subprocess.run")` 的 `side_effect` 抛出 `TimeoutExpired` 时，`cmd` 属性可能是列表；异常消息不依赖 `exc.cmd`，只依赖局部 `timeout` → 不受影响。
- 既有用例 `test_raises_if_subprocess_fails` 用 `MagicMock(returncode=1, stderr=...)`，新增 kwargs 不影响。
- 若执行环境 `DOCX_MCP_PDF_TIMEOUT` 已导出（污染），`test_timeout_env_override` 使用 `monkeypatch.setenv` 覆盖；`test_subprocess_gets_...` 与 `test_timeout_becomes_explicit_runtime_error` 均先 `monkeypatch.delenv`（后者若缺这一步，`match=r"timed out after 90"` 在污染环境下会假失败——R5 已补）；前者另断言默认值 `< 120.0`（该断言同时锁定「DEFAULT_TIMEOUT 必须显著小于部署侧 120 s 硬顶」这一设计约束）。
- 若部署侧日后下调 `mcp.timeout.execution`，`DEFAULT_TIMEOUT` 需同步下调；测试中的 `< 120.0` 只是当前部署口径的守护，不是通用常量。
- 覆盖率：新增 `_resolve_timeout` 三个分支均由 `test_timeout_env_override` 覆盖（未设置/非法/<=0），另有正常路径由其他用例覆盖。

**预留歧义标注（执行后回写）**
- [x] 无歧义
- 歧义点：无（执行结果：commit `d1d0490`，受控变异 RED `3 failed` → GREEN `8 passed`，真实 soffice 冒烟 0.70 s，见 §Execution Log T2）

---

## Phase 3 — Task T3：#2615 mcp 依赖 pin（`>=1.28,<2`）

| 字段 | 值 |
|---|---|
| **task_id** | #2615 |
| **依赖** | 无（文件与 T1/T2 不重叠；仅 commit 串行） |
| **frontier** | 是（含人工审计步骤，故排最后执行） |
| **执行者** | Dev Orchestrator（锁文件索引操作需严格按本 task 命令执行，禁止自创 `git add -A`） |
| **预估墙钟** | 27–30 min（S0-S2 探针 8 · S3-S4 重建+验证 12 · S5-S7 暂存+审计+提交 10）；checkpoint：10 min（S2 解锁完成）· 24 min（S4 三关通过，含 `uv lock --check` exit 0）· 28 min（S6 审计通过） |
| **Commit message** | `fix(deps): pin mcp>=1.28,<2 防止 MCP SDK 2.x 破坏 fresh install #T-2615` |

**modifications（严格限于此，共 2 个文件）**

| 文件 | 动作 |
|---|---|
| `pyproject.toml` | `[project].dependencies` 中 `"mcp>=1.0.0"` → `"mcp>=1.28,<2"`（仅此一行） |
| `uv.lock` | 提交内容 = **S2 `uv lock` 产物回退三项 churn**（删 `revision = 3`、删全部 `upload-time`、删根项目块 `provides-extras`）；**根项目 `version` 保持 `0.7.4`（不回退，随本题提交；R5 修正）**；**保留全部语义派生**：mcp 包块（version/sdist/wheels）、顶层 `resolution-markers`（3 → 6 支）、`exceptiongroup` / `numpy` / `pydantic-core` 版本行、根 `requires-dist` 的 mcp specifier |

**修改边界（不得触碰）**

- ⛔ 不得 `git checkout -- uv.lock` / `git reset -- uv.lock` / `git restore uv.lock` / 从 HEAD 覆盖**工作树** lock（S6 中止路径的 `git reset -q -- uv.lock` 只清**索引**，是允许且指定的）
- ⛔ 不得提交工作树的**三项 churn**：`revision = 3`、`upload-time`、根项目块 `provides-extras`
- ⛔ **不得回退根项目 `version`**：提交态 lock 的根包必须为 `version = "0.7.4"`（与 `pyproject.toml:7` 一致）；回退为 `0.7.3` 会使 `uv lock --check` exit 1（R5 实测），是 NEW-B1 的直接成因
- ⛔ **不得剥离** pin 派生的语义变更（顶层 `resolution-markers` 6 支、`exceptiongroup` / `numpy` / `pydantic-core` 版本行）——它们随本题提交；剥离后 lock 与解析结果不一致
- ⛔ **禁止 `git commit -a` / `git commit -am`**（会把工作树 churn 直接卷入提交，绕过 S5 的 `update-index`）；只允许裸 `git commit -m`
- ⛔ 不得改动 `[dependency-groups].dev`、`requires-python`、其他依赖版本；`pyproject.toml` 的 `version = "0.7.4"`（第 7 行）**保持不变**（HEAD 已是 0.7.4，改动它属计划外）
- ⛔ **禁止整支 cherry-pick PR #16**（该分支污染，见 §风险 R-1）；本次只实现 pin 语义
- ⛔ 不得推送到远端；不得新增测试文件（依赖约束不引入可测行为，靠 AC1–AC5 命令验证）

### 执行步骤

**S0 备份与基线取证**

```bash
cd /home/gw/opt/docx-mcp
mkdir -p /tmp/t2615
git rev-parse HEAD
git rev-parse HEAD^{tree} | tee /tmp/t2615/tree-before.txt   # 索引/工作树一致性基线（S6 对照用）
git status --porcelain=v1 | tee /tmp/t2615/status-before.txt
sha256sum uv.lock | tee /tmp/t2615/worktree-lock-before.sha256
git show HEAD:uv.lock > /tmp/t2615/head-uv.lock
grep -n '"mcp>=' pyproject.toml            # 期望：22:    "mcp>=1.0.0",
grep -n 'name = "mcp", specifier = ">=' /tmp/t2615/head-uv.lock   # 期望 1 行：{ name = "mcp", specifier = ">=1.0.0" },
grep -n 'version = "0.7.4"' pyproject.toml  # 期望：7:version = "0.7.4"（锁内根包版本必须与之一致）
grep -n -A1 '^name = "docx-mcp-server"' /tmp/t2615/head-uv.lock   # 期望 version = "0.7.3"（基线 stale 证据）
```

**S1 编辑 `pyproject.toml`（唯一的工作树源码改动）**

```bash
sed -i 's/"mcp>=1.0.0"/"mcp>=1.28,<2"/' pyproject.toml
grep -n '"mcp>=' pyproject.toml   # 期望唯一命中：    "mcp>=1.28,<2",
```

**S2 在工作树 lock 上跑最小化解锁（保留既有 churn，只追加 mcp 变更）**

```bash
cp pyproject.toml /tmp/t2615/pyproject.pinned.toml
cp uv.lock /tmp/t2615/worktree-lock-before.lock
cp /tmp/t2615/worktree-lock-before.lock /tmp/t2615/gen-before.lock
uv lock                     # 期望 stderr 行：Updated mcp v1.26.0 -> v<X>，X 满足 1.28 <= X < 2
cp uv.lock /tmp/t2615/gen-after.lock   # S3 的重建基底（唯一权威来源）
```

- 记录实际解析出的 `<X>`（规划时探针为 `1.30.0`，**执行时以实际为准**）。
- 记录 diff 规模（仅作观测，**不构成门禁**）：`diff -u /tmp/t2615/worktree-lock-before.lock uv.lock | grep -c '^@@'`。语义分类统一由 S4-(1) 的**允许集分类器**判定，禁止用 hunk 数当质量证据。
- 此步只修改工作树 lock（追加语义），不还原、不覆盖既有 churn。

**S3 重建提交版本（以 S2 产物为基底，回退三项 churn、根 version 保持 0.7.4；不触碰工作树）**

```bash
mkdir -p /tmp/t2615/min
cp /tmp/t2615/gen-after.lock /tmp/t2615/min/uv.lock
cp /tmp/t2615/pyproject.pinned.toml /tmp/t2615/min/pyproject.toml
grep -n '^version' /tmp/t2615/min/pyproject.toml   # 前置断言：期望 7:version = "0.7.4"
python3 - <<'PY'
import pathlib, re

p = pathlib.Path('/tmp/t2615/min/uv.lock')
s = p.read_text()

# churn 1: `revision = 3` —— HEAD lock 无该行
s, n_rev = re.subn(r'(?m)^revision = \d+\n', '', s)
assert n_rev == 1, f'expected exactly one revision line, got {n_rev}'

# churn 2: 全量 upload-time —— HEAD lock 无该字段
s, n_ut = re.subn(r', upload-time = "[^"]*"', '', s)
assert n_ut > 0, 'no upload-time removed: gen-after 不像 uv lock 产物'
assert 'upload-time' not in s

# churn 3: 根项目块新增的 provides-extras（HEAD lock 无；uv 0.12 元数据）
s, n_pe = re.subn(r'(?m)^provides-extras = \[[^\]]*\]\n', '', s)
assert n_pe == 1, f'expected exactly one provides-extras line, got {n_pe}'

# 根项目 version 必须保持 0.7.4（R5 修正：pyproject.toml:7 已为 0.7.4；
# HEAD 锁内 0.7.3 属基线 stale。回退到 0.7.3 会让 uv lock --check 必然 exit 1）
assert s.count('name = "docx-mcp-server"\nversion = "0.7.4"') == 1, 'root version drifted from 0.7.4'
assert s.count('version = "0.7.3"') == 0, 'stale root version 0.7.3 leaked into reconstructed lock'

# 语义派生必须仍在（防止把 pin 语义一起削掉）
assert '{ name = "mcp", specifier = ">=1.28,<2" }' in s
assert ', }' not in s and ',,' not in s, 'field removal left residue'

mcp_blk = re.search(r'(?ms)^\[\[package\]\]\nname = "mcp"\n.*?(?=^\[\[package\]\])', s).group(0)
ver = re.search(r'(?m)^version = "([^"]+)"', mcp_blk).group(1)
maj, minor = (int(x) for x in ver.split('.')[:2])
assert (maj, minor) >= (1, 28) and maj < 2, ver

p.write_text(s)
print('removed upload-time fields:', n_ut, '| removed provides-extras:', n_pe,
      '| root version kept: 0.7.4 | mcp version in reconstructed lock:', ver)
PY
```

**S4 校验重建结果（三道关，任一失败 → 走 S8-D2；除非该关自带的「判别路径」给出可修因）**

```bash
cd /home/gw/opt/docx-mcp
# (1-a) churn 归零 + 根 version 归位（快速检查）
grep -c 'upload-time' /tmp/t2615/min/uv.lock            # 期望 0
grep -c '^revision = ' /tmp/t2615/min/uv.lock           # 期望 0
grep -c 'provides-extras' /tmp/t2615/min/uv.lock        # 期望 0（HEAD lock 无该字段）
grep -c 'version = "0.7.4"' /tmp/t2615/min/uv.lock      # 期望 1（根包；R5 修正：不再回退）
grep -c 'version = "0.7.3"' /tmp/t2615/min/uv.lock      # 期望 0（stale 版本不得残留）

# (1-b) 允许集分类器：只有「mcp 包块 / 顶层 resolution-markers / exceptiongroup|numpy|pydantic-core 版本行 /
#       根项目 requires-dist 的 mcp specifier / 根项目 version 0.7.3→0.7.4」允许变化，其余一律禁止（不写死行数）
python3 - <<'PY'
import pathlib, re, sys

def load(path):
    text = pathlib.Path(path).read_text()
    parts = re.split(r'(?m)^(?=\[\[package\]\])', text)
    blocks = {}
    for part in parts[1:]:
        blocks[re.search(r'(?m)^name = "([^"]+)"', part).group(1)] = part
    return parts[0], blocks

def root_version(block):
    return re.search(r'(?m)^version = "([^"]+)"', block).group(1)

def norm_root(block):
    # 归一化 root 块内允许变化的三处：mcp specifier / 根 version / provides-extras
    b = block.replace('{ name = "mcp", specifier = ">=1.0.0" }', '<<MCP>>')
    b = b.replace('{ name = "mcp", specifier = ">=1.28,<2" }', '<<MCP>>')
    b = re.sub(r'(?m)^version = "0\.7\.[34]"\n', '<<ROOTVER>>\n', b, count=1)
    b = re.sub(r'(?m)^provides-extras = \[[^\]]*\]\n', '', b)
    return b

h_head, b_head = load('/tmp/t2615/head-uv.lock')
h_new, b_new = load('/tmp/t2615/min/uv.lock')
bad = []

# A. 包名集合完全一致
if set(b_head) != set(b_new):
    bad.append(f'package set changed: +{sorted(set(b_new) - set(b_head))} '
               f'-{sorted(set(b_head) - set(b_new))}')

# B. 顶层头：除 resolution-markers 数组外必须逐字节一致
strip = lambda h: re.sub(r'(?ms)^resolution-markers = \[\n.*?^\]\n', '', h)
if strip(h_head) != strip(h_new):
    bad.append('top-level header changed outside resolution-markers')

# C. 包块：允许变化的包名白名单
ALLOWED = {'mcp', 'exceptiongroup', 'numpy', 'pydantic-core'}
for name in sorted(set(b_head) & set(b_new)):
    old, new = b_head[name], b_new[name]
    if old == new:
        continue
    if name == 'docx-mcp-server':
        # 根项目：提交态 version 必须为 0.7.4（R5），HEAD 侧允许 0.7.3/0.7.4
        if root_version(new) != '0.7.4':
            bad.append(f'root project version must stay 0.7.4, got {root_version(new)}')
        if root_version(old) not in {'0.7.3', '0.7.4'}:
            bad.append(f'unexpected HEAD root version {root_version(old)}')
        if norm_root(old) != norm_root(new):
            bad.append('root project block changed beyond mcp specifier / root version')
    elif name not in ALLOWED:
        bad.append(f'changed package not in allow-list: {name}')

print('\n'.join(bad) if bad else 'ALLOW-LIST OK')
sys.exit(1 if bad else 0)
PY

# (2) 门禁：lock 必须是 uv 认可的最新状态（R5 修正：本重建形态实测 exit 0）
cd /tmp/t2615/min && uv lock --check; echo "uv-lock-check exit=$?"
#     期望 exit 0（pin 后 pyproject + 重建 lock：根 version 0.7.4、仅回退三项格式 churn）
#     非 0 → 先跑 (2b) 判别归因，再据此决定「修环境/修重建」或 S8-D2；不得直接判「churn 回退导致不可验证」
# (2b) 判别探针（仅在 (2) 非 0 时执行，用于归因，不单独构成门禁）
#      P-a：gen-after 原样（未回退任何 churn）→ 若通过，说明闸门本身可用，(2) 的失败出在重建环节
mkdir -p /tmp/t2615/probe
cp /tmp/t2615/gen-after.lock /tmp/t2615/probe/uv.lock
cp /tmp/t2615/pyproject.pinned.toml /tmp/t2615/probe/pyproject.toml
(cd /tmp/t2615/probe && uv lock --check); echo "probe-a exit=$?"
#      P-b：把根 version 单独改回 0.7.3 的对照 → 预期 exit 1（证明「根 version 回退」是失败原因）
mkdir -p /tmp/t2615/probe-b
cp /tmp/t2615/gen-after.lock /tmp/t2615/probe-b/uv.lock
cp /tmp/t2615/pyproject.pinned.toml /tmp/t2615/probe-b/pyproject.toml
python3 - <<'PY'
import pathlib
p = pathlib.Path('/tmp/t2615/probe-b/uv.lock'); s = p.read_text()
old = 'name = "docx-mcp-server"\nversion = "0.7.4"'
new = 'name = "docx-mcp-server"\nversion = "0.7.3"'
assert s.count(old) == 1, s.count(old)
p.write_text(s.replace(old, new))
PY
(cd /tmp/t2615/probe-b && uv lock --check); echo "probe-b exit=$?"
#     归因表：(2)=0 → 通过（不必看 2b）
#             (2)≠0 且 probe-a=0 → 重建环节出错（回退正则/残留），按 S3 逐项复核后重跑，不得 D2
#             (2)≠0 且 probe-a≠0 → 副本环境问题（缺 pyproject/网络/cache/uv 版本漂移），修环境后重跑
#             (2)≠0 且 probe-b=0 → 说明根 version 判断与本计划结论冲突（uv 版本行为差异）→ 记录证据后 D2
# (2c) 参考（非门禁）：frozen 同步可解析出 mcp==<X>
(cd /tmp/t2615/min && uv sync --frozen --dry-run 2>&1 | grep -E "mcp==|error")

# (3) 哈希与 PyPI 实际产物一致（防手抄错误）
python3 - <<'PY' > /tmp/t2615/urls.txt
import re, pathlib
s = pathlib.Path('/tmp/t2615/min/uv.lock').read_text()
blk = re.search(r'(?ms)^\[\[package\]\]\nname = "mcp"\n.*?(?=^\[\[package\]\]\n)', s).group(0)
for url, h in re.findall(r'url = "([^"]+)".*?hash = "sha256:([0-9a-f]+)"', blk):
    print(url, h)
PY
while read -r url hash; do
  actual=$(curl -sL "$url" | sha256sum | cut -d' ' -f1)
  [ "$actual" = "$hash" ] && echo "OK  $url" || { echo "MISMATCH $url"; exit 1; }
done < /tmp/t2615/urls.txt                                            # 期望全部 OK，exit 0
```

> **S4-(1-b) 分类器输入约定（消除复用歧义）**：脚本内 `load('/tmp/t2615/head-uv.lock')`（a = 基准侧）与 `load('/tmp/t2615/min/uv.lock')`（b = 被检侧）是**唯一**允许替换的两处：
> - S6 复用 → a 保持 `head-uv.lock`，b 换成 `/tmp/t2615/staged.lock`；
> - V7b 复用 → 先 `git show HEAD~1:uv.lock > /tmp/t2615/head1-uv.lock`、`git show HEAD:uv.lock > /tmp/t2615/head0-uv.lock`，再以 a=`head1-uv.lock`、b=`head0-uv.lock` 运行。
> **禁止**改动判定逻辑（`ALLOWED` 集合、root version 硬判、header 的 `resolution-markers` strip）。

**S5 将重建版暂存为 commit 内容（工作树文件零改动）**

```bash
cd /home/gw/opt/docx-mcp
git add pyproject.toml                                        # 唯一需要的普通 add
blob=$(git hash-object -w /tmp/t2615/min/uv.lock)
git update-index --cacheinfo 100644,"$blob",uv.lock
# 若上面一行报用法错误（旧 git），改用：git update-index --add --cacheinfo 100644 "$blob" uv.lock
```

- ⛔ **禁止 `git commit -a` / `git commit -am`**：工作树 `uv.lock` 与索引 `uv.lock` 在本 task 中**刻意不一致**（索引=重建版，工作树=含 churn 的旧脏基线），`-a` 会把工作树版本直接卷入提交。
- ⛔ 禁止 `git add -A` / `git add .` / `git add uv.lock`（后者会把工作树版本放进索引，绕开重建）。
- 预期状态：`git status --porcelain` 中 `uv.lock` 同时出现在 staged（`M `）与 unstaged（` M`）两侧——这是本 task 的正常形态，由 S6/S7 断言守护。

**S6 提交前审计（全部断言 + 允许集分类器，逐条必须通过；行数/固定加删数不再作为判据）**

```bash
git show :uv.lock > /tmp/t2615/staged.lock          # 导出索引中的 lock（= 将要提交的内容）
git diff --cached --name-only                       # 期望恰好 2 行：pyproject.toml / uv.lock
git diff-tree --no-commit-id --name-only -r \
  "$(cat /tmp/t2615/tree-before.txt)" "$(git write-tree)"   # 期望恰好 2 行：同上（索引树 vs HEAD 树）
git diff --cached -U0 -- pyproject.toml             # 期望仅 "mcp>=1.0.0" → "mcp>=1.28,<2" 一行变化
grep -c 'upload-time' /tmp/t2615/staged.lock        # 期望 0
grep -c '^revision = ' /tmp/t2615/staged.lock       # 期望 0
grep -c 'provides-extras' /tmp/t2615/staged.lock    # 期望 0
grep -c 'version = "0.7.4"' /tmp/t2615/staged.lock  # 期望 1（根包；R5 修正：不回退）
grep -c 'version = "0.7.3"' /tmp/t2615/staged.lock  # 期望 0
grep -c 'specifier = ">=1.28,<2"' /tmp/t2615/staged.lock   # 期望 1（uv 实际写法：{ name = "mcp", specifier = ">=1.28,<2" }）
```

**允许集分类器（对暂存内容重跑一次 S4-(1-b)）**：把 S4-(1-b) 的脚本第二输入由 `/tmp/t2615/min/uv.lock` 换成 `/tmp/t2615/staged.lock`（第一输入保持 `/tmp/t2615/head-uv.lock`）执行；输出必须为 `ALLOW-LIST OK`、exit 0。参见 S4-(1-b) 后的「分类器输入约定」。

> 审计期望的**语义口径**（取代旧的固定行数断言）：暂存 lock 相对 `HEAD:uv.lock` 的差异**仅允许**——
> ① `mcp` 包块（version / sdist / wheels / dependencies）；
> ② 顶层 `resolution-markers` 数组；
> ③ `exceptiongroup` / `numpy` / `pydantic-core` 三个包的版本行及其派生（sdist/wheels/依赖行）；
> ④ 根项目 `requires-dist` 中 mcp 的 specifier 行；
> ⑤ 根项目 `version` 由 `0.7.3` → `0.7.4`（基线 stale 修正，必须为 0.7.4）。
> **其他一律禁止**（含新增/删除包、其他包版本变化、`revision =`、`upload-time`、根块 `provides-extras`、根 version 落回 0.7.3）。
> 禁止写成「期望 N 个 hunk / 4 加 4 删」这类耦合解析结果的常量。

任一条不符 → **停止，不得 commit**，执行 `git reset -q -- uv.lock`（仅清索引，不动工作树）后回到 S3 排查。

**S7 提交 + 提交后验证**

```bash
git commit -m "fix(deps): pin mcp>=1.28,<2 防止 MCP SDK 2.x 破坏 fresh install #T-2615"
git diff-tree --no-commit-id --name-only -r HEAD                # 期望恰好 2 行（pyproject.toml / uv.lock）
git show --stat --oneline HEAD                                  # 期望仅 2 文件
git show HEAD:uv.lock | grep -n 'specifier = ">=1.28,<2"'      # 期望 1 行
git show HEAD:uv.lock | grep -c 'upload-time'                   # 期望 0
git show HEAD:uv.lock | grep -c '^revision = '                  # 期望 0
git show HEAD:uv.lock | grep -c 'version = "0.7.4"'             # 期望 1（根包；与 pyproject 一致）
git show HEAD:uv.lock | grep -c 'version = "0.7.3"'             # 期望 0
git show HEAD:uv.lock | grep -c 'provides-extras'               # 期望 0
git status --porcelain -- uv.lock                               # 期望 " M uv.lock"（既有 churn 仍在工作树）
git diff -- uv.lock | grep -c 'upload-time'                     # 期望 >0（证明未 checkout/未覆盖）
uv sync                                                         # 安装 lock 中的 mcp==<X> 到 .venv
.venv/bin/python -c "import docx_mcp.server"                    # mcp 运行时面可导入（exit 0）
.venv/bin/python -m pytest tests/test_e2e.py tests/test_pdf_export.py -q   # 期望 0 failed
```

> S7 的 `uv sync` / `import docx_mcp.server` / 双文件 pytest 是 **AC5 的扩展**（覆盖 mcp 运行时面）；任一失败 → 走 S8-D2，不得只报「pin 已改」。

**S8-D2（失败升级，不得自行放宽约束）**
触发条件（任一，且 2 次修正仍不通过）：S4-(1) 分类器报出允许集之外的差异；S4-(2) `uv lock --check` 非 0（且 (2b) 归因显示非环境/非重建可修因）；S4-(3) PyPI sha256 不符；S7 的 `import docx_mcp.server` / 双文件 pytest 失败。返回 `NEEDS_USER_DECISION`，选项：
- (A) 授权提交完整 `uv lock` 结果（含三项 churn：`revision = 3` + `upload-time` + 根块 `provides-extras`；根 version 0.7.4 本来就该提交）：优点=零重建步骤、`uv lock --check` 可验证；缺点=违反「不得提交无关 hunks」。**须附 S4-(2b) 的判别探针输出作为证据**（probe-a/probe-b 的 exit code），否则不得提议本项；(A) 的 diff 规模**执行时实测**，禁止沿用本计划中的估算数字。
- (B) 暂缓 #2615，先把 T1/T2 交付：可逆；缺点=pin 目标未达成。
- (C) 改由维护者在上游合入 PR #16/#17 后统一处理。
- (D) 保持本计划的 churn 最小重建（三项 churn 不提交、根 version 0.7.4 提交），但**接受 `uv lock --check` 不可用**，以 S4-(1) 允许集分类器 + S4-(3) PyPI sha256 + S7 运行时冒烟作为替代证据链。优点=满足「不得提交无关 hunks」；缺点=lock 不可被 uv 机械验证，需人工复核。**注意**：R5 已在规划机实测本形态 exit 0，故 (D) 只作为「执行机 uv 版本漂移」时的降级路径。
**禁止**自书授权或默认选 (A)。

### 验收标准（原文 AC + 可执行命令）

| # | 原文 AC（PM #2615） | 可执行命令（`cd /home/gw/opt/docx-mcp`） | 期望 | 类型 | 能失败证明 |
|---|---|---|---|---|---|
| AC1 | `grep -n '"mcp>=' pyproject.toml` → 输出 `mcp>=1.28,<2`，exit 0 | `grep -n '"mcp>=1.28,<2"' pyproject.toml` | exit 0，1 行命中 | T-A | 未改 pyproject 时 grep exit 1 |
| AC2 | `grep -n 'specifier = "mcp>=' uv.lock` → 输出 `specifier = "mcp>=1.28,<2"`，exit 0（**原文 AC 写法**；锁文件真实格式为 `{ name = "mcp", specifier = ">=1.28,<2" }`，故命令与期望按右列修正） | `git show HEAD:uv.lock \| grep -n 'specifier = ">=1.28,<2"'`（提交态）与 `grep -n 'name = "mcp", specifier = ">=' uv.lock`（工作树态） | 提交态 1 行命中 `>=1.28,<2`；工作树态 1 行命中 `>=1.28,<2`（**不含** `mcp>=` 前缀，R5 修正） | T-A | HEAD 未含 pin 时提交态 grep exit 1 |
| AC3 | `.venv/bin/python -c "import importlib.metadata as m; ...assert v.startswith('1.28') or (v>='1.28' and v<'2')"` → exit 0 | **原命令（保留）** + **硬化版**：`.venv/bin/python -c "import importlib.metadata as m; v=m.version('mcp'); parts=tuple(int(x) for x in v.split('.')[:2]); assert (1,28)<=parts<(2,0), v; print(v)"` | exit 0；打印 `<X>` ∈ [1.28, 2) | T-A | 未 `uv sync` 时 `mcp==1.26.0` → 硬化版 AssertionError |
| AC4 | `.venv/bin/python -c "import mcp; print(mcp.__file__)"` → exit 0（导入不破） | 同左 | exit 0，打印 `.venv/.../mcp/__init__.py` | T-A | 若 pin 到 2.x 破坏 API → import 失败 |
| AC5 | `pytest tests/test_pdf_export.py -q` → exit 0（最小冒烟） | ① `.venv/bin/python -c "import docx_mcp.server"`；② `.venv/bin/python -m pytest tests/test_e2e.py tests/test_pdf_export.py -q`；③ `.venv/bin/python -m pytest tests/test_pdf_export.py -q` | 三条均 exit 0、0 failed（② 的 passed 数按当时 T1/T2 是否已落地计，只看 `0 failed`） | T-A | 若 `uv sync` 未执行（.venv 仍 mcp==1.26.0）或 mcp 1.30 改变 API → ①② 出现 import/collection error；任一失败即 S8-D2 |
| AC6 | `git diff --stat` 仅含 `pyproject.toml` 与 `uv.lock`；独立 commit 含 `#T-2615`；不 push | `git diff-tree --no-commit-id --name-only -r HEAD`；`git log -1 --format=%s | grep -F "#T-2615"`；`git status -sb | head -1` | 恰 2 文件；grep exit 0；无 push 痕迹 | T-C | 夹带第三文件 / 提交工作树 churn / message 缺 tag → 失败 |
| AC* | （补充，来自 task notes「不得提交无关 hunks」） | 对暂存内容重跑 S4-(1-b) 允许集分类器（输入换 `/tmp/t2615/staged.lock`）；`grep -c '^revision = '`、`grep -c 'upload-time'`、`grep -c 'provides-extras'`、`grep -c 'version = "0.7.3"'`、`grep -c 'version = "0.7.4"'`；并在 `/tmp/t2615/min` 跑 `uv lock --check` | 分类器 `ALLOW-LIST OK` exit 0；三项 churn 计数均 0；`0.7.3`=0 且 `0.7.4`=1；`uv lock --check` exit 0 | T-C/T-A | 一旦提交完整 `uv lock` 结果 → `revision =` 行出现且分类器报出 markers 之外差异 → 双重暴露；若把根 version 回退为 0.7.3 → `0.7.3` 计数非 0 且 `uv lock --check` exit 1（**不写死行数/包数**） |
| AC* | （补充，非破坏性证据） | `sha256sum uv.lock` 对比 S0 记录 + `git status --porcelain -- uv.lock` | 仍为 ` M uv.lock`（churn 保留，工作树仅追加 mcp 语义） | T-C | 若执行了 `git checkout -- uv.lock` → `git diff -- uv.lock` 变空、`upload-time` 计数归零 → 暴露 |

**潜在风险**

- **R-1 PR #16 分支污染（最高）**：该 PR 的 diff 除 `pyproject.toml`/`uv.lock` 外还改动 `docx_mcp/document/formatting.py`、`docx_mcp/document/tracks.py`、`docx_mcp/server.py` 等无关文件。→ **禁止** `git cherry-pick` / `git am` / 整支 merge；只按本 plan 的 pin 语义实现。
- **R-2 手抄/回退 lock 出错**：由 S4-(3) PyPI sha256 回验 + S4-(1-b) 允许集分类器 + S4-(2) `uv lock --check`（R5 实测本形态 exit 0）三关拦截。**`uv sync --frozen --dry-run` 已被证伪为无效门禁**（对 stale lock 也 exit 0），仅作参考 (2c)，不得作为通过依据。
- **R-2b 基线 stale 被误判为 churn（R5 新增）**：`HEAD:uv.lock` 根包为 `0.7.3` 而 `HEAD:pyproject.toml:7` 为 `0.7.4` → **HEAD 自身 `uv lock --check` 即 exit 1**。处置：把根 version 0.7.4 视为**必须修正项**（不是 churn），S3 脚本与 S6/S7/V7 计数均按 `0.7.4 == 1`、`0.7.3 == 0` 断言；若执行者按旧口径回退为 0.7.3，`uv lock --check` 必然 exit 1 且分类器报 `root project version must stay 0.7.4`。
- **R-3 索引技巧误伤**：`git update-index --cacheinfo` 只改索引不改工作树；若 shell 变量为空会报错（安全）。提交前 S6 全部断言（含 `git write-tree` vs `HEAD^{tree}` 的 `diff-tree` 对照）+ S7 的 `git diff-tree ... -r HEAD` 恰 2 文件 + 提交后 `git diff -- uv.lock | grep -c upload-time > 0` 三重证明「索引正确且工作树未被覆盖」。
- **R-3b 提交态根 version 与 pyproject 脱钩**：S6/S7/V7 都以 `0.7.4 == 1` 与 `0.7.3 == 0` 双侧断言；分类器另设硬判 `root project version must stay 0.7.4`。任一侧不符即停止提交。
- **R-4 uv 解析版本漂移**：执行时 `<X>` 可能不是 1.30.0；所有断言按 `1.28 <= <X> < 2` 表达，禁止硬编码 1.30.0。
- **R-5 `uv sync` 副作用**：会同步 dev 组与项目本身到 `.venv`（非跟踪目录）；不影响提交内容。若 `uv sync` 因网络失败 → 记录并重试一次；仍失败则 `SKIP`（AC3 无法满足，任务标 blocked，不得伪造版本号）。
- **R-6 与 #2625（MCP SDK v2 迁移）方向冲突**：`<2` 上界与 v2 迁移互斥；本 task 只落地 pin，冲突由 #2625 后续处理（已在 task notes 声明）。

**预留歧义标注（执行后回写）**
- [x] 无歧义
- 执行结论：S4-(2) `uv lock --check` **首次即 exit 0**（`/tmp/t2615/min`），未触发 (2b) probe-a/probe-b 归因分支；未出现 D2 选项 (A)/(D) 的裁决需求。
- 已知判断点 ①：S4-(2) `uv lock --check` 非 0 时**先跑 (2b) 的 probe-a / probe-b 归因**再决定「修环境/修重建」或 D2，不得直接判失败，也不得声称「churn 回退导致不可验证」（R5 已实测本形态 exit 0）。
- 已知判断点 ②：D2 选项 (A)/(D) 是互斥路径，须由用户裁决；执行者不得自选。

---

## Execution Wave（并行与串行）

> 三个 task 的**文件集合互不重叠**（T1: base.py + test_e2e.py；T2: pdfexport.py + test_pdf_export.py；T3: pyproject.toml + uv.lock），实现阶段可并行；但**共享同一 git 索引与工作树**，commit 必须串行，且 T3 的 `git update-index` 与 T1/T2 的 `git add` 不可交错。

| Wave | 可并行 Task | Frontier（无人挡即刻开工） | 依赖已完成 |
|---|---|---|---|
| W0 | T1、T2 | T1、T2 | — |
| W1（提交 T1） | T1 commit | T1 | W0 中 T1 实现完成 |
| W1（提交 T2） | T2 commit | T2 | W0 中 T2 实现完成 |
| W2 | T3 | T3（其文件未被 T1/T2 触碰） | T1、T2 commit 完成（避免索引交错） |

**串行建议顺序**：T1 → T2 → T3（风险递增：源文件修复 → 源文件修复 → 锁文件索引操作）。

### 失败处置（每个 task 独立，均可 fix-forward 或整体回滚）

| Task | 优先策略 | 回滚方式（仅在 fix-forward 2 次失败后） | 回滚副作用 |
|---|---|---|---|
| T1 | fix-forward：先确认 RED 是否真触发；再收窄/放宽结构性判据 | `git revert --no-edit <T1-sha>`（本地，不 push） | 无（新增测试一并回退，回归到 4 passed） |
| T2 | fix-forward：先看 kwargs 断言失败点（stdin/timeout 是否真的传入） | `git revert --no-edit <T2-sha>` | 无（回到 5 passed） |
| T3 | fix-forward：仅重跑 S3 重建（工作树 lock 不动）；S4 三关不通时先跑 (2b) 归因（probe-a/probe-b）：probe-a=0 且 (2)≠0 → 重建环节出错，修重建；probe-a≠0 → 环境问题，修环境；probe-b=0 且 (2)≠0 → uv 版本行为差异，记录证据后 D2 | `git revert --no-edit <T3-sha>`；**并用 S0 记录的 `sha256sum uv.lock` 核对工作树未被还原** | revert 只回退提交内容；工作树既有 churn 必须仍在（`git diff -- uv.lock \| grep -c upload-time > 0`） |

---

## Post-Execution Verification

Dev Orchestrator 在三个 task 全部提交后**必须**执行本节。

### Automated Verification

| ID | Description | Command（`cd /home/gw/opt/docx-mcp`） | Expected |
|---|---|---|---|
| V1 | 全量测试 | `.venv/bin/python -m pytest -q` | exit 0（0 failed） |
| V2 | 覆盖率门（CI 口径） | `.venv/bin/python -m pytest --cov=docx_mcp --cov-report=term-missing --cov-fail-under=88 -q` | exit 0，TOTAL ≥ 88% |
| V3 | lint | `.venv/bin/python -m ruff check .` | exit 0 |
| V4 | format | `.venv/bin/python -m ruff format --check .` | exit 0 |
| V5 | 三个 commit 结构 | `git log --oneline -3` + `git show --stat --oneline -1`（逐个） | 3 条，分别含 `#T-5128` / `#T-5129` / `#T-2615`；每个 commit 恰 2 文件 |
| V6 | 脏基线未被侵占 | `git status --porcelain=v1` | 仍为「已知脏基线」集合（`M uv.lock` + 原 7 项未跟踪），无新增/消失 |
| V7 | 提交态 lock 无 churn 且语义完整 | `git show HEAD:uv.lock \| grep -c 'upload-time'`；`git show HEAD:uv.lock \| grep -c '^revision = '`；`git show HEAD:uv.lock \| grep -c 'provides-extras'`；`git show HEAD:uv.lock \| grep -c 'version = "0.7.4"'`；`git show HEAD:uv.lock \| grep -c 'version = "0.7.3"'`；`git show HEAD:uv.lock \| grep -c 'specifier = ">=1.28,<2"'` | 0 / 0 / 0 / **1** / **0** / 1（R5 修正：根 version 必须为 0.7.4） |
| V7b | 提交态 lock 差异形状（允许集口径） | `git show HEAD~1:uv.lock > /tmp/t2615/head1-uv.lock`；`git show HEAD:uv.lock > /tmp/t2615/head0-uv.lock`；以二者替换 S4-(1-b) 的两处 `load(...)` 后运行（见 S4-(1-b) 输入约定） | `ALLOW-LIST OK`，exit 0 |
| V7c | 提交态 lock 可被 uv 机械验证 | `mkdir -p /tmp/t2615/verify && git show HEAD:pyproject.toml > /tmp/t2615/verify/pyproject.toml && git show HEAD:uv.lock > /tmp/t2615/verify/uv.lock && (cd /tmp/t2615/verify && uv lock --check)` | exit 0（R5 实测：同形态在规划机 exit 0） |
| V8 | 提交态 pyproject pin | `git show HEAD:pyproject.toml \| grep -n 'mcp>=1.28,<2'` | exit 0，1 行 |

### Probe (best-effort, run if available)

- [ ] P1：`.venv/bin/python -c "import mcp; print(mcp.__version__ if hasattr(mcp,'__version__') else 'n/a')"` → exit 0
- [ ] P2：`cd /tmp/t2615/min && uv lock --check`（与 S4-(2) 同一门禁口径；**R5 规划机实测 exit 0**）→ exit 0；`uv sync --frozen --dry-run` 输出仅作参考，不作判据
- [ ] P3：`libreoffice --version || soffice --version` → 有输出则额外跑一次真实 `convert_to_pdf` 冒烟（无输出记 SKIP）

### Deferred (needs restart / deployment)

- [ ] D1：MCP server 由客户端（opencode/Claude Desktop）重启后重新加载，确认启动不因 mcp SDK 版本报错；重启命令由部署侧提供，不在本 plan 内执行。

### Manual（真正需要人工判断）

- [ ] M1：用 Word 或 LibreOffice 打开 T1 新用例产出的 `kept.docx`，人工确认注释区（Endnotes 分隔符/continuation notice）完整、无「文档损坏」提示。
- [ ] M2：人工阅读三份 commit diff（`git show <sha>`），确认无夹带、无格式 churn、无无关重构。

---

## Execution Log

<!-- Dev Orchestrator 逐 task 追加；每条记录须包含：命令原文、exit code、关键输出行、RED/GREEN 证据路径或摘录。 -->

### [COMPLETED] T1 (#5128) — commit `2b62f9b`
- RED（受控变异：先把当前实现备份为 `/tmp/opencode/t1mut/impl.py` 并记 sha256，再 `git show HEAD~3:docx_mcp/document/base.py > docx_mcp/document/base.py`，跑 `timeout 300 .venv/bin/python -m pytest tests/test_e2e.py -q`）: **exit 1，`5 failed, 143 passed in 1.03s`**；`grep -c '_STRUCTURAL_NOTE_TYPES' <pre-T1 base.py>` = **0**（证明基线确无该判据）。失败用例：
  - `test_keeps_continuation_notice_named_in_settings`
  - `test_keeps_structural_note_without_settings_entry[footnote]`
  - `test_keeps_structural_note_without_settings_entry[endnote]`
  - `test_keeps_plain_note_named_in_settings[footnote]`
  - `test_keeps_plain_note_named_in_settings[endnote]`
  - 代表性断言：`assert result["repairs"][f"orphan_{kind}s_removed"] == 0` → `assert 1 == 0`
- GREEN（`cp /tmp/opencode/t1mut/impl.py docx_mcp/document/base.py` + `sha256sum -c` → `08be432f6f39b6531dfeefe017a8da6c7cded72211fee94538c3791590bbd5ee ... OK`）: `tests/test_e2e.py` **148 passed**；`git diff --stat -- docx_mcp/document/base.py` 为空（工作树复原）
- 回归: `pytest tests/test_e2e.py -k endnote -q` → **7 passed, 141 deselected**（exit 0）；`pytest tests/test_footnote_endnote_crud.py -q` → **27 passed**（exit 0）；`ruff check` / `ruff format --check` 均 exit 0
- 范围: staged 恰 2 文件（`docx_mcp/document/base.py` +40/−6、`tests/test_e2e.py` +88）；`git diff --cached --check` 干净
- commit: `2b62f9b fix(repair): preserve structural and pinned notes during save #T-5128`

### [COMPLETED] T2 (#5129) — commit `d1d0490`
- RED（同法受控变异：`git show HEAD:docx_mcp/document/pdfexport.py > docx_mcp/document/pdfexport.py`，跑 `pytest tests/test_pdf_export.py -q`）: **exit 1，`3 failed, 5 passed in 0.22s`**；失败形态分别为 `KeyError: 'stdin'`、`DID NOT RAISE`、`AttributeError: module ... has no attribute '_resolve_timeout'`；实现复原后 `sha256sum -c` OK
- GREEN: `pytest tests/test_pdf_export.py -q` → **8 passed**（exit 0）；`pytest tests/test_pdf_export.py tests/test_e2e.py -q` → **156 passed**（exit 0）；`ruff check --fix` 清掉 1 处 I001 后 `ruff check` / `ruff format --check` 均 exit 0
- 真实环境冒烟（P3，LibreOffice `24.2.7.2` 可用）: `DocxDocument.create('/tmp/t2615/pdfsmoke/smoke.docx').convert_to_pdf('/tmp/t2615/pdfsmoke/smoke.pdf')` → `{'pdf_path': ...}`，文件存在 1429 B、magic `b'%PDF-'`、**elapsed 0.70 s**（远低于 `DEFAULT_TIMEOUT=90.0`）→ stdin 隔离与 timeout 传参路径在真实 soffice 下不回归
- 范围: staged 恰 2 文件（`docx_mcp/document/pdfexport.py` +59/−13、`tests/test_pdf_export.py` +47）
- commit: `d1d0490 fix(pdfexport): isolate LibreOffice stdin and bound conversion time #T-5129`

### [COMPLETED] T3 (#2615) — commit `804ebdb`
- 解析版本 `<X>`: **`1.30.0`**（`uv lock` stderr: `Updated mcp v1.26.0 -> v1.30.0`，`Resolved 94 packages in 1.16s`，exit 0；`uv 0.12.0`）
- 重建校验（S3 脚本产物 `/tmp/t2615/min/uv.lock`）: 移除 `upload-time` **1656** 处、`provides-extras` **1** 处、`revision =` **1** 行；根 `version = "0.7.4"` **=1**、`0.7.3` **=0**；mcp 块 version `1.30.0` 满足 `1.28 <= X < 2`；无 `, }` / `,,` 残渣
  - S4-(1-a) grep 计数: `upload-time=0` / `revision=0` / `provides-extras=0` / `v0.7.4=1` / `v0.7.3=0`
  - S4-(1-b) 允许集分类器: 变化块 = `['docx-mcp-server', 'exceptiongroup', 'mcp', 'numpy', 'pydantic-core']`，**`ALLOW-LIST OK`，exit 0**（顶层头在 strip `resolution-markers` 后逐字节一致）
  - S4-(2) `(cd /tmp/t2615/min && uv lock --check)` → **exit 0**（未触发 (2b) probe-a/probe-b，按归因表「(2)=0 → 通过」）；(2c) `uv sync --frozen --dry-run` 参考输出 `+ mcp==1.30.0`
  - S4-(3) PyPI sha256: sdist `445414…a3e4`、wheel `666edb…84d0` 两条 **均 OK**，exit 0
- 暂存审计（S5 用 `git hash-object -w` + `git update-index --cacheinfo 100644,99c0f301…,uv.lock`，工作树零写入）: `git diff --cached --name-only` **2 行**；`git diff-tree -r "$(cat tree-before.txt)" "$(git write-tree)"` **2 行**；`git diff --cached -U0 -- pyproject.toml` 仅 1 行 `mcp>=1.0.0` → `mcp>=1.28,<2`；`staged.lock` 的 sha256 = `40853dd5…2857` 与 `/tmp/t2615/min/uv.lock` 完全一致；staged 计数 `upload-time=0 / revision=0 / provides-extras=0 / v0.7.4=1 / v0.7.3=0 / specifier=1`；对 `staged.lock` 重跑分类器 → `ALLOW-LIST OK`
- 提交后: `git diff-tree --no-commit-id --name-only -r HEAD` → **恰 2 行**（`pyproject.toml`、`uv.lock`）；`git show HEAD:uv.lock` 计数 `0/0/0/1/0/1`；`uv sync` → `- mcp==1.26.0`、`+ mcp==1.30.0`（exit 0）；`.venv/bin/python -c "import docx_mcp.server"` → `server import OK`；`pytest tests/test_e2e.py tests/test_pdf_export.py -q` → **156 passed**；`pytest tests/test_pdf_export.py -q` → **8 passed**
- 工作树保留证据: `git status --porcelain -- uv.lock` → **` M uv.lock`**；`git diff -- uv.lock | grep -c upload-time` → **1656**（未 checkout / 未覆盖）；`git status --porcelain` 仍为原 8 项脏基线（`.coverage` 由 V2 覆盖率跑产生，已 `rm -f` 清除）
- commit: `804ebdb fix(deps): pin mcp>=1.28,<2 防止 MCP SDK 2.x 破坏 fresh install #T-2615`

### [COMPLETED] Post-Execution Verification（V1–V8 / P1–P3，2026-10-31 23:07 CST）
- V1 全量测试: `pytest -q` → **1155 passed, 17 skipped, 1 warning**，exit 0
- V2 覆盖率门: `pytest --cov=docx_mcp --cov-report=term-missing --cov-fail-under=88 -q` → **TOTAL 90.26%**（≥88%），exit 0
- V3 `ruff check .` → `All checks passed!` exit 0；V4 `ruff format --check .` → `144 files already formatted` exit 0
- V5 三个 commit: `2b62f9b` / `d1d0490` / `804ebdb`，message 分别含 `#T-5128` / `#T-5129` / `#T-2615`，每个 commit **files=2**
- V6 脏基线: ` M uv.lock` + 原 7 项未跟踪，无新增/消失（恢复为执行前集合）
- V7 提交态 lock: `upload-time=0 / revision=0 / provides-extras=0 / v0.7.4=1 / v0.7.3=0 / specifier=1`；V7b（`head1-uv.lock` vs `head0-uv.lock`）→ `ALLOW-LIST OK` exit 0；V7c（`/tmp/t2615/verify`）→ `uv lock --check` exit 0
- V8 `git show HEAD:pyproject.toml | grep -n 'mcp>=1.28,<2'` → `22:    "mcp>=1.28,<2",` exit 0
- P1 `import mcp; mcp.__version__ if hasattr(...)` → `n/a`（1.30 未暴露 `__version__`），exit 0；P2 `/tmp/t2615/min` `uv lock --check` → exit 0；P3 LibreOffice `24.2.7.2` 可用 → 真实 PDF 冒烟见 T2 条目
- D1（客户端重启加载）/ M1（Word 打开 `kept.docx` 目视）/ M2（人工读 diff）: **未执行**，留待用户/部署侧
- 未 push: `git status -sb` → `## main...origin/main [ahead 6]`（本 plan 3 个 commit + 既有 3 个本地 commit）

### [COMPLETED] 独立验收（acceptance-verifier，2026-10-31 23:07 CST 之后）
- 三源交叉（AC 原文 / Execution Log / `git show` + `diff-tree`）：三 commit 各 **2 文件**、tag 对应正确、无夹带
- 逐任务 verdict：**#5128 PASS** · **#5129 PASS** · **#2615 PASS**；总体 **PASS**（confidence HIGH，blocking 0）
- 独立只读变异复现：T1 回退 skip 判据 → `5 failed, 143 passed`（失败用例名与本 log 逐条相同）；T1 改 fail-open → `test_strips_orphan_with_unknown_type[footnote]/[endnote]` **2 failed**（白名单语义被锁定）；T2 删两 kwargs → `1 failed, KeyError: 'stdin'`
- 全局门复跑：`pytest -q` 1155 passed / 17 skipped；`ruff check .` 与 `ruff format --check .` 均 exit 0；`git status --porcelain` 精确 8 项脏基线（无 `.coverage` 残留）
- 偏离/关注（均不阻断）：C1 白名单 fail-closed 为计划声明内有意偏离；**C2 计划侧「能失败证明」表述偏差**——T2 AC1 列写「删 kwargs → 2 用例失败」，实测仅 1 failed（两个 kwargs 分别由 AC2/AC3 独立锁定，覆盖无缺口）；C3 `opencode.jsonc` per-server timeout 块未逐块穷举（docx-mcp 区段已核对，无覆盖 → 继承全局 120 s）；C4 变异副本 `/tmp/acc-mut` 因只读权限未删（在 `/tmp`，不入仓）
- 待人工/部署侧（本 plan 不执行）：D1 客户端重启加载、M1 Word 打开 `kept.docx` 目视、M2 人工读三份 diff

---

## 整合后阶段 A — rebase 后状态与证据边界（2026-11-02 11:05 CST 追加）

> 本节为**追加记录**，不修改上列 2026-10-31 的任何历史测试结果、commit sha 与 verdict。上文 T1=`2b62f9b` / T2=`d1d0490` / T3=`804ebdb` 的记录**在其时点真实有效**；本节记录其后 main 经 SDK v2 迁移 + rebase 整合后的实际情况。**日期取自 `date` 实测**：`Mon Nov  2 11:01:58 AM CST 2026`（本节撰写时复测 11:05 CST）。

### A1 授权与决策（用户 `question` 裁决）

| 项 | 用户裁决 | 落地 |
|---|---|---|
| rebase 冲突处置 | 选择 **replay 另 5 个 commits**（在 SDK v2 迁移后的 main 上重放），**drop T3** | ✅ 已执行 |
| #2615（mcp pin `<2`） | **superseded（被取代）**，按 done 关闭——SDK v2 迁移已把约束推到 `mcp>=2,<3`，`<2` 上界与迁移方向互斥（原计划 R-6 已预判） | ✅ 状态 done / superseded |
| 备份锚点 | `backup/pre-rebase-T3` = **`804ebdb`**（rebase 前 T3 提交，`git rev-parse` 实测存在；即原 T3 的最终证据锚） | ✅ 保留 |

### A2 整合后 main 的对应关系

| 原 commit | 整合后 main | 说明 |
|---|---|---|
| T1 `2b62f9b`（#5128 endnote 修复） | **`6706fe0`** `fix(repair): preserve structural and pinned notes during save #T-5128` | replay 后等价内容，2 文件 |
| T2 `d1d0490`（#5129 pdfexport stdin/timeout） | **`ec5fcd7`** `fix(pdfexport): isolate LibreOffice stdin and bound conversion time #T-5129` | replay 后等价内容，2 文件 |
| T3 `804ebdb`（#2615 pin `<2`） | **无对应 commit（dropped）** | 约束改由 SDK v2 迁移落地：`pyproject.toml:22` 现为 **`"mcp>=2,<3"`**（实测）；原 `<2` 上界作废 |

- 整合后 main 后续 docs 提交：`976f415`(#T-5167 Requirements 对齐 `mcp>=2,<3`) · `1f45138`(#T-5168 记录 save-time note repair) · `e5f0053`(#T-5169 PDF export 前置条件/timeout/singleton 限制) · `5a1351e`(#T-5170 roadmap 刷新)。
- **venv 现状**：2.0.0，与 `pyproject.toml` 的 `mcp>=2,<3` 一致（不再是原计划的 1.30.0 —— 原 T3 的 1.28≤X<2 断言口径已被 superseded，不得再据此判失败）。

### A3 全量门复跑（整合后 main，2026-11-02）

| 门 | 结果 |
|---|---|
| `pytest -q` | **1157 passed, 17 skipped**，exit 0（较整合前 1155 passed 增 2，来自 T1/T2 相关新增用例在 rebase 后完整生效；**非重跑替换旧值，旧值 1155 保留于 §Post-Execution Verification V1**） |
| 覆盖率 | **TOTAL 90.29%**（≥88% 门），exit 0（旧值 90.26% 保留） |
| `ruff check .` | pass，exit 0 |
| `ruff format --check .` | pass，exit 0 |
| `uv lock --check` | pass，exit 0（lock 与 `mcp>=2,<3` 一致） |

### A4 部署侧验证（D1）与 falsifier 结论

- **D1 后端**：systemd 重启 docx-mcp HTTP 服务后，`open` / `save` / `close` **均成功** → 后端侧 D1 **通过**。
- **D1 边界**：**未重启 OpenCode 客户端**——故「客户端重启后重新加载不报错」这一条**未验证**，不得据此声称客户端侧 D1 通过。
- **版本号陷阱（重要）**：HTTP `serverInfo` 报 **`1.30.0`**，该值**不能视作后端 mcp SDK 版本**（HTTP 面暴露的不是运行库版本）。
- **独立 falsifier**：会话 `ses_e6601f622ffeGZxJlAXj1j6jeV` 复核该判断，**verdict = SURVIVED**——falsifier 未能推翻，依据是 **stdio 侧 `version` 为空 + bridge 侧 SDK `1.30` fallback**，即 `1.30.0` 来自 fallback 而非常驻服务真实版本。

### A5 M1 人工验收边界（不得过度声称）

- 已完成：**LibreOffice** 打开 T1 新用例产出的样本，图片检查结果与样本像素**一致**（未见损坏提示）。
- **未执行**：**Word 原生**打开 `kept.docx`。因此 M1 结论**不能**表述为「同输入严格 before/after 对比」——LibreOffice 渲染与 Word 原生渲染不可互替。
- 结论口径：M1 记为 **PARTIAL**（LibreOffice 侧通过；Word 原生侧未验证）。

### A6 已知未解问题

- **PDF singleton 缺 `handle`** 仍为 **known issue**（未修复）；与整合无关，记录以免被误读为已闭环。

### A7 证据边界（本节所有结论的适用上限）

1. **push 尚未成功**：整合后 main 与远端仍不完全同步，`git status -sb` 显示本地 **ahead**（含本 plan 之外的本地提交）；**不得**在任何文档中记录为「已 push」。
2. **验证范围**：测试/lint/覆盖率/lock 门均在**本机 main 工作树**复跑；未在 CI、未在远端、未在其他机器验证。
3. **#2615 不是「已修复」而是「superseded」**：`<2` 上界从未进入整合后 main；其需求由 #2625（SDK v2 迁移）吸收。
4. **M1 的 LibreOffice 侧结论不可升级为 Word 侧结论**；D1 的后端侧结论不可升级为客户端侧结论。
5. 本节**不覆盖**上文历史记录：三个原始 commit sha、当时的 1155 passed / 90.26%、以及 2026-10-31 的独立验收 PASS×3 均为其**时点事实**，继续有效。

---

## 整合后阶段 B — 发布记录与最终状态（2026-11-02 14:09 CST 追加）

> 本节为**追加记录**，不修改阶段 A（2026-11-02 11:05 CST）及更早的任何历史结论。**日期取自 `date` 实测**：`Mon Nov  2 14:09:41 PM CST 2026` → `2026-11-02 14:09:41 CST`。

### B1 push 状态（推翻 A7-1 的「push 尚未成功」）

| 项 | 实测值 | 命令 |
|---|---|---|
| `main` | `56fec9ef3ff870c4327d0eebf161143a2f4a7c08` | `git rev-parse main` |
| `origin/main` | `56fec9ef3ff870c4327d0eebf161143a2f4a7c08` | `git rev-parse origin/main` |
| 关系 | **完全一致**（`origin/main..main` = 0，`main..origin/main` = 0） | `git rev-list --count` 双向 |
| `git status -sb` | `## main...origin/main`（**无 ahead/behind 标记**） | — |
| push 方式 | **普通 `git push`（非 force）**，成功 | — |

**结论**：A7-1 记录的「push 尚未成功」在此时点**已失效**——整合后 main 已通过普通 push 与远端同步。A7-1 作为**其撰写时点（11:05 CST）的事实**继续有效，不得据其否定本节的发布结果。

- 本次 push 覆盖的 5 个文档 commit（`ec5fcd7..HEAD`，即 D2–D5 的全部产出）：
  `976f415`(#T-5167) · `1f45138`(#T-5168) · `e5f0053`(#T-5169) · `5a1351e`(#T-5170) · `56fec9e`(#T-5169 follow-up，NaN/inf 边界)
- 区间起点锚为 **`ec5fcd7`（不含）**——即上一轮 T2 整合提交；`ec5fcd7..HEAD` 实测恰 **5** 个 commit、**3** 个文件（`README.md`、`docs/plans/2026-07-27-real-world-defects-roadmap.md`、`.github/reviews/defect-roadmap-verification-2026-07-27.md`），`docx_mcp/`、`tests/`、`pyproject.toml`、`uv.lock` **零改动**。

### B2 D2–D5 独立验收（复跑，2026-11-02 14:09 CST）

| 任务 | 独立复跑命令 | 结果 |
|---|---|---|
| D2 #5167 | `docs-followup.md` §4 W1 T-B（README `mcp{spec}` 与 `pyproject.toml` 同源） | **PASS**（`D2 OK mcp>=2,<3`，exit 0） |
| D3 #5168 | §4 W2 T-B（三 note type 名与 `base.py::_STRUCTURAL_NOTE_TYPES` 同源 + pinned/unknown 语义） | **PASS**（`D3 OK ['separator','continuationSeparator','continuationNotice']`，exit 0） |
| D4 #5169 | §4 W3 T-B（`DEFAULT_TIMEOUT`=90.0 同源 + 解析规则 + singleton 限制）+ T-A（`def convert_to_pdf` 无 handle，README 主张为真）+ NaN/inf 边界句 | **PASS**（`D4 OK default=90.0`；T-A `OK: no handle, README claim true`；`README.md:356` Edge cases 句在位） |
| D5 #5170 | §4 W4 AC1（9 个引用 hash 全部 `git cat-file -e` 通过且为 HEAD 祖先）+ AC2（Bug2 非 FIXED / handle 覆盖率 2 已补 6 缺，与源码一致） | **PASS**（`checked 9 hashes; bad: []`；`D5 AC2 OK`） |
| 结构 | §6 V1 `git diff --stat --name-only ec5fcd7..HEAD`；V3 源码零改动；V6 三个标题各恰 1 次 | **PASS**（3 文件 / 空输出 / 1·1·1） |

> **V1/V3 区间口径修正**：`docs-followup.md` §6 V1 与 V3 原写作 `HEAD~4..HEAD`，该口径**与实际不符**——D2–D5 实际产生 **5** 个文档 commit（`56fec9e` 为 D4 follow-up，见该计划 §8 执行期发现 #5 / §9.1），`HEAD~4` 会漏掉 `976f415`（D2）。**正确区间为 `ec5fcd7..HEAD`**，本记录即按此口径复跑通过。`docs-followup.md` 已在归档副本中同步更正（见 `completed/docs-followup.md` §6 注记）。

### B3 偏差登记（要求逐项保留，不得静默升级）

| 偏差 | 实际边界 | 不得声称 |
|---|---|---|
| **D4 补充提交偏差** | D4 (#5169) 原计划**单 commit**；实际产生 **2 个 commit**：`e5f0053`（主体）+ `56fec9e`（NaN/inf edge-case follow-up，应用户复核反馈追加）。两者均 `#T-5169`、均仅改 `README.md`。 | ❌ 不得称「D4 仅一个 commit」；❌ 不得称 D4 首轮即完整 PASS（首轮 verdict 为 **PARTIAL**，无 blocking，仅缺非有限值边界说明）。 |
| **D1（部署侧）** | **仅后端** systemd 重启 docx-mcp HTTP 服务后 `open`/`save`/`close` 成功。**未重启 OpenCode 客户端**，客户端侧「重启后重新加载不报错」**未验证**。 | ❌ 不得称「D1 全部通过」或「客户端侧验证通过」。 |
| **M1（人工验收）** | **仅 LibreOffice** 打开样本、图片检查与样本像素一致。**Word 原生**打开 `kept.docx` **未执行**。 | ❌ 不得称「Word 原生验证通过」或「同输入严格 before/after 对比」。 |
| **PDF singleton 缺 handle** | `convert_to_pdf` **仍无 `document_handle`** 参数；`DOCX_MCP_REQUIRE_HANDLE=1` 下该工具**不可用**（`RuntimeError: document_handle is required in singleton mode ...`）。**未修复**，仍为 known issue。 | ❌ 不得称「PDF 导出已支持多会话隔离」或「singleton 限制已解决」。 |

### B4 PM 状态（2026-11-02 14:09 CST 实测）

| 任务 | PM status | progress | 备注 |
|---|---|---|---|
| #5167 (D2) | `done` | 100% | — |
| #5168 (D3) | `done` | 100% | — |
| #5169 (D4) | `done` | 100% | 含 follow-up commit `56fec9e` |
| #5170 (D5) | `done` | 100% | — |

四个任务均 `done / 100%`（由 commit trailer `done 100% #T-<id>` 自动置位，本节复测确认，无需额外写操作）。

### B5 最终状态

**状态：COMPLETED** — 整合后 main 与 `origin/main` 一致于 `56fec9e`（普通 push 成功）；D2–D5 独立复跑全部 PASS；PM 四任务 done 100%。上列 B3 四项偏差为**已登记的证据边界**，不构成本计划未完成项。

---

## 审查日志

| 轮次 | 聚焦 | 发现问题数 | 已修正 | 剩余 |
|------|------|-----------|--------|------|
| R1 | 结构完整性（task/AC/modifications/边界/wave 是否齐备） | 2 | 2 | 0 |
| R1.5 | 外部引用事实核查（上游 PR diff、文件路径、行号锚点、命令、版本） | 3 | 3 | 0 |
| R2 | 可执行性（基线命令实测 + 脚本干跑） | 2 | 2 | 0 |
| R2.8 | LLM 可执行性/歧义消解（路径、动作、期望值、D2 条件） | 2 | 2 | 0 |
| R3 | 风险与边缘（跨 task 契约、回滚、粒度门、脏基线保护） | 2 | 2 | 0 |
| R4 | CT（critical-thinking, verdict=MINOR）裁定落地复核：4 blocking + 4 caution | 8 | 8 | 0 |
| R5 | CT 第 2 轮（verdict=MINOR）唯一新 blocking NEW-B1：`uv lock --check` 门禁在「回退根 version」形态下必然失败 | 1 | 1 | 0 |
| **终止** | **T1（issue 清零）— R5 后复核** | | | **0** |

**R1.5 核查记录（实测）**
- 上游补丁：已拉取 `SecurityRonin/docx-mcp` PR #25 / #22 / #16 的 `.diff`；#25 的 hunk 上下文与本仓 `base.py` L278/L300/L312、`tests/test_e2e.py` L593 一致；#22 与 `pdfexport.py` L43-59 一致；#16 确认为分支污染（含 `formatting.py`/`tracks.py` 等）→ 已在 R-1 显式禁止 cherry-pick。
- 测试基线实测：`test_e2e.py -k endnote` 4 passed；`test_footnote_endnote_crud.py` 27 passed；`test_pdf_export.py` 5 passed。
- 锁文件探针实测：`uv 0.12.0`；`uv lock` 后 mcp 1.26.0 → 1.30.0（包数不变）；`uv sync --frozen --dry-run` exit 0 —— **R4 已证伪：该命令对 stale lock 同样 exit 0，不构成门禁**，现仅作参考 (2c)；PyPI sha256 与 lock 条目一致（wheel `666edb…`、sdist `445414…`）。
- 断言修正：PM #2615 AC3 原命令的字符串比较 `v>='1.28'` 对 `1.30.0` 逻辑脆弱 → 保留原命令并补硬化版（元组比较）。

**R4 修订记录（CT verdict=MINOR，逐条落地）**

| # | CT 裁定 | 落点（节/行） | 修正内容 |
|---|---|---|---|
| B1 | `uv sync --frozen --dry-run` 对 stale lock 也 exit 0，**不构成门禁** | T3 S4-(2) / (2c)、R-2、P2、R1.5 记录 | 门禁改为在 `/tmp/t2615/min` 副本（pyproject 已 pin + 重建 lock）内跑 `uv lock --check`，非 0 → **(2b) 判别探针** → S8-D2；原命令降级为「参考，不作判据」（**R5 精化**：(2b) 仅在非 0 时执行且用于归因，不做「churn 回退必致失败」的断言） |
| B2 | pin 到 mcp 1.30 会派生 6 支 `resolution-markers` + `exceptiongroup`/`numpy`/`pydantic-core` 语义变化，**必须随本题提交**；R4 当时认定 churn = `revision = 3` / `upload-time` / 根 version 0.7.3→0.7.4（**该第三项已被 R5 推翻**：根 version 属基线 stale 修正，必须提交 0.7.4） | A-3、A-4、D-1、T3 modifications、⛔边界、S3、S4-(1)、S6、AC*、V7/V7b、已知脏基线 | 重建策略从「HEAD + mcp 块」改为「gen-after 回退 churn」；新增**允许集分类器**（包块级）取代固定 hunk/行数断言；明确「不得剥离语义派生」。**R4 干跑补充**：实测 uv 0.12 还新增根块 `provides-extras = ["equations"]`（HEAD 无）→ 作为 churn 一并回退（同属「HEAD 无的格式元数据」） |
| B3 | T2 `DEFAULT_TIMEOUT` 120.0 → **90.0**，理由改为「必须显著小于部署侧 opencode `mcp.timeout.execution=120000`ms 硬顶」 | D-2、T2 modifications、S2 测试、S3 常量+docstring、潜在风险 | 常量与 docstring 同步；超时测试改 `timeout=90.0` + `match=r"timed out after 90"`（仍按 f-string 秒数）；`test_subprocess_gets_...` 增加 `monkeypatch.delenv` + `timeout < 120.0` + `DEFAULT_TIMEOUT < 120.0` 断言 |
| B4 | T1 A-6 事实错误：fixture `settings.xml` 实为空 `<w:settings/>`，pin 由 `_pin_in_settings` 自建 | A-6、S2 helper、潜在风险 | 修正假设与依据；helper docstring 说明「模拟 Word 写法」；新增**回读断言** `set(note_ids) <= written`，防 helper 静默失效导致测试作弊通过 |
| C5 | `_is_structural_note` 改**白名单** `{separator, continuationSeparator, continuationNotice}`，未知 type 仍按孤儿处理；记为 D1 偏差 | D-5（新增）、S3-1、A-6、潜在风险 | fail-open → fail-closed；新增 `test_strips_orphan_with_unknown_type`（2 id）证明白名单 fail-closed，并纳入 AC2-② |
| C6 | 索引/工作树长期不一致：禁 `git commit -a`/`-am`；中止路径 `git reset -q -- uv.lock`；S0/S6 记录 `HEAD^{tree}` 与 `git write-tree`；提交后断言恰 2 文件 | D-6（新增）、S5、S6、S7、R-3、AC6 | 新增树对照断言与 `git diff-tree --no-commit-id --name-only -r HEAD`；明文禁止 `-a`/`-am`/`git add uv.lock` |
| C7 | T3 AC5 扩展：`uv sync` 后 `python -c "import docx_mcp.server"` + `pytest tests/test_e2e.py tests/test_pdf_export.py -q`，失败即 D2 | T3 S7、AC5 | AC5 从单文件冒烟扩展为运行时面（server 导入 + 双文件回归），失败路径指向 S8-D2 |
| C8 | footnote/endnote id 比较口径统一 | T1 S3-3、modifications | 两分支均 `str(int(...))` 归一后与 `pinned` 比较；endnote 的 `(0, -1)` 判断改为 int 比较，`en_id` 提前计算 |

**R4 干跑验证（本机实测，未改动生产代码）**
- 允许集分类器在 4 个合成用例上行为正确：① 完全相同 → `ALLOW-LIST OK` exit 0；② 仅 mcp specifier 变 → exit 0；③ 仅顶层 `resolution-markers` 变 → exit 0；④ `mistune` 版本行变 / `requires-python` 变 → exit 1 并分别报告 `changed package not in allow-list: mistune`、`top-level header changed outside resolution-markers`。
- S3 重建脚本对「工作树 lock（uv 0.12 产物）+ 伪造 specifier」干跑：`revision` 删除 1 行、`upload-time` 删除 1656 处、`provides-extras` 删除 1 行、根 version 回退（**R5 已改为保留 0.7.4，见 R5 记录**），且 `', }'` 残渣断言通过；对 mcp 版本不满足 `[1.28, 2)` 的输入按预期 AssertionError（证明范围断言有效）。
- 干跑后分类器对「重建结果 vs HEAD」返回 `ALLOW-LIST OK`（差异仅 mcp specifier）——即重建逻辑在结构上可通过允许集门；真实 pin 后的 markers/依赖派生由允许集覆盖。

**R4 影响复核**：三个 task 仍 ≤30 min（T1 22–27 / T2 15–20 / T3 27–30）；仍为 3 个独立 commit、不 push；仍然不触碰既有脏基线（`M uv.lock` churn 与 7 项未跟踪）；T3 因新增分类器与树断言 +3 min，checkpoint 重设为 10 / 24 / 28 min。

**R5 修订记录（CT 第 2 轮 verdict=MINOR → 唯一新 blocking NEW-B1）**

| # | CT 裁定 | 落点（节） | 修正内容 |
|---|---|---|---|
| NEW-B1 | T3 S4-(2) 用 `uv lock --check`，但提交目标要回退根 version `0.7.4→0.7.3` → 门禁必然失败 | 非目标、A-4、D-1、已知脏基线、T3 modifications、⛔边界、S0/S3/S4/S6/S7、AC2/AC*、V7、R-2b/R-3b、P2、失败处置、Execution Log | churn 集 **四项 → 三项**；根 version `0.7.4` 从**禁止集**移入**必须提交项**（基线 stale 修正）；S3 删除回退逻辑，新增 `root version kept 0.7.4` 与 `0.7.3 count == 0` 断言；S4-(1-a)/S6/S7/V7 的 version 计数由 `0` 改为 `1` 并新增 `0.7.3 == 0`；S4-(2) 期望改为**必须 exit 0**；(2b) 改为「仅非 0 时归因」并新增 probe-b（根 version 回退对照） |
| NEW-B1b | 允许集分类器必须允许根 version `0.7.4`（否则合法提交被判违规） | S4-(1-b)、S6 语义口径 | 新增 `root_version()` / `norm_root()`（归一化 mcp specifier + 根 version + provides-extras）；新增硬判 `root project version must stay 0.7.4`（防回退）与 `unexpected HEAD root version`（防 HEAD 漂移）；合成用例扩为 5 例 |
| NEW-B1c | 计划内 `grep 'specifier = "mcp>=1.28,<2"'` 与锁文件真实写法不符（真实为 `{ name = "mcp", specifier = ">=1.28,<2" }`），S0/S6/S7/V7/AC2 必假失败 | S0、AC2、S6、S7、V7 | 统一改为 `specifier = ">=1.28,<2"`（实测：HEAD lock 旧 specifier 恰 1 次、重建 lock 新 specifier 恰 1 次） |
| C-new | T2 `test_timeout_becomes_explicit_runtime_error` 缺 `monkeypatch.delenv("DOCX_MCP_PDF_TIMEOUT", raising=False)` | T2 S2 测试、潜在风险 | 补 fixture 参数 + delenv + 注释；风险节说明污染环境下的假失败机理（不改测试数量与其余步骤） |

**R5 实测证据（规划机 uv 0.12.0；未改动生产代码与工作树 lock）**
- 基线 stale 判定：`git show HEAD:pyproject.toml` 第 7 行 = `version = "0.7.4"`；`git show HEAD:uv.lock` 根包 = `docx-mcp-server 0.7.3`。
- `uv lock --check` 三态实测：
  - `HEAD` lock + `HEAD` pyproject（副本 `/tmp/t2615/headtest`）→ **exit 1**（`error: The lockfile at 'uv.lock' needs to be updated`）→ HEAD 自身即 stale；
  - 重建版**回退**根 version 0.7.3（`/tmp/t2615/min`）→ **exit 1**；
  - 重建版**保留**根 version 0.7.4（`/tmp/t2615/vA`，以及按新 S3 脚本重建的 `/tmp/t2615/r5min`）→ **exit 0**（`Resolved 94 packages`）。
  - 结论：失败根因是**根 version 与 pyproject 不一致**，与 `revision` / `upload-time` / `provides-extras` 的三项回退**无关**（三项回退后 uv 仍认可）。
- 新分类器合成用例（5/5 符合预期）：① `head` vs `r5min` → `ALLOW-LIST OK` exit 0；② `mistune` 版本行改 → exit 1 `changed package not in allow-list: mistune`；③ 顶层头 `requires-python` 改 → exit 1 `top-level header changed outside resolution-markers`；④ 根块 `spacy` specifier 改 → exit 1 `root project block changed beyond mcp specifier / root version`；⑤ 根 version 回退 0.7.3 → exit 1 `root project version must stay 0.7.4, got 0.7.3`。
- 新 S3 脚本干跑（`/tmp/t2615/r5min`）：`removed upload-time fields: 1656 | removed provides-extras: 1 | root version kept: 0.7.4 | mcp version in reconstructed lock: 1.30.0`。

**R5 影响复核**：三个 task 仍 ≤30 min（T1 22–27 / T2 15–20 / T3 27–30）；仍为 3 个独立 commit、不 push；T3 改动只在计划文本与 `/tmp` 副本操作，**不触碰工作树 `uv.lock`**（脏基线保护不变：`git diff -- uv.lock | grep -c upload-time > 0` 仍为提交后断言）。


**R3 粒度门**：T1 22–27 min、T2 15–20 min、T3 27–30 min，均 ≤30 min 且含独立 checkpoint（RED/GREEN/校验），无 >60 min 单步 → 通过（R5 复核后维持：R5 只改期望值与断言口径，未新增 >30 min 单步；`uv lock --check` 在 min 副本内为毫秒级）。

---

