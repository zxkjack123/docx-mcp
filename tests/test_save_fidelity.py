"""Regression guard — a plain save must not rewrite document parts.

A zero-edit open+save may only change ZIP container metadata (entry order,
timestamps, compression method). Every part's bytes must survive untouched.
This pins the property measured for #4271 so a future save-path change cannot
silently start rewriting parts.

Scope: zero-edit save only. This says nothing about edit paths, other office
suites re-saving the file, or Word-native rendering.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from docx_mcp import server

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'  # noqa: E501
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Default Extension="png" ContentType="image/png"/>'
    '<Override PartName="/word/document.xml"'
    ' ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'  # noqa: E501
    "</Types>"
)

_TOP_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/officeDocument" Target="word/document.xml"/>'
    "</Relationships>"
)

# Relationships must point only at parts that exist in the same sample, otherwise
# the designed broken-relationship repair rewrites the rels part (see #4271 notes).
_DOC_RELS_IMAGE = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId11" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/image" Target="media/image1.png"/>'
    "</Relationships>"
)

_DOC_RELS_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId10" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/styles" Target="styles.xml"/>'
    "</Relationships>"
)

_PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(64))


def _doc(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_W}" xmlns:r="{_R}">'
        f"<w:body>{body}</w:body></w:document>"
    )


_PARA = '<w:p><w:r><w:t xml:space="preserve">Body text.</w:t></w:r></w:p>'
_TABLE = "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
_TRACKED = (
    "<w:p><w:r><w:t>kept</w:t></w:r>"
    '<w:ins w:id="1" w:author="A" w:date="2026-01-01T00:00:00Z">'
    "<w:r><w:t>ins</w:t></w:r></w:ins>"
    '<w:del w:id="2" w:author="A" w:date="2026-01-01T00:00:00Z">'
    "<w:r><w:delText>del</w:delText></w:r></w:del></w:p>"
)
_DRAWING = (
    "<w:p><w:r><w:t>figure</w:t></w:r>"
    '<w:r><w:drawing><wp:inline xmlns:wp="http://schemas.openxmlformats.org/'
    'drawingml/2006/wordprocessingDrawing"><a:graphic xmlns:a="http://schemas.'
    'openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.'
    'openxmlformats.org/drawingml/2006/picture"><pic:pic xmlns:pic="http://'
    'schemas.openxmlformats.org/drawingml/2006/picture"><pic:blipFill><a:blip '
    'r:embed="rId11"/></pic:blipFill></pic:pic></a:graphicData></a:graphic>'
    "</wp:inline></w:drawing></w:r></w:p>"
)
_SECTIONS = (
    _PARA
    + '<w:p><w:pPr><w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:pPr></w:p>'
    + _PARA
    + '<w:sectPr><w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/></w:sectPr>'
)
_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:styles xmlns:w="{_W}">'
    '<w:style w:type="paragraph" w:styleId="Heading1">'
    '<w:name w:val="heading 1"/></w:style>'
    '<w:style w:type="character" w:styleId="Strong">'
    '<w:name w:val="Strong"/><w:rPr><w:b/></w:rPr></w:style>'
    "</w:styles>"
)
_FOOTNOTES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:footnotes xmlns:w="{_W}">'
    '<w:footnote w:id="1"><w:p><w:r><w:t>note text</w:t></w:r></w:p></w:footnote>'
    "</w:footnotes>"
)
_COMMENTS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:comments xmlns:w="{_W}">'
    '<w:comment w:id="1" w:author="A" w:date="2026-01-01T00:00:00Z" w:initials="A">'
    "<w:p><w:r><w:t>please fix</w:t></w:r></w:p></w:comment></w:comments>"
)

SAMPLES: dict[str, dict[str, str | bytes]] = {
    "text": {"word/document.xml": _doc(_PARA)},
    "table": {"word/document.xml": _doc(_PARA + _TABLE)},
    "tracked": {"word/document.xml": _doc(_TRACKED)},
    "image": {
        "word/document.xml": _doc(_DRAWING),
        "word/media/image1.png": _PNG,
        "word/_rels/document.xml.rels": _DOC_RELS_IMAGE,
    },
    "styles": {
        "word/document.xml": _doc(_PARA),
        "word/styles.xml": _STYLES,
        "word/_rels/document.xml.rels": _DOC_RELS_STYLES,
    },
    "footnotes": {
        "word/document.xml": _doc(_PARA),
        "word/footnotes.xml": _FOOTNOTES,
    },
    "comments": {
        "word/document.xml": _doc(_PARA),
        "word/comments.xml": _COMMENTS,
    },
    "sections": {"word/document.xml": _doc(_SECTIONS)},
}


def _build(path: Path, parts: dict[str, str | bytes]) -> None:
    payload: dict[str, str | bytes] = {
        "[Content_Types].xml": _CONTENT_TYPES,
        "_rels/.rels": _TOP_RELS,
        **parts,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in payload.items():
            zf.writestr(name, data)


def _rewrite_part(
    src: Path,
    dst: Path,
    name: str | None,
    data: str | bytes | None,
    *,
    extra: tuple[str, bytes] | None = None,
) -> None:
    """Copy *src* to *dst*, replacing one member and/or adding one extra member."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for member in zin.namelist():
            zout.writestr(member, data if member == name else zin.read(member))
        if extra is not None:
            zout.writestr(extra[0], extra[1])


