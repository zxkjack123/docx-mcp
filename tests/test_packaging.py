"""Packaging invariants: the installed metadata must match the running source.

An editable install writes a ``.dist-info`` directory when it is created, and
bumping ``version`` in ``pyproject.toml`` does not touch it. The two therefore
drift until someone re-syncs, and anything reading
``importlib.metadata.version()`` then reports a version the running code does
not have. This test turns that silent drift into a failure.
"""

from __future__ import annotations

import importlib.metadata
from importlib.metadata import PackageNotFoundError

import pytest

import docx_mcp

DIST_NAME = "docx-mcp-server"


def _looks_like_this_project(name: str | None) -> bool:
    """Cheap heuristic used only to tell 'not installed' from 'renamed'."""
    return (name or "").lower().startswith("docx")


def test_installed_metadata_matches_source_version() -> None:
    """metadata.version() must agree with docx_mcp.__version__."""
    try:
        installed = importlib.metadata.version(DIST_NAME)
    except PackageNotFoundError:
        # A bare checkout legitimately has no install. But if some *other*
        # docx-named distribution is present, this project was almost certainly
        # renamed: skipping would let the guard stop running without a trace.
        suspects = sorted(
            {
                dist.metadata["Name"]
                for dist in importlib.metadata.distributions()
                if _looks_like_this_project(dist.metadata["Name"])
            }
        )
        if suspects:
            pytest.fail(
                f"{DIST_NAME!r} is not installed, but {suspects!r} looks like this project. "
                "Either the distribution was renamed (update DIST_NAME so this guard keeps "
                "running) or the install is broken."
            )
        pytest.skip(f"{DIST_NAME} is not installed; metadata cannot be checked")

    assert installed == docx_mcp.__version__, (
        f"installed metadata reports {installed!r} but the source is "
        f"{docx_mcp.__version__!r}. The editable install is stale -- run "
        "`uv sync --frozen --dev` to refresh it."
    )
