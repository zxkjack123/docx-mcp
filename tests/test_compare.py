"""
RED tests — Gap 3: Document comparison → tracked changes output.

compare_documents(base_path, revised_path, output_path="") diffs two DOCX
files and returns a single document where differences are expressed as Word
tracked changes (w:ins / w:del), ready for legal review in Word/LibreOffice.

Paragraph-level diff algorithm:
  - Paragraphs present in revised but absent from base → wrapped in w:ins
  - Paragraphs present in base but absent from revised → re-inserted with w:del
  - Paragraphs present in both but with modified text → word-level del+ins

The output document is written to *output_path* (auto-generated if empty)
and the path is returned in the JSON result.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from docx_mcp import server


def _j(s: str) -> dict:
    return json.loads(s)


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    """Write a minimal DOCX whose body contains one <w:p> per string."""
    paras = ""
    for i, text in enumerate(paragraphs):
        para_id = f"CC{i:06d}"
        paras += (
            f'    <w:p w14:paraId="{para_id}" w14:textId="77777777">\n'
            f'      <w:r><w:t xml:space="preserve">{text}</w:t></w:r>\n'
            f"    </w:p>\n"
        )
    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<w:document\n"
        '    xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"\n'
        '    xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml">\n'
        "  <w:body>\n" + paras + "  </w:body>\n</w:document>"
    )
    ct = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'  # noqa: E501
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml"'
        ' ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'  # noqa: E501
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1"'
        ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
        ' Target="word/document.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", ct)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", doc_xml)


def _write_docx_rich(path: Path, body_xml: str) -> None:
    """Write a DOCX whose body is the supplied raw XML (for non-text structures)."""
    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<w:document\n"
        '    xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"\n'
        '    xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"\n'
        '    xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml">\n'
        "  <w:body>\n" + body_xml + "  </w:body>\n</w:document>"
    )
    ct = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'  # noqa: E501
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml"'
        ' ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'  # noqa: E501
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1"'
        ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
        ' Target="word/document.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", ct)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", doc_xml)


def _get_doc_root(path: str | Path) -> etree._Element:
    with zipfile.ZipFile(path) as zf:
        return etree.fromstring(zf.read("word/document.xml"))


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = lambda tag: f"{{{W_NS}}}{tag}"  # noqa: E731


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCompareDocuments:
    # ── Identical documents ───────────────────────────────────────────────────

    def test_identical_documents_produce_no_tracked_changes(self, tmp_path: Path):
        """Two identical documents produce a result with no w:ins or w:del."""
        base = tmp_path / "base.docx"
        revised = tmp_path / "revised.docx"
        out = tmp_path / "out.docx"
        _write_docx(base, ["This is paragraph one.", "This is paragraph two."])
        _write_docx(revised, ["This is paragraph one.", "This is paragraph two."])
        _j(server.compare_documents(str(base), str(revised), str(out)))
        root = _get_doc_root(out)
        assert list(root.iter(W("ins"))) == []
        assert list(root.iter(W("del"))) == []

    # ── Added paragraph ───────────────────────────────────────────────────────

    def test_added_paragraph_wrapped_in_ins(self, tmp_path: Path):
        """A paragraph present in revised but not in base is wrapped in w:ins."""
        base = tmp_path / "base.docx"
        revised = tmp_path / "revised.docx"
        out = tmp_path / "out.docx"
        _write_docx(base, ["First paragraph.", "Third paragraph."])
        _write_docx(revised, ["First paragraph.", "Second paragraph NEW.", "Third paragraph."])
        _j(server.compare_documents(str(base), str(revised), str(out)))
        root = _get_doc_root(out)
        ins_els = list(root.iter(W("ins")))
        assert len(ins_els) >= 1
        ins_texts = "".join(t.text or "" for ins in ins_els for t in ins.iter(W("t")))
        assert "Second paragraph NEW" in ins_texts

    # ── Deleted paragraph ─────────────────────────────────────────────────────

    def test_deleted_paragraph_wrapped_in_del(self, tmp_path: Path):
        """A paragraph present in base but absent from revised is wrapped in w:del."""
        base = tmp_path / "base.docx"
        revised = tmp_path / "revised.docx"
        out = tmp_path / "out.docx"
        _write_docx(base, ["First paragraph.", "REMOVED PARAGRAPH.", "Third paragraph."])
        _write_docx(revised, ["First paragraph.", "Third paragraph."])
        _j(server.compare_documents(str(base), str(revised), str(out)))
        root = _get_doc_root(out)
        del_els = list(root.iter(W("del")))
        assert len(del_els) >= 1
        del_texts = "".join(dt.text or "" for del_el in del_els for dt in del_el.iter(W("delText")))
        assert "REMOVED PARAGRAPH" in del_texts

    # ── Modified paragraph (word-level diff) ──────────────────────────────────

    def test_modified_paragraph_uses_word_level_diff(self, tmp_path: Path):
        """
        A paragraph changed between base and revised gets word-level del+ins:
        only the changed word is marked, not the entire paragraph.
        """
        base = tmp_path / "base.docx"
        revised = tmp_path / "revised.docx"
        out = tmp_path / "out.docx"
        _write_docx(base, ["The payment is due within thirty days."])
        _write_docx(revised, ["The payment is due within 30 days."])
        _j(server.compare_documents(str(base), str(revised), str(out)))
        root = _get_doc_root(out)
        del_texts = "".join(dt.text or "" for dt in root.iter(W("delText")))
        ins_texts = "".join(t.text or "" for ins in root.iter(W("ins")) for t in ins.iter(W("t")))
        assert "thirty" in del_texts
        assert "30" in ins_texts
        # "The payment is due within" and "days." are NOT tracked
        assert "The payment" not in del_texts
        assert "days." not in del_texts

    # ── Multiple changes ──────────────────────────────────────────────────────

    def test_multiple_changes_all_tracked(self, tmp_path: Path):
        """Mix of added, deleted, and modified paragraphs all appear correctly."""
        base = tmp_path / "base.docx"
        revised = tmp_path / "revised.docx"
        out = tmp_path / "out.docx"
        _write_docx(
            base,
            [
                "Unchanged first paragraph.",
                "This paragraph will be deleted.",
                "This paragraph will be modified.",
            ],
        )
        _write_docx(
            revised,
            [
                "Unchanged first paragraph.",
                "This paragraph will be changed.",
                "Brand new paragraph added.",
            ],
        )
        _j(server.compare_documents(str(base), str(revised), str(out)))
        root = _get_doc_root(out)
        del_els = list(root.iter(W("del")))
        ins_els = list(root.iter(W("ins")))
        assert len(del_els) >= 1
        assert len(ins_els) >= 1

    # ── Output path and result ────────────────────────────────────────────────

    def test_result_contains_output_path(self, tmp_path: Path):
        """The JSON result includes the output file path."""
        base = tmp_path / "base.docx"
        revised = tmp_path / "revised.docx"
        out = tmp_path / "out.docx"
        _write_docx(base, ["Hello."])
        _write_docx(revised, ["Hello."])
        result = _j(server.compare_documents(str(base), str(revised), str(out)))
        assert "path" in result
        assert Path(result["path"]).exists()

    def test_auto_output_path_when_empty(self, tmp_path: Path):
        """compare_documents auto-generates output path when none is provided."""
        base = tmp_path / "base.docx"
        revised = tmp_path / "revised.docx"
        _write_docx(base, ["Hello."])
        _write_docx(revised, ["Hello world."])
        result = _j(server.compare_documents(str(base), str(revised), ""))
        assert "path" in result
        assert Path(result["path"]).exists()

    # ── Non-text structures: fail closed instead of silently dropping them ────

    def test_rejects_table_in_base(self, tmp_path: Path):
        """A table would be dropped by the text-only diff, so the call must fail."""
        base = tmp_path / "base.docx"
        revised = tmp_path / "revised.docx"
        out = tmp_path / "out.docx"
        _write_docx_rich(
            base,
            "    <w:p><w:r><w:t>Before table.</w:t></w:r></w:p>\n"
            "    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>cell</w:t></w:r></w:p>"
            "</w:tc></w:tr></w:tbl>\n",
        )
        _write_docx(revised, ["Before table."])
        with pytest.raises(ValueError, match="table"):
            server.compare_documents(str(base), str(revised), str(out))
        assert not out.exists(), "no half-baked diff may be written"

    def test_rejects_inline_drawing_in_revised(self, tmp_path: Path):
        """An inline image cannot be represented by the text diff."""
        base = tmp_path / "base.docx"
        revised = tmp_path / "revised.docx"
        out = tmp_path / "out.docx"
        _write_docx(base, ["Figure follows."])
        _write_docx_rich(
            revised,
            "    <w:p><w:r><w:t>Figure follows.</w:t></w:r><w:r><w:drawing/></w:r></w:p>\n",
        )
        with pytest.raises(ValueError, match="drawing|image"):
            server.compare_documents(str(base), str(revised), str(out))
        assert not out.exists()

    def test_rejects_equation_in_base(self, tmp_path: Path):
        """OMML equations are dropped by the text diff, so refuse them."""
        base = tmp_path / "base.docx"
        revised = tmp_path / "revised.docx"
        out = tmp_path / "out.docx"
        _write_docx_rich(
            base,
            "    <w:p><m:oMath><m:r><m:t>E=mc^2</m:t></m:r></m:oMath></w:p>\n",
        )
        _write_docx(revised, ["E=mc^2"])
        with pytest.raises(ValueError, match="equation"):
            server.compare_documents(str(base), str(revised), str(out))
        assert not out.exists()

    def test_rejection_names_the_offending_file(self, tmp_path: Path):
        """The error should say which input carries the unsupported structure."""
        base = tmp_path / "base.docx"
        revised = tmp_path / "revised.docx"
        out = tmp_path / "out.docx"
        _write_docx(base, ["Only text."])
        _write_docx_rich(
            revised,
            "    <w:p><w:r><w:drawing/></w:r></w:p>\n",
        )
        with pytest.raises(ValueError, match="revised"):
            server.compare_documents(str(base), str(revised), str(out))
