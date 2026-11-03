# Handle propagation — #2118 completion record

All 158 legacy @mcp.tool functions now accept a trailing optional document_handle, migrated in six independently verified batches (006dcd4, 6bb6435, 022ef43, fb69fcf, 74fa60c, 7bb503e). Static check: 219 tools, 217 with the parameter, pending 0, one _require_doc definition remaining, compare_documents and diff_to_text intentionally unchanged.

Live verification after restarting docx-mcp.service: tools/list returns 219 tools, 217 expose document_handle, only the two path-based tools omit it, and the parameter is never marked required. convert_to_pdf routed an explicit handle and produced a 14716-byte PDF; compare_documents still refuses table input without writing output.

Full suite 1655 passed / 17 skipped, coverage 91.95%, ruff clean. Some tools wrap their return value; routing tests match nested payloads and a dedicated contract test pins get_word_count. This record contains no claim about Word-native rendering and no push.
