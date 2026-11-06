"""Generate the frozen list of declared MCP tool names.

``tests/test_mcp_protocol.py`` compares the names the server actually exposes
over stdio against ``tests/fixtures/tools_snapshot.txt``. Regenerate that file
deliberately whenever the tool surface changes::

    python tests/generate_tools_snapshot.py --write

The resulting diff is the review artefact -- it shows exactly which tool name
appeared or disappeared. Do not regenerate it inside CI: a snapshot that updates
itself cannot witness anything.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_SOURCE = REPO_ROOT / "docx_mcp" / "server.py"
SNAPSHOT = REPO_ROOT / "tests" / "fixtures" / "tools_snapshot.txt"


def declared_tool_names(source: str | None = None) -> list[str]:
    """Return the tool names declared by ``@mcp.tool(...)`` decorators, sorted.

    The name is taken from the decorated function, which is what the server
    advertises: no decorator in the module passes ``name=``. If that ever
    changes, this derivation has to follow it.
    """
    text = SERVER_SOURCE.read_text(encoding="utf-8") if source is None else source
    names: list[str] = []
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if not isinstance(target, ast.Attribute) or target.attr != "tool":
                continue
            owner = target.value
            if isinstance(owner, ast.Name) and owner.id == "mcp":
                names.append(node.name)
    return sorted(names)


def main(argv: list[str]) -> int:
    names = declared_tool_names()
    if "--write" in argv:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text("".join(f"{name}\n" for name in names), encoding="utf-8")
        print(f"wrote {len(names)} tool names to {SNAPSHOT}")
        return 0
    for name in names:
        print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
