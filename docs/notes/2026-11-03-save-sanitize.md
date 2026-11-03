# Save-time metadata sanitization (#2119)

`save_document` accepts `sanitize_level` (0-3, default 0) and `redact_authors_as` (default "Anonymous"). Level 0 saves verbatim; 1 strips revision-save ids; 2 also redacts tracked-change authors; 3 also clears document properties (creator, last modified by, company, attached template). Values outside 0-3 raise ValueError before any write, so no partial or backup file is produced.

The implementation saves first and then applies the existing sanitizer to the saved path, reusing MetadataMixin rather than duplicating its logic. Because `save()` writes the updated trees back to the working directory, the sanitizer reads the same state that was just written.

Evidence: RED 6 failed / 1 passed, all "unexpected keyword argument 'sanitize_level'" (/tmp/opencode/deploy2119-red.log); GREEN 7 passed; full suite 1662 passed / 17 skipped; coverage 91.96% against the plan's 88% gate (the repo config's 100% target was already unmet before this change). Ruff check and format passed. A mutation that disabled the sanitize branch failed 5 tests, confirming the assertions have discriminating power. Independent acceptance PASS, including checks that out-of-range rejection precedes saving, edits survive sanitization, and level 0 is byte-identical to a plain save.

Return shape: the `sanitized` key appears only when level > 0, so callers must not assume a constant schema. The existing sanitizer docstring wording about its empty-string default is unchanged and out of scope here.
