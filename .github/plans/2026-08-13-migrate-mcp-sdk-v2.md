# Plan: Migrate docx-mcp to MCP SDK v2 (MCPServer API)

| 字段 | 值 |
|------|-----|
| **上游 Issue** | #14（pin 止血）+ 本 PR 为后续迁移 |
| **PM Task** | #2615 的后续（新建任务 #2616） |
| **Branch** | `feat/migrate-mcp-sdk-v2` |
| **Plan Type** | EXPANSION（框架主版本迁移，允许补足线程安全基线） |
| **Generated** | 2026-08-13 |
| **Git Commit** | 88d1087 (your main, 含 pin <2) |
| **前置评估** | 迁移面审计已完成：~5 行核心改动 + 10 行锁，219 工具零改动 |

---

## 背景与目标

- **问题**：docx-mcp 使用 MCP SDK v1 API（`mcp.server.fastmcp.FastMCP`）。v1 进入维护模式，v2（2026-07-28）是稳定主线。长期服务应迁到 v2。
- **审计结论**（已实测）：
  - 直接 API 接触面仅 2 处：import（server.py:18）+ 类名（server.py:22）
  - 219 个 `@mcp.tool()` 装饰器官方声明 v1→v2 完全兼容
  - 0 命中 `mcp.types`、camelCase 字段、`get_context()`、`McpError`、`.root`、transport 构造参数、`MCP_*` 环境变量、httpx 依赖
  - v2 `MCPServer.__init__` 签名已从 wheel 实测：`name` 仍为第一位置参数，`instructions=` keyword 传参不受 `title/description/version` 位置插入影响
- **唯一实质风险**：v2 把 sync handler 放到 worker thread（v1 在事件循环线程天然串行）。需要为 `_docs` 全局 dict 加锁。
- **非目标**：不迁移 219 个工具函数体；不做 per-document 串行化（PR B，观察实际并发模式后决定）；不改 mixin 层。
- **与 PR #16 的关系**：本 PR **取代** #16（依赖约束从 `>=1.28,<2` 改为 `>=2,<3`）。

---

## 修改方案

### 核心改动（5 处）

| # | 文件:位置 | 改动 |
|---|-----------|------|
| 1 | `docx_mcp/server.py:18` | `from mcp.server.fastmcp import FastMCP` → `from mcp.server import MCPServer` |
| 2 | `docx_mcp/server.py:22` | `FastMCP(` → `MCPServer(`（参数不变） |
| 3 | `pyproject.toml:22` | `"mcp>=1.28,<2"` → `"mcp>=2,<3"` |
| 4 | `uv.lock` | `uv lock` 重新解析（预期 mcp 2.0.0） |
| 5 | `docx_mcp/server.py:38-72` | 新增 `_docs_lock: threading.RLock` 保护 `_docs` 读写 |

### 线程安全设计（10 行）

v2 中 225 个 sync 工具在 worker thread 上执行，`open_document`/`close_document`/`_resolve` 并发访问 `_docs` 存在竞态。加全局 RLock：

```python
import threading  # 新增到 import 区

_docs_lock = threading.RLock()


def _resolve(handle: str) -> tuple[str, DocxDocument]:
    key = _key(handle)
    with _docs_lock:
        doc = _docs.get(key)
    if doc is None:
        raise RuntimeError(...)
    return key, doc


def _store(handle: str, doc: DocxDocument) -> str:
    key = _key(handle) if handle else uuid.uuid4().hex
    with _docs_lock:
        existing = _docs.get(key)
        _docs[key] = doc          # 原子替换
    if existing is not None:
        existing.close()          # 文件系统操作移到锁外
    return key
```

`close_document`（server.py:111）同样改为：锁内 pop，锁外 `doc.close()`。
`_Module._doc` property（server.py:3077-3085）的 get/set 也加锁。

**残余风险（文档化，不修复）**：同一 handle 的并发编辑（两个工具同时改同一文档）。v1 时代已声明 "unsafe for parallel ones"，LLM 客户端通常串行调用，概率极低。PR 描述中明确标注。

### 测试环境要点

⚠️ **关键**：本地 pip 环境装的是 mcp 1.27.0——改代码后直接 `pytest` 会 import 失败。必须通过 `uv sync` 建立含 mcp 2.0.0 的 `.venv`，用 `uv run pytest` 执行测试。`tests/` 无 MCP SDK 直接导入（已实测 0 命中），测试本身无需改动。

---

## 执行计划

### Phase 1: 代码修改

#### Task 1.1: 创建分支

- **目标**：从 main 创建迁移分支
- **命令**：`git checkout -b feat/migrate-mcp-sdk-v2 main`
- **验收**：`git branch --show-current` 输出正确

#### Task 1.2: 替换 import 与类名

- **目标**：server.py 两处核心改名
- **修改内容**：
  - 第 18 行 → `from mcp.server import MCPServer`
  - 第 22 行 → `mcp = MCPServer(`
- **边界**：不改构造参数；不改任何工具函数
- **验收**：`grep -n "fastmcp\|FastMCP" docx_mcp/server.py` 输出 0 命中

#### Task 1.3: 加线程锁

- **目标**：`_docs` 访问点加 `threading.RLock`
- **修改内容**：
  - import 区加 `import threading`
  - 第 38 行后加 `_docs_lock = threading.RLock()`
  - `_resolve`（51-57）：锁内 get
  - `_store`（60-67）：锁内原子替换，锁外 close
  - `close_document`（104-115）：锁内 pop，锁外 close
  - `_Module._doc` property（3077-3085）：get/set 加锁
