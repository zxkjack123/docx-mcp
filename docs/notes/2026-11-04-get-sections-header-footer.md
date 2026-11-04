# get_sections: header/footer references and field codes (#5205)

`get_sections` now reports, per section, six additional read-only keys alongside the
existing page geometry:

| Key | Meaning |
|---|---|
| `header_refs` / `footer_refs` | number of `w:headerReference` / `w:footerReference` elements in that section's `w:sectPr` |
| `header_ref_types` / `footer_ref_types` | sorted `w:type` values (`default`, `first`, `even`); a reference with no type counts as `default` |
| `titlePg` | `True` when the section sets `w:titlePg` (different first page) |
| `fields` | sorted, de-duplicated field instruction names (PAGE, NUMPAGES, SEQ, …) found in the header/footer parts that section references, aggregated per section |

Relationship targets are resolved through `word/_rels/document.xml.rels`, so a section
reports the parts it actually points at. A reference whose target is missing or
unresolvable contributes nothing and does not raise; missing parts are tolerated rather
than reported as an error.

The implementation extends the existing `get_sections` only. No new tool was added — the
tool count is unchanged at 219 and no `docx_list_sections` exists. The method is
read-only: it marks no part as modified, and it makes no compliance judgement.

Evidence: RED 7 failed / 2 passed (`/tmp/opencode/5205-red.log`, all new-field lookups
raising `KeyError`), GREEN 9 passed, `pytest tests/ -q -k sections` 23 passed, full suite
1689 passed / 17 skipped, coverage 92.02% against the plan's 88% gate, ruff check and
format clean. Disabling field collection with a mutation fails 2 tests. Acceptance was
re-run independently with different mutations. A live check over the MCP HTTP transport
(service restarted, `open_document` + `get_sections`) returned three sections with
`titlePg=True`, `header_refs=2` and `fields=[NUMPAGES, PAGE, SEQ]` for the first
(`/tmp/opencode/5205/live.json`).

Evidence boundary: the card's acceptance criteria name an external reference sample
(`DocxDocument('<S1>')`, `DocxDocument('<S2>')`) that is not present in this repository,
so those literal files were not opened. The asserted structure — three sections, first
with `titlePg` and two header plus two footer references — is reproduced by synthetic
fixtures in `tests/test_sections_header_footer.py`, and the counts are additionally
cross-checked against the two shipped POI fixtures (`poi_header_footer.docx`,
`poi_diff_header_footer.docx`) by deriving the expected numbers straight from the ZIP.
`fields` covers `w:instrText` and `w:fldSimple` instructions; other field representations
are not scanned. `header_refs`/`footer_refs` count reference elements, so a reference
marked `TargetMode="External"` is counted while resolving to no part.
