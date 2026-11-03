# Zero-edit save fidelity guard (#4271)

Adds tests/test_save_fidelity.py: a regression guard asserting that a zero-edit open+save changes no part bytes. Eight synthetic samples cover plain text, tables, tracked changes, images, styles, footnotes, comments and multiple sections; each is saved once and twice, and every ZIP member's SHA-256 is compared with the original. ZIP container metadata (entry order, timestamps, compression) is deliberately not compared.

Scope limit stated in the module docstring: this pins zero-edit save only. It does not cover edited documents, other office suites re-saving the file, or Word-native rendering.

Evidence: 18 passed; full suite 1680 passed / 17 skipped; coverage 91.97% against the plan's 88% gate. Discriminating power was checked by mutation: injecting an extra part or a one-byte change into saved parts makes 16 tests fail, a PNG-only change fails the image cases, and a neutered comparator fails the two comparator self-tests. Independent acceptance reproduced this with its own mutations.

Two sample defects found while writing this are worth recording: a sample whose relationships pointed at a missing part triggered the designed broken-relationship repair, which rewrote that rels part (broken_rels_removed=1). That is correct product behaviour, not a save defect; the samples were corrected to reference only parts that exist.

Task #4271 stays open: the original report also mentions styles inflation, first-line indent loss, image downsampling and removed comment parts, none of which are reproduced by the zero-edit save path measured so far. No root cause is claimed and no pre-edit baseline sample is available.
