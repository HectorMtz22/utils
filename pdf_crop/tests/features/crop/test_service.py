from pdf_crop.features.crop.service import crop
from pdf_crop.shared.pdf_io import open_pdf, page_count


def test_crop_writes_subset(ten_page_pdf, tmp_path):
    # Pure-pypdf path (no redaction): crop() subsets the selected pages into dest.
    reader = open_pdf(ten_page_pdf)
    dest = tmp_path / "out.pdf"
    crop(reader, ten_page_pdf, [1, 2, 3], dest)
    assert page_count(open_pdf(dest)) == 3


def test_crop_writes_single_page(three_page_pdf, tmp_path):
    reader = open_pdf(three_page_pdf)
    dest = tmp_path / "explicit.pdf"
    crop(reader, three_page_pdf, [2], dest)
    assert dest.exists()
    assert page_count(open_pdf(dest)) == 1