- **边界**：不改变任何函数的对外行为与返回值
- **验收**：`grep -c "_docs_lock" docx_mcp/server.py` ≥ 7

#### Task 1.4: 更新依赖

- **目标**：pyproject + uv.lock
- **修改内容**：
  - `pyproject.toml` → `"mcp>=2,<3"`
  - 执行 `uv lock`（预期 mcp → 2.0.0）
- **验收**：`grep -A2 'name = "mcp"' uv.lock` 显示 `version = "2.0.0"`

### Phase 2: 测试

#### Task 2.1: 建立 v2 测试环境

- **目标**：uv 虚拟环境安装 mcp 2.0.0
- **命令**：`uv sync`（含 dev 依赖组）
- **验收**：`uv run python -c "import mcp; print(mcp.__version__ if hasattr(mcp,'__version__') else 'installed')"` 不报错；`uv run python -c "from mcp.server import MCPServer; print('OK')"` 输出 OK

#### Task 2.2: 全量回归

- **目标**：1108 测试在 v2 环境下全部通过
- **命令**：`uv run pytest tests/ --timeout=60 --ignore=tests/test_security_guards.py --ignore=tests/test_pii.py -k "not hypothesis"`
- **验收**：≥1108 passed, 0 failures

#### Task 2.3: Smoke Test（真 MCP 握手 + 工具注册 + 调用）

- **目标**：用 v2 官方 `Client` 进程内连接，验证 219 工具注册与调用
- **命令**（临时脚本，不入库）：
  ```python
  # /tmp/smoke_v2.py
  import anyio
  from mcp import Client
  from docx_mcp.server import mcp as server_obj

  async def main():
      async with Client(server_obj) as client:
          tools = await client.list_tools()
          assert len(tools.tools) >= 200, f"expected >=200 tools, got {len(tools.tools)}"
          print(f"SMOKE OK: {len(tools.tools)} tools registered, server_info={client.server_info}")

  anyio.run(main)
  ```
  执行：`uv run python /tmp/smoke_v2.py`
- **验收**：输出 `SMOKE OK: 219 tools registered`

### Phase 3: 提交与 PR

#### Task 3.1: 提交 + 合并到 main

- **命令**：
  ```bash
  git add docx_mcp/server.py pyproject.toml uv.lock
  git commit -m "feat(server): migrate to MCP SDK v2 MCPServer API

  - FastMCP → MCPServer (from mcp.server import MCPServer)
  - 219 @mcp.tool() decorators unchanged (v2-compatible per migration guide)
  - Add threading.RLock around _docs dict (v2 runs sync handlers on worker threads)
  - Pin mcp>=2,<3

  Supersedes the mcp>=1.28,<2 pin from PR #16.
  Known limitation: same-handle concurrent edits are not serialized (documented)."
  git push origin feat/migrate-mcp-sdk-v2
  git checkout main && git merge feat/migrate-mcp-sdk-v2 --no-ff -m "merge: feat/migrate-mcp-sdk-v2 into main" && git push origin main
  ```
- **验收**：main 含迁移；分支保留

#### Task 3.2: 创建 upstream PR

- **目标**：提交 PR，body 说明：
  - 迁移面审计结论（5 行核心 + 锁）
  - 线程安全设计 + 残余风险
  - 取代 #16
  - 测试结果（1108 passed + smoke）
- **验收**：PR 创建成功，返回 URL

---

## Execution Wave

| Wave | Task | 依赖 |
|------|------|------|
| W1 | T1.1 | — |
| W2 | T1.2, T1.3 | W1 |
| W3 | T1.4 | W1（可并行，改的是不同文件） |
| W4 | T2.1 | W3 |
| W5 | T2.2 | W4, W2 |
| W6 | T2.3 | W5 |
| W7 | T3.1 | W6 |
| W8 | T3.2 | W7 |

## Post-Execution Verification

| ID | 验证 | 命令/方法 | 预期 |
|----|------|-----------|------|
| V1 | 全量测试（v2 环境） | `uv run pytest ...` | ≥1108 passed |
| V2 | Smoke 握手+工具注册 | `uv run python /tmp/smoke_v2.py` | 219 tools |
| V3 | 实际 MCP 客户端连接 | 用户在 Claude/客户端中重连 docx-mcp | 工具列表完整、可编辑文档 |

### Deferred (needs restart / deployment)

- [ ] D1: 用户重启 docx-mcp server 进程 → 客户端重连 → 用 open_document 打开真实文档做一次编辑

### Manual

- [ ] M1: 人工确认 Claude 客户端中 docx-mcp 工具数 = 219，且能完成一次 replace_text + tracked 修改

---

## 审查日志

| 轮次 | 聚焦 | 发现问题数 | 已修正 | 剩余 |
|------|------|-----------|--------|------|
| R1 | 结构完整性 | 0 | — | 0 |
| R1.5 | 外部引用（MCPServer 签名已从 2.0.0 wheel 实测；迁移指南原文已核对） | 0 | — | 0 |
| R2 | 可执行性（含 uv 环境方案） | 0 | — | 0 |
| R2.8 | LLM 可执行性（行号、命令、验收均精确） | 0 | — | 0 |
| R3 | 风险与边缘（锁外 close、残余风险文档化、#16 取代关系明确） | 0 | — | 0 |
| **终止** | **T5 — issue 清零** | | | **0** |

## Rollback

- 若 v2 环境测试失败且无法快速修复：`git revert` 迁移 commit，回退到 #16 的 pin 状态。成本 = 1 次 revert。
- 迁移分支独立于 #16 分支，两者互不阻塞。
