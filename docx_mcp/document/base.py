"""Base mixin: lifecycle, XML cache, namespace constants, shared helpers."""

from __future__ import annotations

import contextlib
import hashlib
import os
import random
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from lxml import etree

from .errors import DocxMcpError, ErrCode
from .guards import InputGuard

# ── OOXML namespace constants ───────────────────────────────────────────────
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
W15 = "{http://schemas.microsoft.com/office/word/2012/wordml}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
V = "{urn:schemas-microsoft-com:vml}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
RELS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
DC = "{http://purl.org/dc/elements/1.1/}"
DCTERMS = "{http://purl.org/dc/terms/}"
CP = "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}"

NSMAP = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "v": "urn:schemas-microsoft-com:vml",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}

REL_TYPES = {
    "comments": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments",
    "commentsExtended": "http://schemas.microsoft.com/office/2011/relationships/commentsExtended",
    "footnotes": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes",
}

CT_TYPES = {
    "comments": ("application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"),
    "commentsExtended": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml"
    ),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _preserve(t_el: etree._Element, text: str) -> None:
    """Set text on a <w:t> or <w:delText> element with xml:space=preserve."""
    t_el.text = text
    t_el.set(XML_SPACE, "preserve")


class BaseMixin:
    """Lifecycle, XML cache, and shared helpers."""

    _MAX_ZIP_ENTRIES = 10_000
    _MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024  # 500 MB

    def __init__(self, path: str):
        self.source_path = Path(path).resolve()
        self.workdir: Path | None = None
        self._trees: dict[str, etree._Element] = {}
        self._modified: set[str] = set()
        self._binaries: dict[str, bytes] = {}  # zip_path -> bytes for in-memory binary updates

    # ── Open / Close ────────────────────────────────────────────────────────

    def open(self) -> dict:
        """Unpack DOCX and parse XML files. Returns document info."""
        if not self.source_path.exists():
            raise FileNotFoundError(f"File not found: {self.source_path}")
        if self.source_path.suffix.lower() != ".docx":
            raise ValueError(f"Not a .docx file: {self.source_path}")

        self.workdir = Path(tempfile.mkdtemp(prefix="docx_mcp_"))
        try:
            zf_handle = zipfile.ZipFile(self.source_path, "r")
        except zipfile.BadZipFile as exc:
            shutil.rmtree(self.workdir, ignore_errors=True)
            self.workdir = None
            raise DocxMcpError(
                ErrCode.OOXML_INVALID,
                f"Corrupt or invalid DOCX (bad ZIP): {exc}",
                hint="The file may be truncated or not a valid .docx file.",
            ) from exc
        with zf_handle:
            infos = zf_handle.infolist()
            # V3: entry count bomb
            if len(infos) > self._MAX_ZIP_ENTRIES:
                shutil.rmtree(self.workdir, ignore_errors=True)
                self.workdir = None
                raise DocxMcpError(
                    ErrCode.OOXML_INVALID,
                    f"DOCX has {len(infos)} ZIP entries (limit {self._MAX_ZIP_ENTRIES})",
                    hint="This may be a ZIP bomb or a corrupted file.",
                )
            # V3: uncompressed size bomb
            total_uncompressed = sum(i.file_size for i in infos)
            if total_uncompressed > self._MAX_UNCOMPRESSED_BYTES:
                shutil.rmtree(self.workdir, ignore_errors=True)
                self.workdir = None
                raise DocxMcpError(
                    ErrCode.OOXML_INVALID,
                    f"DOCX uncompressed size {total_uncompressed} bytes exceeds "
                    f"limit of {self._MAX_UNCOMPRESSED_BYTES} bytes",
                    hint="This may be a ZIP bomb.",
                )
            # V1: ZipSlip — validate every entry before extraction
            for member in zf_handle.namelist():
                dest = (self.workdir / member).resolve()
                if not dest.is_relative_to(self.workdir.resolve()):
                    shutil.rmtree(self.workdir, ignore_errors=True)
                    self.workdir = None
                    raise DocxMcpError(
                        ErrCode.UNSAFE_PATH,
                        f"ZipSlip: entry escapes workdir: {member!r}",
                        hint="The DOCX contains a malicious ZIP entry name.",
                    )
            zf_handle.extractall(self.workdir)

        # Discover and parse XML files
        xml_files = ["[Content_Types].xml"]
        # Core properties
        core = self.workdir / "docProps" / "core.xml"
        if core.exists():
            xml_files.append("docProps/core.xml")
        word_dir = self.workdir / "word"
        if word_dir.exists():
            for name in [
                "document.xml",
                "footnotes.xml",
                "endnotes.xml",
                "comments.xml",
                "commentsExtended.xml",
                "styles.xml",
                "numbering.xml",
                "settings.xml",
            ]:
                if (word_dir / name).exists():
                    xml_files.append(f"word/{name}")
            # Headers and footers
            for f in word_dir.iterdir():
                if f.name.startswith(("header", "footer")) and f.suffix == ".xml":
                    xml_files.append(f"word/{f.name}")

        # Relationship files
        rels_dir = word_dir / "_rels"
        if rels_dir.exists():
            for f in rels_dir.iterdir():
                if f.suffix == ".rels":
                    xml_files.append(f"word/_rels/{f.name}")

        for rel_path in xml_files:
            full_path = self.workdir / rel_path
            if full_path.exists():
                try:
                    parser = etree.XMLParser(
                        remove_blank_text=False,
                        resolve_entities=False,
                        no_network=True,
                        huge_tree=False,
                    )
                    tree = etree.parse(str(full_path), parser)
                    self._trees[rel_path] = tree.getroot()
                except etree.XMLSyntaxError:
                    pass

        return self.get_info()

    def close(self) -> None:
        """Clean up temporary files."""
        if self.workdir and self.workdir.exists():
            shutil.rmtree(self.workdir, ignore_errors=True)
        self._trees.clear()
        self._modified.clear()
        self._binaries.clear()
        self.workdir = None

    # ── Save ────────────────────────────────────────────────────────────────

    def save(self, output_path: str | None = None, *, backup: bool = True) -> dict:
        """Write modified XML back to files and repack into a .docx.

        Returns a dict with ``path``, ``size_bytes``, ``modified_parts``,
        ``repairs``, ``warnings`` (plus ``backup`` when a backup was made) and
        ``part_byte_delta``. ``modified_parts`` lists the parts the editor marked
        as dirty -- it is not a byte-level difference. ``part_byte_delta``
        reports a part-by-part byte comparison at the part layer against the
        pre-save target file on disk (container-layer metadata such as ZIP entry
        order and timestamps is not compared); when the caller rewrites that path
        after the save (for example ``save_document(sanitize_level>0)`` runs
        ``sanitize_metadata`` on it), the report predates that rewrite and does
        not describe the final file.
        """
        if self.workdir is None:
            raise RuntimeError("No document is open")

        if output_path is not None:
            output_path = str(InputGuard.output_path(output_path))

        output = Path(output_path) if output_path else self.source_path

        # Backup existing file before overwriting
        backup_path = self._backup_if_exists(output) if backup else None

        # PM #4271 -- part-level baseline. MUST be read here: after the backup and
        # before the write-back loop below. Reading it after the repack would
        # compare the output file with itself and always report zero differences.
        # Best-effort: reporting must never turn an already-successful save into an
        # exception, so any failure here degrades to "no baseline".
        try:
            same_target = Path(output).resolve() == Path(self.source_path).resolve()
            parts_before = self._digest_parts_from_zip(output) if output.exists() else None
        except Exception:  # noqa: BLE001 - best-effort reporting, degrade to no baseline
            same_target = True
            parts_before = None

        # Auto-repair known corruption patterns
        repairs = self._pre_save_repair()

        # Lightweight validation — warn about issues that can't be auto-repaired
        warnings = self._post_repair_warnings()

        # Serialize modified trees
        for rel_path in self._modified:
            tree = self._trees.get(rel_path)
            if tree is None:
                continue
            fp = self.workdir / rel_path
            fp.parent.mkdir(parents=True, exist_ok=True)
            et = etree.ElementTree(tree)
            et.write(
                str(fp),
                xml_declaration=True,
                encoding="UTF-8",
                standalone=True,
            )

        # Write in-memory binary overrides (e.g. replaced images)
        for zip_path, data in self._binaries.items():
            fp = self.workdir / zip_path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_bytes(data)
        self._binaries.clear()

        # Repack
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(self.workdir):
                for fname in files:
                    fpath = Path(root) / fname
                    arcname = str(fpath.relative_to(self.workdir))
                    zf.write(fpath, arcname)

        modified = sorted(self._modified)
        self._modified.clear()

        # PM #4271 -- container/part byte comparison. `modified_parts` lists parts the
        # editor marked dirty; it is NOT a byte-level difference. Best-effort: any
        # failure degrades to a null report plus a note, never to an exception (the
        # output file has already been written at this point).
        try:
            parts_after = self._digest_parts_from_dir(self.workdir)
            part_byte_delta: dict[str, object] = {
                "baseline_source": None,
                "changed": None,
                "added": None,
                "removed": None,
                "marked_but_unchanged": None,
                "note": (
                    f"No pre-save baseline for {output}: the target file did not exist "
                    "(or was not a readable DOCX container), so part bytes were not "
                    "compared. This is informational only -- it is not a content-loss "
                    "verdict. For a content-level comparison use compare_documents or "
                    "diff_to_text."
                ),
            }
            if parts_before is None:
                pass  # keep the "no baseline" note set above
            elif parts_after is None:
                part_byte_delta["note"] = (
                    "Part-level byte comparison could not be computed: the post-save "
                    "working tree could not be hashed, so no delta is reported. This is "
                    "informational only -- it is not a content-loss verdict."
                )
            else:
                changed = sorted(
                    name
                    for name in parts_before
                    if name in parts_after and parts_before[name] != parts_after[name]
                )
                added = sorted(set(parts_after) - set(parts_before))
                removed = sorted(set(parts_before) - set(parts_after))
                part_byte_delta.update(
                    baseline_source=("target_file" if same_target else "other_existing_target"),
                    changed=changed,
                    added=added,
                    removed=removed,
                    marked_but_unchanged=sorted(set(modified) - set(changed) - set(added)),
                )
                if changed or added or removed:
                    part_byte_delta["note"] = (
                        f"Part bytes differ from the pre-save target file: changed="
                        f"{len(changed)}, added={len(added)}, removed={len(removed)} of "
                        f"{len(parts_before)} part(s). Detected byte changes are NOT "
                        "evidence of content loss -- re-serialization alone rewrites "
                        "bytes without changing document content."
                    )
                else:
                    part_byte_delta["note"] = None
        except Exception as exc:  # noqa: BLE001 - reporting is best-effort, never fatal
            part_byte_delta = {
                "baseline_source": None,
                "changed": None,
                "added": None,
                "removed": None,
                "marked_but_unchanged": None,
                "note": (
                    f"Part-level byte comparison failed ({type(exc).__name__}); no byte "
                    "delta is reported. This is informational only -- it is not a "
                    "content-loss verdict."
                ),
            }

        result = {
            "path": str(output),
            "size_bytes": output.stat().st_size,
            "modified_parts": modified,
            "repairs": repairs,
            "warnings": warnings,
            "part_byte_delta": part_byte_delta,
        }
        if backup_path:
            result["backup"] = str(backup_path)
        return result

    @staticmethod
    def _sha256_stream(handle) -> str:
        """SHA-256 of an open binary stream, read in 1 MiB chunks (never buffered whole)."""
        digest = hashlib.sha256()
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _digest_parts_from_zip(path: Path) -> dict[str, str] | None:
        """Map every file member of a ZIP container to the SHA-256 of its bytes.

        Directory entries are skipped; member names are normalised to forward
        slashes. Returns ``None`` when *path* is not a readable ZIP container --
        callers MUST treat that as "no baseline", never as "zero differences".
        """
        parts: dict[str, str] = {}
        try:
            with zipfile.ZipFile(path) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    with zf.open(info.filename) as fh:
                        parts[info.filename.replace("\\", "/")] = BaseMixin._sha256_stream(fh)
        except (zipfile.BadZipFile, OSError, NotImplementedError):
            # NOTE: zipfile.BadZipFile is NOT an OSError subclass, and an unsupported
            # compression method raises NotImplementedError -- both must be listed.
            return None
        return parts

    @staticmethod
    def _digest_parts_from_dir(root: Path) -> dict[str, str] | None:
        """Map every file under *root* to the SHA-256 of its bytes (streamed).

        Returns ``None`` when the tree cannot be hashed completely -- a partial
        mapping would silently under-report the delta, so callers MUST degrade.
        """
        parts: dict[str, str] = {}
        try:
            for dirpath, _dirnames, filenames in os.walk(root):
                for name in filenames:
                    fp = Path(dirpath) / name
                    with open(fp, "rb") as fh:
                        key = str(fp.relative_to(root)).replace(os.sep, "/")
                        parts[key] = BaseMixin._sha256_stream(fh)
        except (OSError, NotImplementedError):
            # Partial results are worse than no result: degrade instead of guessing.
            return None
        return parts

    @staticmethod
    def _backup_if_exists(output: Path) -> Path | None:
        """Create a backup of output if it already exists.

        Uses .bak, .bak2, .bak3, ... to avoid overwriting previous backups.
        """
        if not output.exists():
            return None
        # Find next available backup name
        bak = output.with_suffix(output.suffix + ".bak")
        if not bak.exists():
            shutil.copy2(output, bak)
            return bak
        n = 2
        while True:
            bak = output.parent / (output.stem + output.suffix + f".bak{n}")
            if not bak.exists():
                break
            n += 1
        shutil.copy2(output, bak)
        return bak

    # ── Pre-save auto-repair ─────────────────────────────────────────────────

    # Word's structural notes are not referenced by body text but must exist.
    _STRUCTURAL_NOTE_TYPES = frozenset({"separator", "continuationSeparator", "continuationNotice"})

    @classmethod
    def _is_structural_note(cls, note: etree._Element) -> bool:
        """Return whether a note uses a known Word structural-note type."""
        return note.get(f"{W}type") in cls._STRUCTURAL_NOTE_TYPES

    def _settings_note_ids(self, kind: str) -> set[str]:
        """Return note ids pinned by word/settings.xml note properties."""
        settings = self._tree("word/settings.xml")
        if settings is None:
            return set()
        return {
            n.get(f"{W}id")
            for pr in settings.iter(f"{W}{kind}Pr")
            for n in pr.findall(f"{W}{kind}")
        }

    def _pre_save_repair(self) -> dict:
        """Auto-repair known corruption patterns before writing.

        Returns a dict of repair counts (all zero if nothing was fixed).
        """
        repairs: dict[str, int] = {
            "orphan_footnotes_removed": 0,
            "orphan_endnotes_removed": 0,
            "paraids_deduplicated": 0,
            "broken_rels_removed": 0,
        }

        doc = self._tree("word/document.xml")
        if doc is None:
            return repairs

        body = doc.find(f"{W}body")

        # ── Orphan footnotes ──────────────────────────────────────────────
        fn_tree = self._tree("word/footnotes.xml")
        if fn_tree is not None and body is not None:
            ref_ids = {int(ref.get(f"{W}id", "0")) for ref in body.iter(f"{W}footnoteReference")}
            pinned = self._settings_note_ids("footnote")
            for fn in list(fn_tree.findall(f"{W}footnote")):
                fn_id = int(fn.get(f"{W}id", "0"))
                if (
                    fn_id >= 2
                    and fn_id not in ref_ids
                    and not self._is_structural_note(fn)
                    and str(fn_id) not in pinned
                ):
                    fn_tree.remove(fn)
                    repairs["orphan_footnotes_removed"] += 1
            if repairs["orphan_footnotes_removed"]:
                self._mark("word/footnotes.xml")

        # ── Orphan endnotes ───────────────────────────────────────────────
        en_tree = self._tree("word/endnotes.xml")
        if en_tree is not None and body is not None:
            ref_ids = {int(ref.get(f"{W}id", "0")) for ref in body.iter(f"{W}endnoteReference")}
            pinned = self._settings_note_ids("endnote")
            for en in list(en_tree.findall(f"{W}endnote")):
                en_id = int(en.get(f"{W}id", "0"))
                if (
                    en_id not in (0, -1)
                    and en_id not in ref_ids
                    and not self._is_structural_note(en)
                    and str(en_id) not in pinned
                ):
                    en_tree.remove(en)
                    repairs["orphan_endnotes_removed"] += 1
            if repairs["orphan_endnotes_removed"]:
                self._mark("word/endnotes.xml")

        # ── Duplicate paraIds ─────────────────────────────────────────────
        seen: dict[str, bool] = {}
        for rel_path, tree in self._trees.items():
            if not rel_path.endswith(".xml"):
                continue
            for elem in tree.iter():
                pid = elem.get(f"{W14}paraId")
                if pid is None:
                    continue
                if pid in seen:
                    elem.set(f"{W14}paraId", self._new_para_id())
                    repairs["paraids_deduplicated"] += 1
                    self._mark(rel_path)
                else:
                    seen[pid] = True

        # ── Broken internal relationships ─────────────────────────────────
        rels_tree = self._tree("word/_rels/document.xml.rels")
        if rels_tree is not None:
            for rel in list(rels_tree.findall(f"{RELS}Relationship")):
                if rel.get("TargetMode") == "External":
                    continue
                target = rel.get("Target", "")
                if target and not (self.workdir / "word" / target).exists():
                    rels_tree.remove(rel)
                    repairs["broken_rels_removed"] += 1
            if repairs["broken_rels_removed"]:
                self._mark("word/_rels/document.xml.rels")

        return repairs

    def _post_repair_warnings(self) -> list[str]:
        """Check for issues that can't be auto-repaired. Returns warning strings."""
        warnings: list[str] = []
        doc = self._tree("word/document.xml")
        if doc is None:
            return warnings

        # Heading level skips
        headings = self._find_headings(doc)
        prev = 0
        for h in headings:
            if h["level"] > prev + 1 and prev > 0:
                warnings.append(
                    f"Heading level skip: H{prev} -> H{h['level']} at '{h['text'][:50]}'"
                )
            prev = h["level"]

        # Unpaired bookmarks
        starts = {e.get(f"{W}id") for e in doc.iter(f"{W}bookmarkStart") if e.get(f"{W}id")}
        ends = {e.get(f"{W}id") for e in doc.iter(f"{W}bookmarkEnd") if e.get(f"{W}id")}
        unpaired = len(starts - ends) + len(ends - starts)
        if unpaired:
            warnings.append(f"{unpaired} unpaired bookmark(s)")

        # Inconsistent table columns
        for idx, tbl in enumerate(doc.iter(f"{W}tbl")):
            counts = [len(tr.findall(f"{W}tc")) for tr in tbl.findall(f"{W}tr")]
            if counts and len(set(counts)) > 1:
                warnings.append(f"Table {idx + 1} has inconsistent column counts: {counts}")

        # Artifact markers (DRAFT, TODO, FIXME, XXX)
        for marker in ("DRAFT", "TODO", "FIXME", "XXX"):
            hits = self.search_text(marker)
            for hit in hits:
                warnings.append(f"{marker} marker in {hit['source']}: '{hit['text'][:60]}'")

        return warnings

    # ── Private helpers ─────────────────────────────────────────────────────

    def _tree(self, rel_path: str) -> etree._Element | None:
        return self._trees.get(rel_path)

    def _require(self, rel_path: str) -> etree._Element:
        t = self._tree(rel_path)
        if t is None:
            raise RuntimeError(f"{rel_path} not found — is a document open?")
        return t

    def _mark(self, rel_path: str) -> None:
        self._modified.add(rel_path)

    @staticmethod
    def _text(element: etree._Element) -> str:
        """Concatenate all <w:t> text descendants."""
        return "".join(t.text for t in element.iter(f"{W}t") if t.text)

    @staticmethod
    def _real_footnotes(fn_root: etree._Element) -> list[etree._Element]:
        """Return footnote elements excluding separators (id 0 and -1)."""
        return [f for f in fn_root.findall(f"{W}footnote") if f.get(f"{W}id") not in ("0", "-1")]

    def _find_para(self, root: etree._Element, para_id: str) -> etree._Element | None:
        for p in root.iter(f"{W}p"):
            if p.get(f"{W14}paraId") == para_id:
                return p
        return None

    def _new_para_id(self) -> str:
        """Generate a unique paraId (8 hex digits, < 0x80000000)."""
        existing: set[str] = set()
        for tree in self._trees.values():
            for el in tree.iter():
                pid = el.get(f"{W14}paraId")
                if pid:
                    existing.add(pid.upper())
        while True:
            val = random.randint(1, 0x7FFFFFFF)
            pid = f"{val:08X}"
            if pid not in existing:
                return pid

    @staticmethod
    def _next_markup_id(doc: etree._Element) -> int:
        """Next available ID for ins/del/comment/bookmark markup."""
        max_id = 0
        for tag in (
            f"{W}ins",
            f"{W}del",
            f"{W}commentRangeStart",
            f"{W}commentRangeEnd",
            f"{W}bookmarkStart",
            f"{W}bookmarkEnd",
        ):
            for el in doc.iter(tag):
                eid = el.get(f"{W}id")
                if eid:
                    with contextlib.suppress(ValueError):
                        max_id = max(max_id, int(eid))
        return max_id + 1

    @staticmethod
    def _next_comment_id(cm_tree: etree._Element) -> int:
        max_id = -1
        for c in cm_tree.findall(f"{W}comment"):
            cid = c.get(f"{W}id")
            if cid:
                with contextlib.suppress(ValueError):
                    max_id = max(max_id, int(cid))
        return max_id + 1

    @staticmethod
    def _make_run(text: str, rpr_bytes: bytes | None) -> etree._Element:
        """Build a <w:r> element with optional copied rPr."""
        r = etree.Element(f"{W}r")
        if rpr_bytes:
            r.append(etree.fromstring(rpr_bytes))
        t = etree.SubElement(r, f"{W}t")
        _preserve(t, text)
        return r

    def _create_comments_part(self) -> etree._Element:
        """Create word/comments.xml and register it in rels + content types."""
        root = etree.Element(
            f"{W}comments",
            nsmap={"w": NSMAP["w"], "w14": NSMAP["w14"], "r": NSMAP["r"]},
        )
        self._trees["word/comments.xml"] = root

        # Write file so it exists on disk
        fp = self.workdir / "word" / "comments.xml"
        fp.parent.mkdir(parents=True, exist_ok=True)
        etree.ElementTree(root).write(str(fp), xml_declaration=True, encoding="UTF-8")

        # Content type
        ct = self._tree("[Content_Types].xml")
        if ct is not None:
            existing = {e.get("PartName") for e in ct.findall(f"{CT}Override")}
            if "/word/comments.xml" not in existing:
                ov = etree.SubElement(ct, f"{CT}Override")
                ov.set("PartName", "/word/comments.xml")
                ov.set("ContentType", CT_TYPES["comments"])
                self._mark("[Content_Types].xml")

        # Relationship
        rels = self._tree("word/_rels/document.xml.rels")
        if rels is not None:
            existing_targets = {r.get("Target") for r in rels.findall(f"{RELS}Relationship")}
            if "comments.xml" not in existing_targets:
                max_rid = 0
                for r in rels.findall(f"{RELS}Relationship"):
                    rid = r.get("Id", "")
                    if rid.startswith("rId"):
                        with contextlib.suppress(ValueError):
                            max_rid = max(max_rid, int(rid[3:]))
                rel = etree.SubElement(rels, f"{RELS}Relationship")
                rel.set("Id", f"rId{max_rid + 1}")
                rel.set("Type", REL_TYPES["comments"])
                rel.set("Target", "comments.xml")
                self._mark("word/_rels/document.xml.rels")

        self._mark("word/comments.xml")
        return root
