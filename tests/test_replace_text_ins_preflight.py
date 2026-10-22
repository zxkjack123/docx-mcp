"""replace_text / delete_text 的 w:ins 交叠预检（2026-10-22 MCP 体检）。

30 天 MCP 工具级统计里 ``docx-mcp_replace_text`` 错误率 **41.9%（13 次失败）**，
全部是 ``Cannot delete text inside an existing w:ins`` —— 报错只给了"不行"，
没给 ``change_id``、没给可调用的修复工具，调用方只能重复试错。

现在要求：预检在**任何 mutation 之前**触发，报错保留可检索子串
``existing w:ins``（向后兼容既有日志/知识库检索），并附带
``change_id`` / author / date 与具体可调用的工具（``accept_change(change_id=...)``）。
"""

from __future__ import annotations

import json

import pytest

from docx_mcp import server


def _j(text: str) -> dict:
    return json.loads(text)


@pytest.fixture()
def corpus(mike_corpus_docx):
    server.open_document(str(mike_corpus_docx))
    return mike_corpus_docx


# ── 1. 预检报错必须可自助 ────────────────────────────────────────────────────


def test_replace_text_reports_change_id_author_and_hint(corpus):
    with pytest.raises(ValueError) as exc:
        server.replace_text(para_id="00000107", find="two hundred", replace="three hundred")

    msg = str(exc.value)
    assert "existing w:ins" in msg, "必须保留可检索子串，避免破坏既有检索/文档"
    assert "change_id=51" in msg, f"缺少冲突修正的 change_id：{msg}"
    assert "Reviewer" in msg, f"缺少作者信息：{msg}"
    assert "accept_change(change_id=51)" in msg, f"缺少可直接调用的修复工具：{msg}"
    assert "00000107" in msg, f"缺少段落定位：{msg}"


def test_untracked_replace_also_preflights_and_leaves_doc_untouched(corpus):
    """tracked=False 走 _apply_untracked_deletion，此前会静默拆掉 w:ins。"""
    with pytest.raises(ValueError, match="existing w:ins"):
        server.replace_text(
            para_id="00000107",
            find="two hundred",
            replace="three hundred",
            tracked=False,
        )
    body = _j(server.get_body_text())["body"]
    assert "two hundred" in body, "预检必须在 mutation 之前，文档不得被改动"
    assert "three hundred" not in body


def test_delete_text_reports_change_id(corpus):
    with pytest.raises(ValueError) as exc:
        server.delete_text(para_id="00000107", text="two hundred")
    msg = str(exc.value)
    assert "existing w:ins" in msg
    assert "change_id=51" in msg


# ── 2. 按报错提示修复后必须能继续 ────────────────────────────────────────────


def test_accept_insertion_then_replace_succeeds(corpus, tmp_path):
    accepted = _j(server.accept_change(change_id=51))
    assert accepted == {"change_id": 51, "action": "accepted", "type": "insertion"}

    res = _j(server.replace_text(para_id="00000107", find="two hundred", replace="three hundred"))
    assert res["type"] == "replacement"
    assert res["ins_id"] is not None

    out = tmp_path / "accept_then_replace.docx"
    server.save_document(str(out))
    server.open_document(str(out))
    body = _j(server.get_body_text())["body"]
    assert "three hundred" in body
    assert "two hundred" not in body


# ── 3. 无 w:ins 的普通替换不受影响（防误伤） ─────────────────────────────────


def test_replace_outside_insertion_unaffected(corpus):
    res = _j(server.replace_text(para_id="00000104", find="twelve months", replace="six months"))
    assert res["type"] == "replacement"
    body = _j(server.get_body_text())["body"]
    assert "six months from commencement" in body


def test_noop_replacement_still_returns_empty_ids(corpus):
    res = _j(
        server.replace_text(
            para_id="00000107", find="dollars per month", replace="dollars per month"
        )
    )
    assert res["del_id"] is None and res["ins_id"] is None
