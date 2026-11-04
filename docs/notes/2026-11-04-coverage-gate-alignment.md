# Coverage gate: single source of truth aligned to the enforced 88% (#T-5271)

The coverage threshold was declared twice with different values, and the smaller
one won silently.

## What was wrong

| Where | Declared | Actually enforced |
|---|---|---|
| `pyproject.toml` → `[tool.coverage.report] fail_under` | `100` | **no** — overridden by the command-line flag |
| `.github/workflows/ci.yml` → `pytest --cov-fail-under=88` | `88` | **yes** |

`pytest-cov` gives the command-line `--cov-fail-under` precedence over the
`fail_under` value read from `pyproject.toml`. CI has always passed the flag, so
the declared `100` never gated anything in CI; it only ever applied to a bare
local `pytest --cov …` run, where it failed against the real (92%) coverage and
produced a red result that CI itself considered green. Declared ≠ enforced.

## Discriminating experiment (run before the change)

Four runs, all on this tree, to prove the declared value was inert rather than
merely assume it:

| # | Command | Result |
|---|---|---|
| D1 | `pytest -q --cov=docx_mcp --cov-report=term` (no flag) | **FAIL** — `Required test coverage of 100.0% not reached. Total coverage: 92.06%`, exit 1 |
| D2 | `pytest -q --cov=docx_mcp --cov-report=term --cov-fail-under=88` | **PASS** — `Required test coverage of 88% reached. Total coverage: 92.06%`, exit 0 |
| D3 | same as D2 but via `coverage report` | `Coverage failure: total of 92 is less than fail-under=100` — confirms `pyproject` was read |
| D4 | `.pre-commit-config.yaml` inspection | no coverage invocation at all |

D1 vs D2 is the decisive pair: identical tree, identical tests, opposite verdicts —
the flag is what governs. Actual figures: `TOTAL 8881 705 92%` (705 statements
uncovered).

## Resolution

Aligned the declaration to the value that has actually been enforced, and removed
the duplicate so there is exactly one source:

- `pyproject.toml`: `fail_under = 100` → `88`, with a comment stating that CI
  deliberately passes no `--cov-fail-under` flag so this value is what gets
  enforced in both environments.
- `.github/workflows/ci.yml`: dropped `--cov-fail-under=88`; the step is now
  `uv run pytest --cov=docx_mcp --cov-report=term-missing`, with a comment
  pointing at `pyproject.toml` as the source.

Strictness is unchanged where it actually mattered — CI enforced 88 before and
enforces 88 after. The only behavioural change is that a bare local
`pytest --cov` no longer fails against a threshold nobody was enforcing.

## Post-change verification

| # | Command | Result |
|---|---|---|
| V1 | bare `pytest --cov=docx_mcp --cov-report=term` (pyproject = 88) | **PASS** — `Required test coverage of 88.0% reached`, exit 0 |
| V2 | exact CI invocation (no flag) | **PASS**, exit 0 |
| V3 | pyproject temporarily set to `99`, bare run | **FAIL** — `Required test coverage of 99.0% not reached`, exit 1 |
| V4 | pyproject restored to `88`, bare run | **PASS**, exit 0 |

V3 is the anti-vacuity check: had `pyproject` been ignored, V3 would have passed.
It failed, so the file really is the source, and V4 confirms the restore is clean.

## Boundary

This note records a *configuration* change only. It does not raise coverage; the
705 uncovered statements remain uncovered, and 88 is a floor, not a target. Anyone
wanting to reinstate 100 needs to add tests first (`pyproject.toml` is now the one
place to change the number). The value 88 was chosen by the user in-session from a
set of spelled-out options; it was not inferred by the agent.

## Supersedes

This note supersedes the closing remark in `docs/notes/2026-11-04-list-captions.md`
(committed with #T-5206), which recorded `pyproject.toml` as `fail_under = 100`
against CI's 88 and noted that a bare `pytest --cov` consequently failed on the
repository baseline. That note is frozen once committed, so its wording is left
intact; as of #T-5271 the statement no longer holds — `pyproject.toml` declares 88
and a bare `pytest --cov` passes.

The other `fail_under = 100` / `--cov-fail-under=100` mentions in this repository
are dated historical records only (`sessions/`, `docs/plans/`,
`docs/superpowers/plans|specs/`). None is a live configuration: `coverage debug
config` reports `pyproject.toml` as the only config file read. Leaving them as they
are is deliberate — they document what was true in March–May 2026 and are not
rewritten retroactively.

Related: the same session corrected a PM ledger inconsistency on task #2116
(`status=done` but `progress=0` and `completed_at=None`); the tool-level
`pm_task_update` cannot backfill `completed_at`, so `pm_task_complete` with the
evidenced acceptance date was used.
