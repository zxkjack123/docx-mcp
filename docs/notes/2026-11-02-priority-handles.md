# Priority handle propagation (#2118)

Status: PARTIAL. Six high-frequency tools now accept a trailing optional document_handle and resolve it through the existing registry: convert_to_pdf, sanitize_metadata, find_replace_formatted, get_document_outline, accept_all_changes, reject_all_changes. The remaining 158 legacy tools are outside this batch.

Routing tests use mock document instances to isolate server dispatch from document operation semantics: explicit B selects B and never A; unknown C raises; required-handle mode rejects omission; compatibility mode accepts omission and empty handles. PDF tests establish routing only, not rendering. Existing full-suite tests exercise the underlying operations.

RED: 12 failed / 6 passed (unexpected keyword document_handle). GREEN: 19 passed including a real-document isolation regression (also RED on the original server). Full suite: 1180 passed / 17 skipped, coverage 90.35%, threshold 88%. Ruff check and format check passed. No service restart, client restart or push is included.
