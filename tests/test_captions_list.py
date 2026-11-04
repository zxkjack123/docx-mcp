"""RED tests — docx_list_captions: read-only listing of figure/table captions.

The new tool must report every caption paragraph (literal numbering included)
with its base number, any sub-figure suffix and whether the number comes from a
SEQ field. It must not insert, modify or judge anything.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from lxml import etree

from docx_mcp import server

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_W = f"{{{W_NS}}}"
FIXTURES = Path(__file__).parent / "fixtures"

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

_TOP_RELS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{RELS_NS}">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
  <Relationship Id="rId2"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
    Target="styles.xml"/>
</Relationships>"""

_STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W_NS}">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Caption">
    <w:name w:val="caption"/>
  </w:style>
</w:styles>"""


def _para(
    text: str, *, style: str | None = None, para_id: str | None = None, body: str = ""
) -> str:
    pid = f' w14:paraId="{para_id}"' if para_id else ""
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'{body}<w:p{pid}>{ppr}<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def _complex_seq(instr: str) -> str:
    return (
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        f'<w:r><w:instrText xml:space="preserve"> {instr} </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        "<w:r><w:t>1</w:t></w:r>"
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    )


def _seq_caption_para(label: str, description: str, para_id: str) -> str:
    """Caption whose number comes from a SEQ field (cached result "1")."""
    instr = f"SEQ {label} " + "\\* ARABIC"
    return (
        f'<w:p w14:paraId="{para_id}">'
        '<w:pPr><w:pStyle w:val="Caption"/></w:pPr>'
        f'<w:r><w:t xml:space="preserve">{label} </w:t></w:r>'
        f"{_complex_seq(instr)}"
        f'<w:r><w:t xml:space="preserve">: {description}</w:t></w:r>'
        "</w:p>"
    )


def _build(path: Path, paragraphs: list[str]) -> None:
    body = "\n".join(paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W_NS}" xmlns:w14="{W14_NS}">'
        f"<w:body>{body}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _TOP_RELS)
        zf.writestr("word/document.xml", document)
        zf.writestr("word/styles.xml", _STYLES)


def _j(result) -> list | dict:
    return json.loads(result)


@pytest.fixture()
def caption_doc(tmp_path: Path):
    """Seventeen literal captions, mirroring the reference S1 shape."""
    texts = [f"表 2-{i}: 数据表 {i}" for i in range(1, 9)]
    texts += [f"图 1-{i}: 示意图 {i}" for i in range(1, 8)]
    texts += ["表 A-1: 附录表", "表 B-1: 另一个附录表"]
    paras = [_para(f"正文段落 {i}", para_id=f"{100 + i:08d}") for i in range(3)]
    paras += [_para(t, style="Caption", para_id=f"{200 + i:08d}") for i, t in enumerate(texts)]
    path = tmp_path / "s1like.docx"
    _build(path, paras)
    server.open_document(str(path), document_handle="caps")
    yield "caps", texts
    server.close_document(document_handle="caps")


class TestListCaptions:
    def test_all_literal_captions_are_listed(self, caption_doc):
        handle, texts = caption_doc
        caps = _j(server.docx_list_captions(document_handle=handle))
        assert len(caps) == len(texts) == 17

    def test_literal_numbers_are_not_seq_fields(self, caption_doc):
        handle, _ = caption_doc
        caps = _j(server.docx_list_captions(document_handle=handle))
        assert all(c["seq_field_present"] is False for c in caps)

    def test_letter_based_numbers_are_extracted(self, caption_doc):
        handle, _ = caption_doc
        caps = _j(server.docx_list_captions(document_handle=handle))
        bases = {c["number_base"] for c in caps}
        assert {"A-1", "B-1"} <= bases
        appendix = [c for c in caps if c["number_base"] == "A-1"]
        assert len(appendix) == 1
        assert appendix[0]["kind"] == "table"
        assert appendix[0]["sub_suffix"] is None

    def test_kind_separates_tables_from_figures(self, caption_doc):
        handle, _ = caption_doc
        caps = _j(server.docx_list_captions(document_handle=handle))
        kinds = [c["kind"] for c in caps]
        assert kinds.count("table") == 10
        assert kinds.count("figure") == 7

    def test_document_order_is_preserved(self, caption_doc):
        handle, _ = caption_doc
        caps = _j(server.docx_list_captions(document_handle=handle))
        assert caps[0]["text"].startswith("表 2-1")
        assert caps[-1]["text"].startswith("表 B-1")
        ids = [c["para_id"] for c in caps]
        assert all(pid for pid in ids)

    def test_listing_is_read_only(self, caption_doc, tmp_path: Path):
        handle, _ = caption_doc
        server.docx_list_captions(document_handle=handle)
        out = tmp_path / "after.docx"
        result = _j(server.save_document(str(out), document_handle=handle))
        assert result["modified_parts"] == []


class TestListCaptionsSubFigures:
    def test_sub_suffix_from_document_style_numbering(self, tmp_path: Path):
        """S2-style: one base number with several sub-figure suffixes."""
        paras = [
            _para(f"表 3-{i}: 表 {i}", style="Caption", para_id=f"{300 + i:08d}")
            for i in range(1, 37)
        ]
        paras += [
            _para(f"图 10-5{c}: 子图 {c}", style="Caption", para_id=f"{400 + i:08d}")
            for i, c in enumerate("abcde")
        ]
        paras += [
            _para(f"图 2-{i}: 图 {i}", style="Caption", para_id=f"{500 + i:08d}")
            for i in range(1, 24)
        ]
        path = tmp_path / "s2like.docx"
        _build(path, paras)
        server.open_document(str(path), document_handle="s2")
        try:
            caps = _j(server.docx_list_captions(document_handle="s2"))
        finally:
            server.close_document(document_handle="s2")

        assert len(caps) == 64
        assert sum(1 for c in caps if c["kind"] == "table") == 36
        assert sum(1 for c in caps if c["kind"] == "figure") == 28
        subs = {c["sub_suffix"] for c in caps if c["number_base"] == "10-5"}
        assert subs >= {"b", "c", "d", "e"}

    def test_parenthesised_sub_suffix(self, tmp_path: Path):
        path = tmp_path / "sub.docx"
        _build(
            path,
            [_para("图 7-2(b): 子图 b", style="Caption", para_id="00000010")],
        )
        server.open_document(str(path), document_handle="sub")
        try:
            caps = _j(server.docx_list_captions(document_handle="sub"))
        finally:
            server.close_document(document_handle="sub")
        assert caps[0]["number_base"] == "7-2"
        assert caps[0]["sub_suffix"] == "b"


class TestListCaptionsSeqFields:
    def test_complex_seq_field_is_reported(self, tmp_path: Path):
        path = tmp_path / "seq.docx"
        _build(path, [_seq_caption_para("Figure", "first figure", "00000021")])
        server.open_document(str(path), document_handle="seq")
        try:
            caps = _j(server.docx_list_captions(document_handle="seq"))
        finally:
            server.close_document(document_handle="seq")
        assert len(caps) == 1
        assert caps[0]["seq_field_present"] is True
        assert caps[0]["kind"] == "figure"

    def test_simple_seq_field_is_reported(self, tmp_path: Path):
        path = tmp_path / "seqsimple.docx"
        para = (
            '<w:p w14:paraId="00000022"><w:pPr><w:pStyle w:val="Caption"/></w:pPr>'
            '<w:r><w:t xml:space="preserve">Table </w:t></w:r>'
            '<w:fldSimple w:instr=" SEQ Table \\* ARABIC "><w:r><w:t>3</w:t></w:r></w:fldSimple>'
            "</w:p>"
        )
        _build(path, [para])
        server.open_document(str(path), document_handle="seq2")
        try:
            caps = _j(server.docx_list_captions(document_handle="seq2"))
        finally:
            server.close_document(document_handle="seq2")
        assert len(caps) == 1
        assert caps[0]["seq_field_present"] is True
        assert caps[0]["number_base"] == "3"


class TestListCaptionsDetection:
    def test_body_text_mentioning_a_label_is_not_a_caption(self, tmp_path: Path):
        path = tmp_path / "body.docx"
        _build(
            path,
            [
                _para("详见 图 1-1 的说明。", para_id="00000031"),
                _para("图 1-1: 真正的题注", style="Caption", para_id="00000032"),
                _para("图 如下所示", para_id="00000033"),
            ],
        )
        server.open_document(str(path), document_handle="body")
        try:
            caps = _j(server.docx_list_captions(document_handle="body"))
        finally:
            server.close_document(document_handle="body")
        assert len(caps) == 1
        assert caps[0]["para_id"] == "00000032"
        assert caps[0]["detected_by"] == ["label", "style"]

    def test_label_only_caption_without_style_is_detected(self, tmp_path: Path):
        path = tmp_path / "nostyle.docx"
        _build(path, [_para("表 5-2: 无样式题注", para_id="00000041")])
        server.open_document(str(path), document_handle="nostyle")
        try:
            caps = _j(server.docx_list_captions(document_handle="nostyle"))
        finally:
            server.close_document(document_handle="nostyle")
        assert len(caps) == 1
        assert caps[0]["detected_by"] == ["label"]
        assert caps[0]["kind"] == "table"
        assert caps[0]["number_base"] == "5-2"

    def test_caption_style_without_label_is_still_listed(self, tmp_path: Path):
        path = tmp_path / "styleonly.docx"
        _build(path, [_para("5.1 Overview", style="Caption", para_id="00000051")])
        server.open_document(str(path), document_handle="styleonly")
        try:
            caps = _j(server.docx_list_captions(document_handle="styleonly"))
        finally:
            server.close_document(document_handle="styleonly")
        assert len(caps) == 1
        assert caps[0]["detected_by"] == ["style"]
        assert caps[0]["number_base"] == "5.1"
        assert caps[0]["kind"] is None


class TestListCaptionsRealFixture:
    def test_pandoc_fixture(self):
        path = FIXTURES / "pandoc_table_captions.docx"
        assert path.exists()
        with zipfile.ZipFile(path) as zf:
            root = etree.fromstring(zf.read("word/document.xml"))
        styled = [
            p
            for p in root.iter(f"{_W}p")
            if (p.find(f"{_W}pPr/{_W}pStyle") is not None)
            and (p.find(f"{_W}pPr/{_W}pStyle").get(f"{_W}val") or "").lower() == "caption"
        ]

        server.open_document(str(path), document_handle="pandoc-caps")
        try:
            caps = _j(server.docx_list_captions(document_handle="pandoc-caps"))
        finally:
            server.close_document(document_handle="pandoc-caps")

        assert len(caps) == len(styled)
        assert len(caps) >= 1
        assert all(c["seq_field_present"] is False for c in caps)
        assert all(c["number_base"] is not None for c in caps)
        assert any(c["kind"] == "table" for c in caps)


class TestListCaptionsHandleRouting:
    """The tool name (docx_list_captions) differs from the document method
    (list_captions), so routing is checked here rather than through the shared
    CASES table."""

    def test_routes_to_the_selected_handle(self, monkeypatch):
        a, b = Mock(), Mock()
        b.list_captions.return_value = [{"kind": "table"}]
        monkeypatch.setattr(server, "_docs", {"A": a, "B": b})
        monkeypatch.setattr(server, "_REQUIRE_HANDLE", True)
        assert json.loads(server.docx_list_captions(document_handle="B")) == [{"kind": "table"}]
        b.list_captions.assert_called_once()
        assert not a.mock_calls
        with pytest.raises(RuntimeError, match="'C'"):
            server.docx_list_captions(document_handle="C")

    def test_requires_a_handle_in_singleton_mode(self, monkeypatch):
        monkeypatch.setattr(server, "_REQUIRE_HANDLE", True)
        with pytest.raises(RuntimeError, match="document_handle is required"):
            server.docx_list_captions()

    def test_default_slot_used_when_handle_not_required(self, monkeypatch):
        doc = Mock()
        doc.list_captions.return_value = []
        monkeypatch.setattr(server, "_docs", {server._DEFAULT_HANDLE: doc})
        monkeypatch.setattr(server, "_REQUIRE_HANDLE", False)
        assert json.loads(server.docx_list_captions()) == []
        assert json.loads(server.docx_list_captions(document_handle="")) == []
