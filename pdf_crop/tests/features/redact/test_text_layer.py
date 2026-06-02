from pypdf import PdfWriter
from pypdf.generic import ArrayObject, ContentStream, NameObject, NumberObject, TextStringObject

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


def test_page_text_handles_page_without_contents():
    """A blank page (get_contents() is None) must return empty text and charmap."""
    w = PdfWriter()
    page = w.add_blank_page(width=200, height=200)

    text, charmap = text_layer.page_text(page)

    assert text == ""
    assert charmap == []
    # delete_spans with empty spans is a true no-op; a non-empty span would
    # IndexError because charmap is empty — tested separately as a known
    # limitation (delete_spans is not robust to out-of-range spans on
    # contentless pages).
    text_layer.delete_spans(page, [])  # must not raise


def test_tj_array_reconstruct_and_delete():
    """The TJ (kerning array) path is exercised end-to-end."""
    w = PdfWriter()
    page = w.add_blank_page(width=300, height=300)

    cs = ContentStream(None, None)
    arr = ArrayObject([
        TextStringObject("AB"),
        NumberObject(-120),
        TextStringObject("12345678"),
    ])
    cs.operations = [
        ([], b"BT"),
        ([arr], b"TJ"),
        ([], b"ET"),
    ]
    page[NameObject("/Contents")] = cs

    text, charmap = text_layer.page_text(page)
    assert text == "AB12345678"
    assert len(charmap) == len(text)

    start = text.index("12345678")
    text_layer.delete_spans(page, [(start, start + 8)])

    text2, _ = text_layer.page_text(page)
    assert text2 == "AB"

    # The kerning number (-120) must survive in the rebuilt TJ array.
    new_arr = page.get_contents().operations[1][0][0]
    assert any(not hasattr(e, "lower") for e in new_arr)  # NumberObject has no .lower
