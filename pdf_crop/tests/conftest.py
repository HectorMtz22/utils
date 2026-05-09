from pathlib import Path

import pytest
from reportlab.pdfgen.canvas import Canvas


def _make_pdf(path: Path, page_count: int) -> Path:
    """Generate a minimal PDF with `page_count` pages, each labelled 'Page N'."""
    c = Canvas(str(path))
    for i in range(1, page_count + 1):
        c.setFont("Helvetica", 24)
        c.drawString(72, 720, f"Page {i}")
        c.showPage()
    c.save()
    return path


@pytest.fixture
def pdf_factory(tmp_path):
    """Returns a callable: pdf_factory(name, pages) -> Path."""
    def _factory(name: str, page_count: int) -> Path:
        return _make_pdf(tmp_path / name, page_count)
    return _factory


@pytest.fixture
def three_page_pdf(pdf_factory):
    return pdf_factory("three.pdf", 3)


@pytest.fixture
def ten_page_pdf(pdf_factory):
    return pdf_factory("ten.pdf", 10)
