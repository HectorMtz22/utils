from pdf_crop.features.crop.service import crop_pdf
from pdf_crop.shared.pdf_io import open_pdf, page_count


def test_crop_writes_subset(ten_page_pdf, tmp_path):
    dest = tmp_path / "out.pdf"
    result = crop_pdf(ten_page_pdf, [1, 2, 3], dest)
    assert result == dest
    assert page_count(open_pdf(result)) == 3


def test_crop_returns_dest(three_page_pdf, tmp_path):
    dest = tmp_path / "explicit.pdf"
    result = crop_pdf(three_page_pdf, [2], dest)
    assert result == dest
    assert dest.exists()
