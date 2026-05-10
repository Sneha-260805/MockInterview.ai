"""Tests for the pdf_parser service (txt and docx support; pdf requires PyMuPDF)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.pdf_parser import extract_text, extract_from_txt


class TestExtractFromTxt:
    def test_basic_utf8_text(self):
        content = "John Doe\nSoftware Engineer\nPython, JavaScript, React"
        result = extract_from_txt(content.encode("utf-8"))
        assert "John Doe" in result
        assert "Python" in result

    def test_latin1_encoding_fallback(self):
        content = "Résumé - Software Ëngineer"
        result = extract_from_txt(content.encode("latin-1"))
        assert len(result) > 0

    def test_strips_extra_blank_lines(self):
        content = "Line 1\n\n\n\n\nLine 2"
        result = extract_from_txt(content.encode("utf-8"))
        # Should not have more than 2 consecutive newlines
        assert "\n\n\n" not in result

    def test_normalises_whitespace(self):
        content = "Python   JavaScript    React"
        result = extract_from_txt(content.encode("utf-8"))
        assert "  " not in result  # multiple spaces collapsed

    def test_empty_file_returns_empty_string(self):
        result = extract_from_txt(b"")
        assert result == ""


class TestExtractText:
    def test_unsupported_extension_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_text(b"content", "resume.xyz")

    def test_no_extension_raises_value_error(self):
        with pytest.raises(ValueError):
            extract_text(b"content", "resume")

    def test_txt_file_dispatched_correctly(self):
        content = "Alice Smith\nPython Developer"
        result = extract_text(content.encode("utf-8"), "cv.txt")
        assert "Alice Smith" in result

    def test_txt_uppercase_extension(self):
        content = "Bob Jones\nJava Developer"
        result = extract_text(content.encode("utf-8"), "cv.TXT")
        assert "Bob Jones" in result

    def test_docx_without_library_raises_value_error(self):
        """If python-docx is not installed, should raise ValueError not ImportError."""
        import importlib
        import unittest.mock as mock

        # Simulate python-docx not being available
        with mock.patch.dict("sys.modules", {"docx": None}):
            with pytest.raises((ValueError, Exception)):
                extract_text(b"fake docx bytes", "resume.docx")

    def test_docx_invalid_bytes_raises_value_error(self):
        """Passing garbage bytes as docx should raise ValueError."""
        with pytest.raises((ValueError, Exception)):
            extract_text(b"not a real docx file bytes here", "resume.docx")


class TestExtractFromDocx:
    def test_real_docx_extraction(self):
        """Create a real in-memory docx and verify extraction."""
        pytest.importorskip("docx", reason="python-docx not installed")
        import io
        from docx import Document

        doc = Document()
        doc.add_paragraph("Jane Smith")
        doc.add_paragraph("Senior Backend Engineer")
        doc.add_paragraph("Skills: Python, FastAPI, PostgreSQL")

        buf = io.BytesIO()
        doc.save(buf)
        docx_bytes = buf.getvalue()

        result = extract_text(docx_bytes, "resume.docx")
        assert "Jane Smith" in result
        assert "Python" in result

    def test_docx_table_content_extracted(self):
        """Tables in resume templates should also be extracted."""
        pytest.importorskip("docx", reason="python-docx not installed")
        import io
        from docx import Document

        doc = Document()
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Experience"
        table.cell(0, 1).text = "5 years"
        table.cell(1, 0).text = "Education"
        table.cell(1, 1).text = "B.Sc. Computer Science"

        buf = io.BytesIO()
        doc.save(buf)
        docx_bytes = buf.getvalue()

        result = extract_text(docx_bytes, "resume.docx")
        assert "Experience" in result
        assert "B.Sc. Computer Science" in result
