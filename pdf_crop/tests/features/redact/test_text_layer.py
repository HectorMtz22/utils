from pypdf import PdfWriter

from pdf_crop.shared.pdf_io import open_pdf
from pdf_crop.features.redact import text_layer


def test_page_text_reconstructs_drawn_string(text_pdf_factory):
    src = text_pdf_factory(["CLABE 002010077777777771 here"])
    page = open_pdf(src).pages[0]
    text, charmap = text_layer.page_text(page)
    assert "002010077777777771" in text
    assert len(charmap) == len(text)


def test_delete_spans_removes_target_keeps_neighbors(text_pdf_factory, tmp_path):
    src = text_pdf_factory(["CLABE 002010077777777771 here"])
    reader = open_pdf(src)
    page = reader.pages[0]
    text, _ = text_layer.page_text(page)
    start = text.index("002010077777777771")
    end = start + len("002010077777777771")

    text_layer.delete_spans(page, [(start, end)])

    writer = PdfWriter()
    writer.add_page(page)
    out = tmp_path / "redacted.pdf"
    with out.open("wb") as f:
        writer.write(f)

    extracted = open_pdf(out).pages[0].extract_text()
    assert "002010077777777771" not in extracted
    assert "CLABE" in extracted
    assert "here" in extracted


def test_delete_spans_only_affects_targeted_span(text_pdf_factory, tmp_path):
    src = text_pdf_factory(["Alpha 002010077777777771", "Beta keepme"])
    reader = open_pdf(src)
    p0 = reader.pages[0]
    text, _ = text_layer.page_text(p0)
    s = text.index("002010077777777771")
    text_layer.delete_spans(p0, [(s, s + 18)])
    w = PdfWriter()
    w.add_page(p0)
    w.add_page(reader.pages[1])
    out = tmp_path / "r.pdf"
    with out.open("wb") as f:
        w.write(f)
    pages = open_pdf(out).pages
    assert "002010077777777771" not in pages[0].extract_text()
    assert "Alpha" in pages[0].extract_text()
    assert "keepme" in pages[1].extract_text()
