"""Caption mixin: insert and list figure/table captions."""

from __future__ import annotations

import re

from lxml import etree

from .base import W14, XML_SPACE, W

# Caption labels mapped to a coarse kind. Chinese and English forms both appear
# in the wild; the lookup is done on the lower-cased label.
_LABEL_KIND = {"表": "table", "图": "figure", "table": "table", "figure": "figure"}

# Number shapes seen in captions: "5", "10-5", "5.1", "A-1", "AB-12", "10-5b".
_SEP = r"[.\-\u2010-\u2015]"
# A base is either digits with an optional letter prefix ("10", "A1"), or bare
# letters followed by at least one separator group ("A-1") — never bare letters.
_NUM_RE = rf"(?:[A-Za-z]*\d+(?:{_SEP}[A-Za-z]*\d+)*|[A-Za-z]+(?:{_SEP}[A-Za-z]*\d+)+)"
_SUB_RE = r"(?:\s*\((?P<paren>[a-zA-Z])\)|(?P<bare>[a-zA-Z])(?![a-zA-Z]))?"

# `表 10-5b`, `图 10-5(b)`, `Table 5.1: ...`, `Figure A-1`
_LABEL_NUMBER_RE = re.compile(
    rf"^\s*(?P<label>表|图|Table|Figure)\s*(?P<num>{_NUM_RE}){_SUB_RE}",
    re.IGNORECASE,
)

# Same number shape without a label: used for Caption-styled paragraphs whose
# text does not start with a recognised label.
_NUMBER_RE = re.compile(rf"^\s*(?P<num>{_NUM_RE}){_SUB_RE}")


class CaptionMixin:
    def insert_caption(self, after_para_id: str, text: str, label: str = "Figure") -> dict:
        doc = self._tree("word/document.xml")

        target = self._find_para(doc, after_para_id)
        if target is None:
            raise ValueError(f"Paragraph '{after_para_id}' not found")

        existing_captions = [
            p
            for p in doc.iter(f"{W}p")
            if (
                p.find(f"{W}pPr/{W}pStyle") is not None
                and p.find(f"{W}pPr/{W}pStyle").get(f"{W}val", "").lower() == "caption"
            )
        ]
        seq_num = len(existing_captions) + 1

        new_pid = self._new_para_id()

        new_para = etree.Element(f"{W}p")
        new_para.set(f"{W14}paraId", new_pid)
        new_para.set(f"{W14}textId", "77777777")

        ppr = etree.SubElement(new_para, f"{W}pPr")
        pstyle = etree.SubElement(ppr, f"{W}pStyle")
        pstyle.set(f"{W}val", "Caption")

        run = etree.SubElement(new_para, f"{W}r")
        t = etree.SubElement(run, f"{W}t")
        caption_text = f"{label} {seq_num}: {text}"
        t.text = caption_text
        t.set(XML_SPACE, "preserve")

        parent = target.getparent()
        idx = list(parent).index(target)
        parent.insert(idx + 1, new_para)

        self._mark("word/document.xml")

        return {
            "para_id": new_pid,
            "label": label,
            "seq_num": seq_num,
            "text": text,
        }

    # ── Read-only caption listing ────────────────────────────────────────────

    def list_captions(self) -> list[dict]:
        """Return every figure/table caption paragraph, in document order.

        A paragraph counts as a caption when its text starts with a recognised
        label followed by a number (``表`` / ``图`` / ``Table`` / ``Figure``), or
        when it carries the ``Caption`` paragraph style. Captions whose number is
        literal text and captions whose number comes from a SEQ field are both
        reported; ``seq_field_present`` tells them apart.

        Each record has: ``para_id``, ``kind`` ("table"/"figure" when a label was
        recognised, else None), ``label``, ``number_base`` (e.g. "10-5", "A-1"),
        ``sub_suffix`` (e.g. "b", from ``10-5b`` or ``10-5(b)``), ``seq_field_present``,
        ``detected_by`` ("label" and/or "style") and ``text``.

        Read-only: marks no part as modified, and makes no compliance judgement.
        """
        doc = self._require("word/document.xml")
        records = []
        for para in doc.iter(f"{W}p"):
            record = self._caption_record(para)
            if record is not None:
                records.append(record)
        return records

    def _caption_record(self, para) -> dict | None:
        """Build one caption record, or None when the paragraph is not a caption."""
        text = self._text(para)
        styled = self._is_caption_styled(para)
        label_match = _LABEL_NUMBER_RE.match(text)
        if label_match is None and not styled:
            return None

        label = label_match.group("label") if label_match is not None else None
        number_match = label_match if label_match is not None else _NUMBER_RE.match(text)
        number_base = number_match.group("num") if number_match is not None else None
        sub_suffix = None
        if number_match is not None:
            sub_suffix = number_match.group("paren") or number_match.group("bare")

        detected_by = []
        if label_match is not None:
            detected_by.append("label")
        if styled:
            detected_by.append("style")

        return {
            "para_id": para.get(f"{W14}paraId"),
            "kind": _LABEL_KIND.get(label.lower()) if label else None,
            "label": label,
            "number_base": number_base,
            "sub_suffix": sub_suffix,
            "seq_field_present": self._has_seq_field(para),
            "detected_by": detected_by,
            "text": text,
        }

    @staticmethod
    def _is_caption_styled(para) -> bool:
        pstyle = para.find(f"{W}pPr/{W}pStyle")
        return pstyle is not None and (pstyle.get(f"{W}val") or "").lower() == "caption"

    @staticmethod
    def _has_seq_field(para) -> bool:
        """True when the paragraph holds a SEQ field (complex or fldSimple)."""
        for instr in para.iter(f"{W}instrText"):
            tokens = (instr.text or "").split()
            if tokens and tokens[0].upper() == "SEQ":
                return True
        for fld in para.iter(f"{W}fldSimple"):
            tokens = (fld.get(f"{W}instr") or "").split()
            if tokens and tokens[0].upper() == "SEQ":
                return True
        return False
