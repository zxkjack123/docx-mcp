# save(): part-level byte delta + round-trip boundary statement (#T-4271)

Implements the second branch of the #4271 acceptance criterion — a conclusive
write-up plus a save-time change report — and goal (c), the boundary statement
in the tool description and README. Root-cause localisation was deliberately
**out of scope** (see `## 边界`).

## 结论

> 基于 2026-11-02/11-03 两轮调查（17 样本 / 278 部件 / 部件级 0 差异）+ n=1 WPS 外部重存样本 + 本轮告警实现：四类损失在本服务零编辑保存路径未复现；编辑路径缺 pre-edit baseline，根因不可判定。

This paragraph is reproduced verbatim in `README.md` (section *Save round-trip
fidelity*); `grep -F` over both files returns exactly one line each.

## 实现

`save()` returns a seventh key, `part_byte_delta`. The existing six keys keep
their names, types and semantics.

| Field | Meaning |
|---|---|
| `baseline_source` | `"target_file"` (target is this document's own source path) / `"other_existing_target"` (target is a different file that already existed) / `null` (no readable pre-save target) |
| `changed` | Parts present both before and after whose bytes differ |
| `added` | Parts present only after the save |
| `removed` | Parts present only before the save |
| `marked_but_unchanged` | Parts the editor marked dirty whose bytes did not move |
| `note` | Summary, or the reason no comparison was possible |

**Baseline point.** The baseline is read after `_backup_if_exists()` and before
the write-back loop. Reading it after the repack would compare the output file
with itself and always report zero differences.

**Baseline identity.** The baseline is the *pre-save contents of the target
file*: `save()` answers "how did the container I am writing to change", not
"how did this document change since it was opened".

**Degradation.** With no readable target — a new output path, a file that is not
a DOCX container, an unsupported compression method — the four set fields and
`baseline_source` are `null`, never `[]`. An empty list would assert "compared,
and nothing changed", which is a different claim. The `note` is actionable: it
points at `compare_documents` / `diff_to_text` for content-level work.

**Best-effort reporting.** Both the baseline capture and the comparison are
wrapped, and both digest helpers return `None` rather than partial data. A
reporting failure can never turn an already-written save into an exception; it
degrades to a note.

## 证据

Measured in this task (each backed by an executable assertion in
`tests/test_save_fidelity.py::TestPartFidelity`, 7 new cases):

| Case | Observed |
|---|---|
| Zero-edit in-place save | all four sets empty, `note` is `None`, `baseline_source == "target_file"` |
| One paragraph edited | `changed == ["word/document.xml"]` only — `word/styles.xml` and `media/*` untouched |
| Brand-new output path | every field `null`, `note` starts with `No pre-save baseline` |
| A marked part with no parsed tree (`word/media/image1.png`) | reported in `marked_but_unchanged`, bytes unmoved |
| A newly created part (`add_comment`) | `added == ["word/comments.xml"]` |
| A non-ZIP target | degrades to no-baseline, and the save still overwrites successfully |
| Save As over a different, existing docx | `baseline_source == "other_existing_target"`, `removed == ["word/comments.xml"]` |

Suite state: `tests/test_save_fidelity.py` 25 passed; full suite **1713 passed,
17 skipped**, coverage **92.01%** (gate 88).

Anti-vacuity, each run by mutating the implementation and then restoring it:

- Flipping one expected value turns exactly that test red.
- Deleting the anti-misreading sentence from the note turns the edit case red —
  the disclaimer is a runtime contract, not decoration.
- Forcing `baseline_source` to `"target_file"` turns the Save-As case red.
- Raising inside the report block leaves the save successful, the file a valid
  zip, and the failure recorded in `note`.

Earlier investigation (carried over, not re-measured here): two bounded rounds
over 17 samples / 278 parts found zero part-level differences on the zero-edit
save path; the four originally reported losses did not reproduce, and appeared
only in a single externally re-saved sample.

## 连带修正

`README.md`'s *Footnotes & Endnotes* paragraph listed only two of the four
`_pre_save_repair` classes. It now names all four, adding `paraids_deduplicated`
and `broken_rels_removed`. **This gap predates this task and was not introduced
by it** — it is corrected here only because this change already edits that
paragraph's section. It is flagged in the commit message rather than bundled
silently. Names match `docx_mcp/document/base.py` literally.

## 与既有能力分工

| Capability | Answers | Does not answer |
|---|---|---|
| `part_byte_delta` (this change) | which parts differ byte-for-byte from the pre-save target | whether content was lost |
| `generate_change_summary` | what changed in the document, from tracked changes | whether bytes were rewritten |
| `compare_documents` / `diff_to_text` | paragraph-text differences between two files | byte-level package differences |

Neither implies the other: byte differences are not evidence of content loss,
and a clean byte comparison is not evidence that the content is correct.

## sanitize 交互

`save_document(sanitize_level>0)` calls `sanitize_metadata`, which rewrites the
same path after `save()` has returned. `part_byte_delta` therefore describes the
**pre-sanitize** state. `save_document` appends a suffix to `note` saying so:

> The on-disk file was rewritten afterwards by sanitize_level=N; this report
> predates that rewrite and does not describe the final file.

The suffix is appended even when the note was `None` (an empty delta), because
in that situation the file really was rewritten. This affects only
`save_document`; `scrub_pii` and the `sanitize_metadata` tool do not route
through `save()` and carry no such report.

## 非目标

- No root-cause localisation, and no root-cause claim.
- `_mark()`, `_pre_save_repair()`, `_post_repair_warnings()` and
  `_backup_if_exists()` behaviour is unchanged.
- `sanitize_metadata()` itself, `protection.py` and the `scrub_pii` path are
  untouched.
- The existing 18 guard-rail tests and the 5 `modified_parts` assertions are
  unmodified.
- No fidelity information is written into `warnings`.
- No new third-party dependency.

## 边界

Two layers, only one of which is informative:

- **Part layer** — the bytes of each part. This is what `part_byte_delta`
  compares.
- **Container layer** — ZIP entry order, timestamps and compression method.
  These can differ on every repack and are not compared.

The report is a measurement, not a verdict. `modified_parts` lists the parts the
editor marked dirty and is not a byte-level difference.

Scope of the underlying investigation: it covers the **zero-edit save path
within this service only**. It does not cover edited documents, other office
suites re-saving the file, or Word-native rendering. Because the originally
reported losses did not reproduce and no pre-edit baseline exists, the
responsible mechanism is **not determined** — hence `根因不可判定` above rather
than a causal claim.
