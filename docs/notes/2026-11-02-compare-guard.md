# Compare non-text guard (#2115)

Comparison now rejects tables, drawing/image elements, embedded objects and OMML equations in either input before writing output. Detection includes paragraph descendants. Plain-text comparisons retain their existing behavior. This deliberately changes unsupported inputs from silently incomplete output to ValueError.

Evidence: four new regression tests failed with DID NOT RAISE before wiring the guard; comparison suite then passed 11 tests and full suite passed 1161 with 17 skips. Content controls (w:sdt) remain a separate follow-up, not covered by this guard. No native Word rendering claim is made.