def _part_hashes(path: Path) -> dict[str, str]:
    """Map every ZIP member to the SHA-256 of its bytes (container layer ignored)."""
    with zipfile.ZipFile(path) as zf:
        return {name: hashlib.sha256(zf.read(name)).hexdigest() for name in zf.namelist()}


@pytest.mark.parametrize("kind", sorted(SAMPLES))
def test_service_save_preserves_all_parts(tmp_path: Path, kind: str):
    src = tmp_path / f"{kind}.docx"
    out = tmp_path / f"{kind}-saved.docx"
    _build(src, SAMPLES[kind])
    before = _part_hashes(src)

    handle = f"fidelity-{kind}"
    server.open_document(str(src), document_handle=handle)
    try:
        result = json.loads(server.save_document(str(out), document_handle=handle))
    finally:
        server.close_document(document_handle=handle)

    assert result["modified_parts"] == []
    assert _part_hashes(out) == before, "a zero-edit save rewrote part bytes"


@pytest.mark.parametrize("kind", sorted(SAMPLES))
def test_second_save_is_stable(tmp_path: Path, kind: str):
    """Saving an already-saved file again must not drift either."""
    src = tmp_path / f"{kind}.docx"
    first = tmp_path / f"{kind}-1.docx"
    second = tmp_path / f"{kind}-2.docx"
    _build(src, SAMPLES[kind])

    handle = f"fidelity2-{kind}"
    server.open_document(str(src), document_handle=handle)
    try:
        server.save_document(str(first), document_handle=handle)
    finally:
        server.close_document(document_handle=handle)

    server.open_document(str(first), document_handle=handle)
    try:
        server.save_document(str(second), document_handle=handle)
    finally:
        server.close_document(document_handle=handle)

    assert _part_hashes(second) == _part_hashes(src)


def test_part_comparison_detects_a_single_changed_part(tmp_path: Path):
    """The comparison used above must actually distinguish different bytes."""
    a = tmp_path / "a.docx"
    b = tmp_path / "b.docx"
    _build(a, SAMPLES["text"])
    _build(b, SAMPLES["text"])
    # Change one part's content only. Same container, different payload.
    _rewrite_part(a, b, "word/document.xml", _doc(_PARA.replace("Body", "Bady")))

    assert _part_hashes(a) != _part_hashes(b)
    assert _part_hashes(a)["word/document.xml"] != _part_hashes(b)["word/document.xml"]


def test_part_comparison_detects_an_added_part(tmp_path: Path):
    """A save that starts emitting extra parts must not pass unnoticed."""
    a = tmp_path / "add-a.docx"
    b = tmp_path / "add-b.docx"
    _build(a, SAMPLES["text"])
    _build(b, SAMPLES["text"])
    _rewrite_part(a, b, None, None, extra=("word/extra.xml", b"<extra/>"))

    assert set(_part_hashes(a)) != set(_part_hashes(b))


