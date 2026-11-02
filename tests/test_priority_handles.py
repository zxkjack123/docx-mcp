"""Handle routing regression tests for the priority singleton tools."""

import json
import zipfile
from unittest.mock import Mock

import pytest

from docx_mcp import server

CT = """<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>"""  # noqa: E501
RELS = """<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>"""  # noqa: E501
DRELS = """<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>"""  # noqa: E501
STYLES = """<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style><w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/></w:style></w:styles>"""  # noqa: E501


def doc(body):
    return f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'


CASES = [
    ("convert_to_pdf", {"output_path": "out.pdf"}),
    ("sanitize_metadata", {"output_path": "clean.docx"}),
    ("find_replace_formatted", {"find": "old", "replace": "new"}),
    ("get_document_outline", {}),
    ("accept_all_changes", {}),
    ("reject_all_changes", {}),
]


@pytest.mark.parametrize("name,kwargs", CASES)
def test_priority_handle_isolation(monkeypatch, name, kwargs):
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
def test_priority_required_handle(monkeypatch, name, kwargs):
    monkeypatch.setattr(server, "_REQUIRE_HANDLE", True)
    with pytest.raises(RuntimeError, match="document_handle is required"):
        getattr(server, name)(**kwargs)


@pytest.mark.parametrize("name,kwargs", CASES)
def test_priority_legacy_default(monkeypatch, name, kwargs):
    doc = Mock()
    getattr(doc, name).return_value = {"selected": "default"}
    monkeypatch.setattr(server, "_docs", {server._DEFAULT_HANDLE: doc})
    monkeypatch.setattr(server, "_REQUIRE_HANDLE", False)
    assert json.loads(getattr(server, name)(**kwargs)) == {"selected": "default"}
    assert json.loads(getattr(server, name)(**kwargs, document_handle="")) == {
        "selected": "default"
    }


def test_real_document_isolation(tmp_path, monkeypatch):

    monkeypatch.setattr(server, "_docs", {})
    monkeypatch.setattr(server, "_REQUIRE_HANDLE", True)
    for handle in ("A", "B"):
        path = tmp_path / f"{handle}.docx"
        body = (
            f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            f"<w:r><w:t>{handle}</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>old</w:t></w:r></w:p>"
        )
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("[Content_Types].xml", CT)
            archive.writestr("_rels/.rels", RELS)
            archive.writestr("word/_rels/document.xml.rels", DRELS)
            archive.writestr("word/styles.xml", STYLES)
            archive.writestr("word/document.xml", doc(body))
        server.open_document(str(path), document_handle=handle)
    try:
        result = json.loads(server.find_replace_formatted("old", "new", document_handle="B"))
        assert result["count"] == 1
        assert json.loads(server.get_document_outline(document_handle="A"))[0]["text"] == "A"
        assert json.loads(server.get_document_outline(document_handle="B"))[0]["text"] == "B"
        # A still contains old, whereas B no longer does.
        assert (
            json.loads(server.find_replace_formatted("old", "check", document_handle="A"))["count"]
            == 1
        )
        assert (
            json.loads(server.find_replace_formatted("old", "check", document_handle="B"))["count"]
            == 0
        )
    finally:
        for opened in server._docs.values():
            opened.close()
