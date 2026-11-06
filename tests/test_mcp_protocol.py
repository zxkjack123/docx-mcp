"""Protocol-level smoke tests: the server must speak MCP over stdio.

Every other test in this suite imports the tool functions and calls them
directly, which never exercises the transport, the SDK wiring, or the JSON-RPC
framing. These tests launch the real server as a subprocess and drive it with raw
JSON-RPC lines instead, so a break in that layer fails here rather than in a
user's client.

The subprocess is started with HOME redirected: ``cli.run_server()`` calls
``auto_install_skill()`` on startup, which copies SKILL.md into the user's home
directory. Redirecting HOME keeps that write in the test sandbox, and one test
asserts the real home was left alone.
"""

from __future__ import annotations

import ast
import asyncio
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import docx_mcp
from docx_mcp import server as server_module

# Generous: the server imports lxml and parses a document set on startup. A
# healthy run takes a couple of seconds; this only exists to stop a hang.
TIMEOUT = 60

REPO_ROOT = Path(__file__).resolve().parents[1]


def _initialize_message() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pytest-protocol-smoke", "version": "1"},
        },
    }


def _tools_list_message() -> dict:
    return {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}


def _snapshot(path: Path) -> tuple:
    """Return a comparable fingerprint of *path*, tolerating a missing file."""
    try:
        stat = path.stat()
    except OSError:
        return (False, None, None)
    return (True, stat.st_mtime_ns, stat.st_size)


def _run_stdio(messages: list[dict], home: Path) -> list[dict]:
    """Start the server over stdio, feed *messages*, return parsed responses.

    stdin is kept open until every expected response id has arrived. Closing it
    right after writing (what ``subprocess.run(input=...)`` does) races the
    server: on EOF the transport shuts down, and a request still queued behind
    the notification can be dropped before it is handled.
    """
    env = {**os.environ, "HOME": str(home)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "docx_mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )
    expected = {m["id"] for m in messages if "id" in m}
    responses: list[dict] = []

    # A reader thread keeps stdout draining without blocking the write side.
    lines: queue.Queue = queue.Queue()

    def _pump(stream) -> None:
        try:
            for line in stream:
                lines.put(line)
        finally:
            lines.put(None)

    threading.Thread(target=_pump, args=(proc.stdout,), daemon=True).start()

    try:
        if proc.stdin is not None:
            for message in messages:
                proc.stdin.write(json.dumps(message) + "\n")
            proc.stdin.flush()

        deadline = time.monotonic() + TIMEOUT
        while {r.get("id") for r in responses} & expected != expected:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                line = lines.get(timeout=remaining)
            except queue.Empty:
                break
            if line is None:
                break
            line = line.strip()
            if not line:
                continue
            try:
                responses.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # tolerate any non-JSON banner on stdout
    finally:
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    stderr = proc.stderr.read() if proc.stderr is not None else ""
    assert responses, f"server produced no JSON-RPC output; stderr={stderr!r}"
    missing = expected - {r.get("id") for r in responses}
    assert not missing, f"no response for id(s) {sorted(missing)}; stderr={stderr!r}"
    return responses


@pytest.fixture(scope="module")
def handshake(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """One server run shared by the tests below (startup is the slow part)."""
    home = tmp_path_factory.mktemp("sandbox-home")
    real_skill = Path.home() / ".claude" / "skills" / "docx-mcp" / "SKILL.md"
    before = _snapshot(real_skill)

    responses = _run_stdio(
        [
            _initialize_message(),
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            _tools_list_message(),
        ],
        home,
    )

    after = _snapshot(real_skill)
    return {"responses": responses, "home": home, "real_skill": (before, after)}


def _by_id(responses: list[dict], msg_id: int) -> dict:
    for msg in responses:
        if msg.get("id") == msg_id:
            return msg
    pytest.fail(f"no response with id={msg_id} in {responses}")


def test_initialize_reports_name_version_and_capabilities(handshake: dict) -> None:
    """initialize must advertise a name, a non-empty version and the tool capability."""
    result = _by_id(handshake["responses"], 1).get("result")
    assert result is not None, "initialize returned an error"

    info = result["serverInfo"]
    assert info["name"] == "docx-mcp"
    # An empty version string is what a client shows in its server list, so it
    # must carry the package version rather than "".
    assert info["version"] == docx_mcp.__version__
    assert info["version"] != ""
    assert result["protocolVersion"]
    assert "tools" in result["capabilities"]


def _count_declared_tools() -> int:
    """Count ``@mcp.tool(...)`` decorators in server.py by parsing the source.

    This is the signal that is independent of runtime state. Comparing the wire
    tool set against the in-process registry cannot catch a tool that is declared
    but never registered: both sides read the same singleton, so both miss it and
    the sets still match. The source text still shows the decorator, so the counts
    diverge.

    What this deliberately does not see:

    - **Names.** It counts decorators, so replacing one tool with another leaves
      the count unchanged. Only the three tools named explicitly in the caller
      have a name-level guard.
    - **Syntax other than ``@mcp.tool(...)`` on a def.** Moving tools into a
      separate module, aliasing the server object, or registering through a
      factory would make the count too low and raise a *false* red with a
      misleading message. If tools are ever restructured that way, this helper
      needs to follow them.
    """
    source = (REPO_ROOT / "docx_mcp" / "server.py").read_text(encoding="utf-8")
    count = 0
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if not isinstance(target, ast.Attribute) or target.attr != "tool":
                continue
            owner = target.value
            if isinstance(owner, ast.Name) and owner.id == "mcp":
                count += 1
    return count


def test_tools_list_matches_registered_tools(handshake: dict) -> None:
    """The transport must expose exactly the tools registered in-process."""
    result = _by_id(handshake["responses"], 2).get("result")
    assert result is not None, "tools/list returned an error"

    over_the_wire = [tool["name"] for tool in result["tools"]]
    assert over_the_wire, "tools/list returned nothing"
    assert len(over_the_wire) == len(set(over_the_wire)), "duplicate tool names over the wire"

    registered = asyncio.run(server_module.mcp.list_tools())
    assert set(over_the_wire) == {tool.name for tool in registered}

    # Independent cross-check: source declarations vs what actually reached the wire.
    declared = _count_declared_tools()
    assert declared == len(over_the_wire), (
        f"server.py declares {declared} @mcp.tool decorators but the wire exposes "
        f"{len(over_the_wire)} tools -- a declared tool did not register"
    )

    for required in ("open_document", "save_document", "docx_list_captions"):
        assert required in over_the_wire


def test_server_startup_does_not_write_outside_home(handshake: dict) -> None:
    """Startup may install the bundled skill, but only under the given HOME."""
    before, after = handshake["real_skill"]
    assert before == after, (
        "server startup wrote to the real ~/.claude/skills/docx-mcp; "
        f"fingerprint changed from {before} to {after}"
    )
    installed = handshake["home"] / ".claude" / "skills" / "docx-mcp" / "SKILL.md"
    assert installed.exists(), "the sandboxed HOME did not receive the skill install"
