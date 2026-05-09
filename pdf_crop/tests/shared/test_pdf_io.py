import pytest

from pdf_crop.shared.pdf_io import open_pdf, page_count, write_subset
from pdf_crop.shared.errors import SourceNotFound, NotAPdf


def test_open_pdf_returns_reader(three_page_pdf):
    reader = open_pdf(three_page_pdf)
    assert reader is not None


def test_page_count(three_page_pdf, ten_page_pdf):
    assert page_count(open_pdf(three_page_pdf)) == 3
    assert page_count(open_pdf(ten_page_pdf)) == 10


def test_open_pdf_missing_file(tmp_path):
    with pytest.raises(SourceNotFound):
        open_pdf(tmp_path / "nope.pdf")


def test_open_pdf_not_a_pdf(tmp_path):
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"this is not a pdf")
    with pytest.raises(NotAPdf):
        open_pdf(fake)


def test_write_subset_extracts_correct_pages(ten_page_pdf, tmp_path):
    reader = open_pdf(ten_page_pdf)
    dest = tmp_path / "subset.pdf"
    write_subset(reader, [1, 3, 5], dest)

    out = open_pdf(dest)
    assert page_count(out) == 3


def test_write_subset_preserves_order(ten_page_pdf, tmp_path):
    reader = open_pdf(ten_page_pdf)
    dest = tmp_path / "subset.pdf"
    write_subset(reader, [7, 2, 9], dest)

    out = open_pdf(dest)
    extracted = [page.extract_text().strip() for page in out.pages]
    assert extracted == ["Page 7", "Page 2", "Page 9"]
