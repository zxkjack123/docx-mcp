# Handle migration batch 1 — #2118

30 table/style/property/image tools now append optional document_handle and use the existing resolver. No operation arguments or underlying method names changed.

RED: 60 failed / 30 passed (unexpected handle keyword); GREEN: 90 passed; full suite: 1270 passed / 17 skipped. Ruff check and format passed. Independent acceptance confirmed all 30 signatures, routing and absence of unrelated edits. Evidence: /tmp/opencode/deploy2118/b1-red.log. Remaining legacy tools: 128. No push.
