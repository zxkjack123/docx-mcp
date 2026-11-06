# serverInfo.version + protocol-level smoke test (#T-5303)

Two leftovers from the MCP SDK v2 migration (#2625): the server advertised an
empty version, and nothing in the suite exercised the transport layer.

## Version

`MCPServer("docx-mcp", instructions=...)` was constructed without `version`, so
`initialize` returned `serverInfo = {"name": "docx-mcp", "version": ""}`. Clients
show that string in their server list, so it was visibly wrong.

The value now comes from `docx_mcp.__version__`, **not** from
`importlib.metadata`. That is deliberate — the three sources disagree in this
repo today:

| Source | Value |
|---|---|
| `.venv` dist-info (editable install) | **0.7.4** |
| `pyproject.toml` `version` | **0.8.0** |
| `docx_mcp.__version__` (what actually runs) | **0.8.0** |

The dist-info is stale: the version was bumped to 0.8.0 in `2702442` and the
venv was never re-synced. Reading metadata would therefore report a version that
does not match the code being executed. `__version__` tracks the source. The
stale-metadata problem itself is pre-existing and out of scope here; a CI check
comparing the two would be the durable fix.

## Protocol smoke test

`tests/test_mcp_protocol.py` launches `python -m docx_mcp` as a subprocess and
drives it with raw JSON-RPC lines, which is the only place in the suite that
touches transport, SDK wiring and framing. Three cases: the initialize handshake
(name, version, protocolVersion, tools capability), tools/list, and a check that
startup does not write outside `HOME`.

`cli.run_server()` calls `auto_install_skill()` on startup, so every spawn runs
with `HOME` redirected into the test sandbox; one assertion confirms the real
`~/.claude/skills/docx-mcp` fingerprint is unchanged and another confirms the
sandbox did receive the install (so the redirection is actually exercised, not
bypassed).

## The flake worth remembering

The first draft drove the server with `subprocess.run(input=payload)`, which
writes every line and then closes stdin. On EOF the SDK transport shuts down, so
a request still queued behind the `notifications/initialized` message can be
dropped before it is handled. Symptom: `initialize` responds, `tools/list` never
does — `no response with id=2`, with an empty stderr, which reads like a server
bug but is a harness bug.

Frequency before the fix: 2 failures across ~11 local runs during development,
then the independent verifier measured 3/20 (15%) on a reverted copy and
reproduced the same signature.

The fix is to keep stdin **open** until every expected response id has arrived,
draining stdout from a reader thread so the write side never blocks:

- write all messages, flush, do not close stdin
- read lines until the set of seen ids covers the set of expected ids, or the
  deadline expires
- close stdin, `wait(timeout=...)`, `kill()` on timeout, then include stderr in
  any failure message

Verified with 58 consecutive clean runs (10 serial, 20 serial in a copy, 20 in
two parallel streams, 8 under CPU load). If the residual failure rate were still
15%, 58 clean runs would have probability ~5.6e-5.

## Known limitation

The `tools/list` assertion compares the wire names against the in-process
registry (`mcp.list_tools()`). Both sides derive from the same module-level
singleton, so a failure that removes a tool on **both** sides — for example a
decorator raising during subprocess import — keeps the two sets equal and passes.
The test still catches an empty or truncated wire response, duplicate names, and
the absence of any of three named tools, which is the intended scope for a smoke
test. A full completeness proof would need an expected tool list frozen
independently of the implementation; pinning the count would instead churn on
every new tool.

## Non-goals

- `pyproject.toml` versioning is unchanged (no dynamic version).
- CLI behaviour, including skill auto-install, is unchanged.
- No MCP tool was added, removed or modified (still 220).
- No new third-party dependency.
