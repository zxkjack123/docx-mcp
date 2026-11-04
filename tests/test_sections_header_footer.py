"""RED tests — get_sections must expose header/footer references and field codes.

The section listing currently reports only page geometry. Downstream consumers
(FormatForge C4 / P3 checks) also need to know which header/footer parts each
section references, whether the section has a different first page, and which
field codes (PAGE / NUMPAGES / SEQ) those parts contain.

Structure under test mirrors the reference S1 sample: three sections where the
first has titlePg plus two header and two footer references (default + first),
the second has one of each, and the final body section has none.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from docx_mcp import server

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/header1.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/header2.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/header3.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/footer1.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
  <Override PartName="/word/footer2.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
  <Override PartName="/word/footer3.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
</Types>"""

_TOP_RELS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{RELS_NS}">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>"""


def _rel(rid: str, kind: str, target: str) -> str:
    return (
        f'  <Relationship Id="{rid}"'
        f' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{kind}"'
        f' Target="{target}"/>'
    )


# Section 0 (first): default + first headers/footers, titlePg set.
_DOC_RELS = "\n".join(
    [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<Relationships xmlns="{RELS_NS}">',
        _rel("rId101", "header", "header1.xml"),
        _rel("rId102", "header", "header2.xml"),
        _rel("rId103", "footer", "footer1.xml"),
        _rel("rId104", "footer", "footer2.xml"),
        _rel("rId105", "header", "header3.xml"),
        _rel("rId106", "footer", "footer3.xml"),
        "</Relationships>",
    ]
)


def _sectpr(index: int) -> str:
    if index == 0:
        return """<w:sectPr>
      <w:headerReference w:type="default" r:id="rId101"/>
      <w:headerReference w:type="first" r:id="rId102"/>
      <w:footerReference w:type="default" r:id="rId103"/>
      <w:footerReference w:type="first" r:id="rId104"/>
      <w:titlePg/>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:bottom="1440"/>
    </w:sectPr>"""
    if index == 1:
        return """<w:sectPr>
      <w:type w:val="nextPage"/>
      <w:headerReference w:type="default" r:id="rId105"/>
      <w:footerReference w:type="default" r:id="rId106"/>
      <w:pgSz w:w="11906" w:h="16838"/>
    </w:sectPr>"""
    return """<w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
    </w:sectPr>"""


_DOCUMENT = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W_NS}" xmlns:w14="{W14_NS}" xmlns:r="{R_NS}">
  <w:body>
    <w:p w14:paraId="00000001" w14:textId="77777777">
      <w:pPr>{_sectpr(0)}</w:pPr>
      <w:r><w:t>Section one</w:t></w:r>
    </w:p>
    <w:p w14:paraId="00000002" w14:textId="77777777">
      <w:pPr>{_sectpr(1)}</w:pPr>
      <w:r><w:t>Section two</w:t></w:r>
    </w:p>
    <w:p w14:paraId="00000003" w14:textId="77777777">
      <w:r><w:t>Section three</w:t></w:r>
    </w:p>
    {_sectpr(2)}
  </w:body>
</w:document>"""


def _part(kind: str, runs: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:{kind} xmlns:w="{W_NS}" xmlns:r="{R_NS}">
  <w:p>{runs}</w:p>
</w:{kind}>"""


def _complex_field(instr: str) -> str:
    """Build a Word complex field: begin / instrText / separate / end."""
    return (
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        f'<w:r><w:instrText xml:space="preserve"> {instr} </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        "<w:r><w:t>1</w:t></w:r>"
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    )


def _simple_field(instr: str) -> str:
    return f'<w:fldSimple w:instr=" {instr} "><w:r><w:t>1</w:t></w:r></w:fldSimple>'


# footer1 carries the page-number fields; header2 carries a SEQ field.
_HEADER1 = _part("hdr", "<w:r><w:t>Report title</w:t></w:r>")
_HEADER2 = _part("hdr", "<w:r><w:t>First page</w:t></w:r>" + _simple_field("SEQ Figure"))
_HEADER3 = _part("hdr", "<w:r><w:t>Section two header</w:t></w:r>")
_FOOTER1 = _part(
    "ftr",
    "<w:r><w:t>Page </w:t></w:r>"
    + _complex_field("PAGE")
    + "<w:r><w:t> of </w:t></w:r>"
    + _complex_field("NUMPAGES"),
)
_FOOTER2 = _part("ftr", "<w:r><w:t>First page footer</w:t></w:r>")
_FOOTER3 = _part("ftr", "<w:r><w:t>Section two footer</w:t></w:r>")


def _build(path: Path, *, rels: str = _DOC_RELS, document: str = _DOCUMENT) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _TOP_RELS)
        zf.writestr("word/document.xml", document)
        zf.writestr("word/_rels/document.xml.rels", rels)
        zf.writestr("word/header1.xml", _HEADER1)
        zf.writestr("word/header2.xml", _HEADER2)
        zf.writestr("word/header3.xml", _HEADER3)
        zf.writestr("word/footer1.xml", _FOOTER1)
        zf.writestr("word/footer2.xml", _FOOTER2)
        zf.writestr("word/footer3.xml", _FOOTER3)


def _j(result: str):
    return json.loads(result)


@pytest.fixture()
def handle(tmp_path: Path):
    path = tmp_path / "ref.docx"
    _build(path)
    server.open_document(str(path), document_handle="hf")
    yield "hf"
    server.close_document(document_handle="hf")


