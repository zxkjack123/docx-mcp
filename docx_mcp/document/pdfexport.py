"""PDF export mixin: convert the open document to PDF via LibreOffice headless."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

DEFAULT_TIMEOUT = 90.0
"""Seconds to wait for a headless LibreOffice conversion before failing loudly.

Must stay clearly below the deployment-side client hard cap
(`mcp.timeout.execution` = 120000 ms = 120 s); at or above that cap the client
gives up first and the hang never surfaces as an explicit RuntimeError.
Override with DOCX_MCP_PDF_TIMEOUT.
"""

TIMEOUT_ENV = "DOCX_MCP_PDF_TIMEOUT"


def _resolve_timeout() -> float:
    """Return the conversion timeout in seconds, with a positive env override."""
    raw = os.environ.get(TIMEOUT_ENV)
    if not raw:
        return DEFAULT_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT
    return value if value > 0 else DEFAULT_TIMEOUT


class PdfExportMixin:
    def convert_to_pdf(self, output_path: str) -> dict:
        """Convert the current document to PDF using LibreOffice headless.

        Saves the document first, then invokes:
          libreoffice --headless --convert-to pdf --outdir <dir> <docx>

        Args:
            output_path: Desired path for the output PDF file.

        Returns:
            {"pdf_path": str}

        Raises:
            RuntimeError: If no document is open, LibreOffice is not found,
                          or the conversion process exits with a non-zero code.
        """
        if self.workdir is None:
            raise RuntimeError("No document is open.")

        lo = shutil.which("libreoffice") or shutil.which("soffice")
        if lo is None:
            raise RuntimeError(
                "LibreOffice not found. Install it and ensure 'libreoffice' or "
                "'soffice' is on PATH."
            )

        self.save(self.source_path, backup=False)

        out = Path(output_path)
        outdir = out.parent
        outdir.mkdir(parents=True, exist_ok=True)

        timeout = _resolve_timeout()
        try:
            result = subprocess.run(
                [
                    lo,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(outdir),
                    str(self.source_path),
                ],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"LibreOffice conversion timed out after {timeout:g}s "
                f"(set {TIMEOUT_ENV} to change the limit)."
            ) from exc
        if result.returncode != 0:
            raise RuntimeError(
                f"LibreOffice conversion failed (exit {result.returncode}): {result.stderr.strip()}"
            )

        # LibreOffice names the output after the input stem
        generated = outdir / (Path(self.source_path).stem + ".pdf")
        if generated != out and generated.exists():
            generated.rename(out)

        return {"pdf_path": str(out)}