class TestPartFidelity:
    """PM #4271 - save() must report a part-level byte delta, not just marked parts."""

    def test_inplace_zero_edit_reports_empty_part_delta(self, test_docx: Path):
        server.open_document(str(test_docx))
        try:
            result = json.loads(server.save_document())  # in-place: the target exists
        finally:
            server.close_document()
        delta = result["part_byte_delta"]
        assert delta["baseline_source"] == "target_file"
        assert delta["changed"] == []
        assert delta["added"] == []
        assert delta["removed"] == []
        assert delta["marked_but_unchanged"] == []
        assert delta["note"] is None
        assert result["modified_parts"] == []

    def test_single_paragraph_edit_reports_document_xml_only(self, test_docx: Path):
        server.open_document(str(test_docx))
        try:
            server.insert_text("00000004", " x", tracked=False)
            result = json.loads(server.save_document())
        finally:
            server.close_document()
        delta = result["part_byte_delta"]
        assert delta["baseline_source"] == "target_file"
        assert delta["changed"] == ["word/document.xml"]
        assert "word/styles.xml" not in delta["changed"]
        assert not [p for p in delta["changed"] if p.startswith("word/media/")]
        assert delta["added"] == []
        assert delta["removed"] == []
        assert delta["marked_but_unchanged"] == []
        assert result["modified_parts"] == ["word/document.xml"]
        # The anti-misreading sentence is a runtime contract, not prose: deleting it
        # from the note must break this test. Case-insensitive on purpose: the note
        # emphasises NOT, while this assertion pins the presence of the negation.
        assert "not evidence of content loss" in delta["note"].lower()

    def test_new_output_path_reports_no_baseline(self, test_docx: Path, tmp_path: Path):
        out = tmp_path / "brand-new.docx"  # does not exist -> no baseline
        server.open_document(str(test_docx))
        try:
            result = json.loads(server.save_document(str(out)))
        finally:
            server.close_document()
        delta = result["part_byte_delta"]
        assert delta["baseline_source"] is None
        assert delta["changed"] is None
        assert delta["added"] is None
        assert delta["removed"] is None
        assert delta["marked_but_unchanged"] is None
        assert isinstance(delta["note"], str)
        assert delta["note"].startswith("No pre-save baseline")
        assert out.exists() and result["size_bytes"] > 0

    def test_marked_part_without_tree_is_marked_but_unchanged(self, test_docx: Path):
        server.open_document(str(test_docx))
        try:
            # No parsed tree -> the part is never re-serialized, so its bytes stay put.
            server._resolve("")[1]._mark("word/media/image1.png")
            result = json.loads(server.save_document())
        finally:
            server.close_document()
        delta = result["part_byte_delta"]
        assert delta["marked_but_unchanged"] == ["word/media/image1.png"]
        assert "word/media/image1.png" in result["modified_parts"]
        assert delta["changed"] == []

    def test_new_part_is_reported_as_added(self, test_docx: Path):
        server.open_document(str(test_docx))
        try:
            server.add_comment("00000001", "fidelity probe")
            result = json.loads(server.save_document())
        finally:
            server.close_document()
        delta = result["part_byte_delta"]
        assert delta["added"] == ["word/comments.xml"]
        assert "word/comments.xml" not in delta["changed"]
        assert delta["changed"] == [
            "[Content_Types].xml",
            "word/_rels/document.xml.rels",
            "word/document.xml",
        ]
        assert delta["marked_but_unchanged"] == []

    def test_corrupt_target_degrades_to_no_baseline(self, test_docx: Path, tmp_path: Path):
        bad = tmp_path / "corrupt.docx"
        bad.write_bytes(b"not a zip container at all")  # exists, but unreadable as ZIP
        server.open_document(str(test_docx))
        try:
            result = json.loads(server.save_document(str(bad)))
        finally:
            server.close_document()
        delta = result["part_byte_delta"]
        assert delta["baseline_source"] is None and delta["changed"] is None
        assert bad.stat().st_size > 0  # the save still overwrote successfully

    def test_save_as_over_existing_other_docx_reports_removed_and_sanitize_suffix(
        self, test_docx: Path, tmp_path: Path
    ):
        """Save As onto a *different* existing docx.

        Covers the only branch where `removed` can be non-empty (`baseline_source`
        must say `other_existing_target`), and - because this call also passes
        `sanitize_level=1` - the note suffix marking the report as predating the
        sanitizer's rewrite of the same path.
        """
        other = tmp_path / "other.docx"
        _build(other, SAMPLES["comments"])  # has comments.xml; `test_docx` has not
        server.open_document(str(test_docx))
        try:
            result = json.loads(server.save_document(str(other), sanitize_level=1))
        finally:
            server.close_document()
        delta = result["part_byte_delta"]
        assert delta["baseline_source"] == "other_existing_target"
        # Deterministic: every part of `other` except comments.xml also exists in the
        # source fixture's part set, so exactly this one part disappears.
        assert delta["removed"] == ["word/comments.xml"]
        assert "rewritten afterwards by sanitize_level=1" in delta["note"]
        assert "predates" in delta["note"]
        assert result["sanitized"]["level"] == 1
