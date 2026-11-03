"""RED tests — save_document(sanitize_level=...) writes a sanitized document.

The save tool should optionally apply the metadata sanitizer to its own output
so callers do not need a save → reopen → sanitize → close dance.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from docx_mcp import server

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_DC = "http://purl.org/dc/elements/1.1/"
_EP = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'  # noqa: E501
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml"'
    ' ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'  # noqa: E501
    '<Override PartName="/docProps/core.xml"'
    ' ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
    '<Override PartName="/docProps/app.xml"'
    ' ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
    "</Types>"
)

_TOP_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1"'
    ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
    ' Target="word/document.xml"/>'
    '<Relationship Id="rId2"'
    ' Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"'
    ' Target="docProps/core.xml"/>'
    '<Relationship Id="rId3"'
    ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties"'
    ' Target="docProps/app.xml"/>'
    "</Relationships>"
)

_CORE_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    "<cp:coreProperties"
    ' xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
    ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
    "<dc:creator>Alice Smith</dc:creator>"
    "<cp:lastModifiedBy>Bob Jones</cp:lastModifiedBy>"
    "<cp:revision>42</cp:revision>"
    "</cp:coreProperties>"
)

_APP_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
    "<Company>Acme Legal LLP</Company>"
    "</Properties>"
)

_SETTINGS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<w:attachedTemplate r:id="rId1"/>'
    "</w:settings>"
)

_WORD_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1"'
    ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate"'
    ' Target="file:///C:/Users/alice/AppData/Roaming/Microsoft/Templates/Acme.dotx"'
    ' TargetMode="External"/>'
    "</Relationships>"
)

_DOC_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    "<w:document\n"
    '    xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
    "  <w:body>\n"
    '    <w:p w:rsidR="00AB1234" w:rsidRDefault="00AB1234">\n'
    "      <w:r><w:t>Kept text. </w:t></w:r>\n"
    '      <w:ins w:id="1" w:author="Alice Smith" w:date="2026-01-01T00:00:00Z">\n'
    "        <w:r><w:t>inserted</w:t></w:r>\n"
    "      </w:ins>\n"
    "    </w:p>\n"
    "  </w:body>\n"
    "</w:document>"
)


def _j(s: str) -> dict:
    return json.loads(s)


def _build_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _TOP_RELS)
        zf.writestr("word/document.xml", _DOC_XML)
        zf.writestr("docProps/core.xml", _CORE_XML)
        zf.writestr("docProps/app.xml", _APP_XML)
        zf.writestr("word/settings.xml", _SETTINGS_XML)
        zf.writestr("word/_rels/document.xml.rels", _WORD_RELS)


def _part(path: Path, member: str) -> etree._Element:
    with zipfile.ZipFile(path) as zf:
        return etree.fromstring(zf.read(member))


def _open(tmp_path: Path, handle: str = "s1") -> tuple[Path, Path]:
    source = tmp_path / "source.docx"
    out = tmp_path / "out.docx"
    _build_docx(source)
    server.open_document(str(source), document_handle=handle)
    return source, out


@pytest.fixture()
def handle():
    yield "s1"
    server.close_document(document_handle="s1")


class TestSaveDocumentSanitize:
    def test_level3_clears_properties_in_saved_output(self, tmp_path: Path, handle: str):
        source, out = _open(tmp_path, handle)
        result = _j(server.save_document(str(out), document_handle=handle, sanitize_level=3))
        assert result["path"] == str(out)
        core = _part(out, "docProps/core.xml")
        assert core.find(f"{{{_DC}}}creator").text in ("", None)
        assert core.find(f"{{{_CP}}}lastModifiedBy").text in ("", None)
        app = _part(out, "docProps/app.xml")
        assert app.find(f"{{{_EP}}}Company").text in ("", None)
        settings = _part(out, "word/settings.xml")
        assert settings.find(f"{{{_W}}}attachedTemplate") is None
        assert source  # the fixture file is still referenced

    def test_level0_keeps_metadata(self, tmp_path: Path, handle: str):
        _source, out = _open(tmp_path, handle)
        server.save_document(str(out), document_handle=handle)
        core = _part(out, "docProps/core.xml")
        assert core.find(f"{{{_DC}}}creator").text == "Alice Smith"

    def test_level1_removes_revision_ids_only(self, tmp_path: Path, handle: str):
        _source, out = _open(tmp_path, handle)
        server.save_document(str(out), document_handle=handle, sanitize_level=1)
        doc = _part(out, "word/document.xml")
        assert not any(key.endswith("}rsidR") for el in doc.iter() for key in el.attrib)
        core = _part(out, "docProps/core.xml")
        assert core.find(f"{{{_DC}}}creator").text == "Alice Smith"

    def test_level2_redacts_authors(self, tmp_path: Path, handle: str):
        _source, out = _open(tmp_path, handle)
        server.save_document(str(out), document_handle=handle, sanitize_level=2)
        doc = _part(out, "word/document.xml")
        authors = [el.get(f"{{{_W}}}author") for el in doc.iter(f"{{{_W}}}ins")]
        assert authors == ["Anonymous"]

    def test_level2_custom_author_label(self, tmp_path: Path, handle: str):
        _source, out = _open(tmp_path, handle)
        server.save_document(
            str(out),
            document_handle=handle,
            sanitize_level=2,
            redact_authors_as="REDACTED",
        )
        doc = _part(out, "word/document.xml")
        authors = [el.get(f"{{{_W}}}author") for el in doc.iter(f"{{{_W}}}ins")]
        assert authors == ["REDACTED"]

    def test_out_of_range_level_is_rejected(self, tmp_path: Path, handle: str):
        _source, out = _open(tmp_path, handle)
        with pytest.raises(ValueError, match="sanitize_level"):
            server.save_document(str(out), document_handle=handle, sanitize_level=4)
        assert not out.exists()


class TestSaveSanitizePreservesEdits:
    def test_save_edits_survive_sanitize(self, tmp_path: Path, handle: str):
        """Sanitizing must not drop the edits that this same save wrote."""
        _source, out = _open(tmp_path, handle)
        replaced = _j(
            server.find_replace_formatted("Kept text.", "Edited text.", document_handle=handle)
        )
        assert replaced["count"] == 1
        server.save_document(str(out), document_handle=handle, sanitize_level=3)
        with zipfile.ZipFile(out) as zf:
            xml = zf.read("word/document.xml").decode()
        assert "Edited text." in xml
        assert "Kept text." not in xml
        core = _part(out, "docProps/core.xml")
        assert core.find(f"{{{_DC}}}creator").text in ("", None)
