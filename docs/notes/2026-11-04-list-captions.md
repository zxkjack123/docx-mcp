# docx_list_captions: read-only caption listing (#5206)

New MCP tool `docx_list_captions(document_handle="")` returning every figure/table
caption paragraph in document order. Each record carries `para_id`, `kind`
(`"table"` / `"figure"` / `null`), `label`, `number_base` (e.g. `"10-5"`, `"A-1"`,
`"5.1"`), `sub_suffix` (e.g. `"b"`, from `10-5b` or `10-5(b)`), `seq_field_present`,
`detected_by` (`"label"` and/or `"style"`) and `text`.

A paragraph is treated as a caption when its text starts with a recognised label
(`表` / `图` / `Table` / `Figure`) followed by a number, **or** when it carries the
`Caption` paragraph style. This is what makes literal, non-SEQ captions visible —
the property the card asks for. SEQ detection covers both complex fields
(`w:instrText`) and `w:fldSimple`; the number cached in the text is reported in
both cases, with `seq_field_present` telling them apart. The method is read-only:
it marks no part as modified and makes no compliance judgement.

## Capability audit (hard prerequisite from the card)

Before implementing, the existing candidate tools were audited so the boundary is
explicit rather than assumed:

| Tool | Writes? | What it actually reports | Why it is not this API |
|---|---|---|---|
| `generate_list_of_figures` | **yes** — inserts a List-of-Figures field block (`toc.py::generate_tof` → `_insert_toc_block`, which marks `word/document.xml`) | entry count of inserted entries | it *generates* a table of contents; it does not return a caption inventory, and its `_collect_captions` only matches Caption-styled paragraphs whose text starts with `Figure` |
| `generate_list_of_tables` | **yes** — same, with the `Table` prefix | same | same |
| `list_fields` | no | raw field inventory: every field code with its cached value | no notion of table vs figure, no base number, no sub-figure suffix |
| `list_bookmarks` | no | bookmark inventory | bookmarks are unrelated to captions |
| `get_sections` | no | section geometry, header/footer references and field codes (#5205) | per-section layout, not per-caption |
| `insert_caption` (`captions.py`) | **yes** | writes one literal caption paragraph | write-only; `captions.py` had no reading path at all |

Boundary in one line: `generate_list_of_*` **produce** a table of contents and depend
on SEQ numbering; `docx_list_captions` **reads** the captions that already exist,
including literal ones without SEQ. The two do not overlap.

## Evidence

RED 17 failed (all `module 'docx_mcp.server' has no attribute 'docx_list_captions'`,
`/tmp/opencode/5206-red.log`, same test revision as the final GREEN), GREEN 17 passed,
`pytest tests/ -q -k captions` 33 passed, full suite 1706 passed / 17 skipped,
coverage 92.06% against the plan's 88% gate, ruff check and format clean. Two mutations
were run: forcing `sub_suffix` to `None` failed exactly the two sub-figure tests, and
forcing `seq_field_present` to `False` failed exactly the two SEQ tests. Independent
acceptance re-ran everything with different mutations. Live check over the MCP HTTP
transport after a service restart: `tools/list` returns 220 tools (219 + this one),
`docx_list_captions` exists with only the optional `document_handle`, and the shipped
`pandoc_table_captions.docx` fixture yields one record
(`kind=table`, `number_base=5.1`, `seq_field_present=false`) — `/tmp/opencode/5206/live.json`.

## Boundaries and known issues

- The card's acceptance criteria name external reference samples (`S1`, `S2`) that are
  not present in this repository, so those literal files were not opened. The asserted
  shapes — 17 literal captions including `表 A-1`/`表 B-1` with `seq_field_present false`,
  and one base number carrying several child suffixes — are reproduced by synthetic
  fixtures in `tests/test_captions_list.py`, plus a real-fixture cross-check against
  `tests/fixtures/pandoc_table_captions.docx` whose expected count is derived from the
  ZIP rather than hard-coded.
- Detection is text- and style-based, so a body paragraph that begins with a label and
  a number (`表 1 列出了…`) is reported as a caption. A label at the start without a
  number (e.g. `图 如下所示`) is not. `detected_by` makes the evidence for each record
  visible so callers can filter.
- `sub_suffix` is reported exactly as found; it is not case-normalised.
- The tool name `docx_list_captions` is the one the card specifies. It differs from the
  repository's usual prefix-free tool naming, and it also differs from the underlying
  method name (`list_captions`), so its handle routing is covered by dedicated tests in
  `tests/test_captions_list.py` rather than by the shared `CASES` table, which assumes
  tool name == method name.
- `pyproject.toml` sets `fail_under = 100` while CI uses 88; a bare `pytest --cov`
  therefore fails on the repository baseline. Pre-existing, not introduced here.