class TestGetSectionsHeaderFooter:
    def test_three_sections_with_reference_counts(self, handle: str):
        sections = _j(server.get_sections(document_handle=handle))
        assert len(sections) == 3

        first = sections[0]
        assert first["titlePg"] is True
        assert first["header_refs"] == 2
        assert first["footer_refs"] == 2

        second = sections[1]
        assert second["titlePg"] is False
        assert second["header_refs"] == 1
        assert second["footer_refs"] == 1

        final = sections[2]
        assert final["titlePg"] is False
        assert final["header_refs"] == 0
        assert final["footer_refs"] == 0

    def test_reference_types_are_reported(self, handle: str):
        sections = _j(server.get_sections(document_handle=handle))
        assert sections[0]["header_ref_types"] == ["default", "first"]
        assert sections[0]["footer_ref_types"] == ["default", "first"]
        assert sections[1]["header_ref_types"] == ["default"]
        assert sections[2]["header_ref_types"] == []

    def test_field_codes_are_collected(self, handle: str):
        sections = _j(server.get_sections(document_handle=handle))
        # footer1 has PAGE + NUMPAGES, header2 has SEQ — all belong to section 0.
        assert sections[0]["fields"] == ["NUMPAGES", "PAGE", "SEQ"]
        assert sections[1]["fields"] == []
        assert sections[2]["fields"] == []

    def test_existing_geometry_keys_are_preserved(self, handle: str):
        sections = _j(server.get_sections(document_handle=handle))
        assert sections[0]["index"] == 0
        assert sections[0]["page_width"] == 11906
        assert sections[0]["page_height"] == 16838
        assert sections[2]["break_type"] == ""
        assert sections[1]["break_type"] == "nextPage"

    def test_listing_is_read_only(self, tmp_path: Path, handle: str):
        """get_sections must not mark any part as modified."""
        server.get_sections(document_handle=handle)
        out = tmp_path / "after.docx"
        result = _j(server.save_document(str(out), document_handle=handle))
        assert result["modified_parts"] == []


class TestGetSectionsHeaderFooterEdgeCases:
    def test_dangling_reference_target_is_tolerated(self, tmp_path: Path):
        """A reference whose target part is missing must not break the listing."""
        path = tmp_path / "dangling.docx"
        # rId103 (the footer that carries PAGE/NUMPAGES) points at a missing part.
        _build(path, rels=_DOC_RELS.replace("footer1.xml", "footer-missing.xml"))
        server.open_document(str(path), document_handle="dangling")
        try:
            sections = _j(server.get_sections(document_handle="dangling"))
        finally:
            server.close_document(document_handle="dangling")
        assert sections[0]["header_refs"] == 2
        assert sections[0]["footer_refs"] == 2
        # The unresolvable footer contributes nothing; SEQ from header2 remains.
        assert sections[0]["fields"] == ["SEQ"]

    def test_reference_without_type_defaults_to_default(self, tmp_path: Path):
        path = tmp_path / "notype.docx"
        document = _DOCUMENT.replace(
            '<w:headerReference w:type="default" r:id="rId101"/>',
            '<w:headerReference r:id="rId101"/>',
        )
        _build(path, document=document)
        server.open_document(str(path), document_handle="notype")
        try:
            sections = _j(server.get_sections(document_handle="notype"))
        finally:
            server.close_document(document_handle="notype")
        assert sections[0]["header_ref_types"] == ["default", "first"]


# ─────────────────────────────────────────────────────────────────────────────
#  Real-document cross-check (POI fixtures shipped in the repository)
# ─────────────────────────────────────────────────────────────────────────────

FIXTURES = Path(__file__).parent / "fixtures"

_W = f"{{{W_NS}}}"
_R = f"{{{R_NS}}}"


def _package_expectations(path: Path) -> tuple[int, int, int, int, set[str]]:
    """Derive section/header/footer/field expectations straight from the ZIP.

    Deliberately does not reuse SectionsMixin so it is an independent oracle.
    """
    with zipfile.ZipFile(path) as zf:
        root = etree.fromstring(zf.read("word/document.xml"))
        rels = {
            rel.get("Id"): rel.get("Target")
            for rel in etree.fromstring(zf.read("word/_rels/document.xml.rels"))
        }
        refs = [*root.iter(f"{_W}headerReference"), *root.iter(f"{_W}footerReference")]
        fields: set[str] = set()
        for ref in refs:
            target = rels.get(ref.get(f"{_R}id"))
            if target is None:
                continue
            try:
                part = etree.fromstring(zf.read(f"word/{target}"))
            except KeyError:
                continue
            for el in part.iter(f"{_W}instrText"):
                tokens = (el.text or "").split()
                if tokens:
                    fields.add(tokens[0].upper())
            for el in part.iter(f"{_W}fldSimple"):
                tokens = (el.get(f"{_W}instr") or "").split()
                if tokens:
                    fields.add(tokens[0].upper())

    return (
        len(list(root.iter(f"{_W}sectPr"))),
        len(list(root.iter(f"{_W}headerReference"))),
        len(list(root.iter(f"{_W}footerReference"))),
        len(list(root.iter(f"{_W}titlePg"))),
        fields,
    )


@pytest.mark.parametrize("name", ["poi_diff_header_footer.docx", "poi_header_footer.docx"])
def test_real_fixture_matches_package_structure(name: str):
    path = FIXTURES / name
    assert path.exists(), f"missing fixture {path}"
    n_sect, n_hdr, n_ftr, n_title, fields = _package_expectations(path)

    server.open_document(str(path), document_handle=f"fx-{name}")
    try:
        sections = _j(server.get_sections(document_handle=f"fx-{name}"))
    finally:
        server.close_document(document_handle=f"fx-{name}")

    assert len(sections) == n_sect
    assert sum(s["header_refs"] for s in sections) == n_hdr
    assert sum(s["footer_refs"] for s in sections) == n_ftr
    assert sum(1 for s in sections if s["titlePg"]) == n_title
    assert set().union(*(set(s["fields"]) for s in sections)) == fields
