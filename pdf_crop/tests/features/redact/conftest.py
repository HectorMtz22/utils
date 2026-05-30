from pathlib import Path

import pytest
from reportlab.pdfgen.canvas import Canvas


@pytest.fixture
def text_pdf_factory(tmp_path):
    """pdf with one line of text per page. text_pdf_factory(["line a", "line b"]) -> Path."""
    def _factory(lines):
        path = tmp_path / "text.pdf"
        c = Canvas(str(path))
        for line in lines:
            c.setFont("Helvetica", 12)
            c.drawString(72, 720, line)
            c.showPage()
        c.save()
        return path
    return _factory
