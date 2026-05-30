from pdf_crop.shared.pdf_io import open_pdf
from pdf_crop.features.redact import text_layer


def test_page_text_reconstructs_drawn_string(text_pdf_factory):
    src = text_pdf_factory(["CLABE 002010077777777771 here"])
    page = open_pdf(src).pages[0]
    text, charmap = text_layer.page_text(page)
    assert "002010077777777771" in text
    assert len(charmap) == len(text)
