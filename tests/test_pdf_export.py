"""Tests for P9.5: PDF export — convert_to_pdf."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docx_mcp.document import DocxDocument


def _make_doc(tmp_path: Path) -> DocxDocument:
    out = str(tmp_path / "test.docx")
    return DocxDocument.create(out)


class TestConvertToPdf:
    def test_returns_pdf_path_key(self, tmp_path: Path):
        """convert_to_pdf returns dict with 'pdf_path' key."""
        doc = _make_doc(tmp_path)
        pdf_out = str(tmp_path / "out.pdf")

        with (
            patch("shutil.which", return_value="/usr/bin/libreoffice"),
            patch("subprocess.run") as mock_run,
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.rename"),
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = doc.convert_to_pdf(pdf_out)

        assert "pdf_path" in result

    def test_raises_if_libreoffice_not_found(self, tmp_path: Path):
        """convert_to_pdf raises RuntimeError when LibreOffice is not installed."""
        doc = _make_doc(tmp_path)
        with (
            patch("shutil.which", return_value=None),
            pytest.raises(RuntimeError, match="LibreOffice"),
        ):  # noqa: E501
            doc.convert_to_pdf(str(tmp_path / "out.pdf"))

    def test_calls_libreoffice_subprocess(self, tmp_path: Path):
        """convert_to_pdf calls libreoffice --headless --convert-to pdf."""
        doc = _make_doc(tmp_path)
        pdf_out = str(tmp_path / "out.pdf")

        with (
            patch("shutil.which", return_value="/usr/bin/libreoffice"),
            patch("subprocess.run") as mock_run,
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.rename"),
        ):
            mock_run.return_value = MagicMock(returncode=0)
            doc.convert_to_pdf(pdf_out)

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "--headless" in cmd
        assert "--convert-to" in cmd
        assert "pdf" in cmd

    def test_raises_if_subprocess_fails(self, tmp_path: Path):
        """convert_to_pdf raises RuntimeError when libreoffice exits non-zero."""
        doc = _make_doc(tmp_path)
        pdf_out = str(tmp_path / "out.pdf")

        with (
            patch("shutil.which", return_value="/usr/bin/libreoffice"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=1, stderr="error msg")
            with pytest.raises(RuntimeError, match="conversion failed"):
                doc.convert_to_pdf(pdf_out)

    def test_subprocess_gets_devnull_stdin_and_timeout(self, tmp_path: Path, monkeypatch):
        """The child must not inherit the MCP stdio pipe, and must be time-bounded."""
        from docx_mcp.document import pdfexport

        monkeypatch.delenv("DOCX_MCP_PDF_TIMEOUT", raising=False)
        doc = _make_doc(tmp_path)
        with (
            patch("shutil.which", return_value="/usr/bin/libreoffice"),
            patch("subprocess.run") as mock_run,
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.rename"),
        ):
            mock_run.return_value = MagicMock(returncode=0)
            doc.convert_to_pdf(str(tmp_path / "out.pdf"))

        kwargs = mock_run.call_args.kwargs
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert isinstance(kwargs["timeout"], (int, float))
        assert kwargs["timeout"] > 0
        assert kwargs["timeout"] < 120.0
        assert pdfexport.DEFAULT_TIMEOUT < 120.0

    def test_timeout_becomes_explicit_runtime_error(self, tmp_path: Path, monkeypatch):
        """A hung conversion must surface as RuntimeError naming the timeout."""
        monkeypatch.delenv("DOCX_MCP_PDF_TIMEOUT", raising=False)
        doc = _make_doc(tmp_path)
        with (
            patch("shutil.which", return_value="/usr/bin/libreoffice"),
            patch("subprocess.run") as mock_run,
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="libreoffice", timeout=90.0)
            with pytest.raises(RuntimeError, match=r"timed out after 90"):
                doc.convert_to_pdf(str(tmp_path / "out.pdf"))

    def test_timeout_env_override(self, tmp_path: Path, monkeypatch):
        """DOCX_MCP_PDF_TIMEOUT overrides the default; invalid values fall back."""
        from docx_mcp.document import pdfexport

        monkeypatch.setenv("DOCX_MCP_PDF_TIMEOUT", "7.5")
        assert pdfexport._resolve_timeout() == 7.5
        monkeypatch.setenv("DOCX_MCP_PDF_TIMEOUT", "not-a-number")
        assert pdfexport._resolve_timeout() == pdfexport.DEFAULT_TIMEOUT
        monkeypatch.setenv("DOCX_MCP_PDF_TIMEOUT", "0")
        assert pdfexport._resolve_timeout() == pdfexport.DEFAULT_TIMEOUT

    def test_raises_if_no_document_open(self, tmp_path: Path):
        """convert_to_pdf raises RuntimeError when no document is open."""
        doc = DocxDocument.__new__(DocxDocument)
        doc.workdir = None
        with pytest.raises(RuntimeError, match="No document"):
            doc.convert_to_pdf(str(tmp_path / "out.pdf"))
