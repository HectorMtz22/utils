from pdf_crop.shared.pdf_io import open_pdf
from pdf_crop.features.redact import service, text_layer


def test_scan_counts_matches_per_category(text_pdf_factory):
    src = text_pdf_factory([
        "CLABE 002010077777777771 de JOSE PEREZ",
        "Otra pagina sin datos",
    ])
    reader = open_pdf(src)
    findings = service.scan(reader, [1, 2], categories={"clabe", "name"}, names=["Jose Perez"])
    assert findings.summary() == {"clabe": 1, "name": 1}
    assert set(findings.by_page) == {1}  # only page 1 (1-indexed) had matches


def test_scan_empty_when_no_text(three_page_pdf):
    reader = open_pdf(three_page_pdf)
    findings = service.scan(reader, [1, 2, 3], categories={"clabe", "card"}, names=[])
    assert findings.matches == []
    assert findings.summary() == {}


def test_redact_removes_matches_from_written_pdf(text_pdf_factory, tmp_path):
    src = text_pdf_factory(["CLABE 002010077777777771 de JOSE PEREZ"])
    reader = open_pdf(src)

    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_page(reader.pages[0])

    service.redact(writer, categories={"clabe", "name"}, names=["Jose Perez"])

    out = tmp_path / "redacted.pdf"
    with out.open("wb") as f:
        writer.write(f)

    extracted = open_pdf(out).pages[0].extract_text()
    assert "002010077777777771" not in extracted
    assert "JOSE PEREZ" not in extracted
    assert "CLABE" in extracted


def test_redact_noop_when_nothing_matches(text_pdf_factory, tmp_path):
    src = text_pdf_factory(["Nothing sensitive here", "Still clean"])
    reader = open_pdf(src)
    from pypdf import PdfWriter
    writer = PdfWriter()
    for p in reader.pages:
        writer.add_page(p)
    service.redact(writer, categories={"clabe", "card", "name"}, names=["Zoe"])
    out = tmp_path / "out.pdf"
    with out.open("wb") as f:
        writer.write(f)
    pages = open_pdf(out).pages
    assert "Nothing sensitive here" in pages[0].extract_text()
    assert "Still clean" in pages[1].extract_text()


def test_redact_returns_count_of_removed_matches(text_pdf_factory, tmp_path):
    src = text_pdf_factory(["CLABE 002010077777777771 de JOSE PEREZ"])
    reader = open_pdf(src)
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    count = service.redact(writer, categories={"clabe", "name"}, names=["Jose Perez"])
    assert count == 2  # one CLABE + one name


def test_redact_returns_zero_when_nothing_matches(text_pdf_factory):
    src = text_pdf_factory(["nothing here"])
    reader = open_pdf(src)
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    assert service.redact(writer, categories={"clabe"}, names=[]) == 0


def test_scan_records_skipped_pages_on_parse_error(text_pdf_factory, monkeypatch):
    src = text_pdf_factory([
        "CLABE 002010077777777771 ok",
        "second page",
    ])
    reader = open_pdf(src)

    real_page_text = text_layer.page_text
    calls = {"n": 0}

    def flaky(page):
        calls["n"] += 1
        if calls["n"] == 2:  # fail on the second page scanned
            raise ValueError("boom")
        return real_page_text(page)

    monkeypatch.setattr(text_layer, "page_text", flaky)

    findings = service.scan(reader, [1, 2], categories={"clabe"}, names=[])
    assert findings.skipped_pages == [2]
    assert findings.summary() == {"clabe": 1}  # page 1 still processed


def test_redact_keeps_image_layer_and_does_not_blank_page(tmp_path):
    # Regression (UTILS-18): on a page with a background image + a real text
    # layer (a scanned/templated statement), redacting a text match must remove
    # only that text and leave the page intact. The old direct `/Contents`
    # assignment produced a malformed, fully-blank page (MuPDF "syntax error in
    # dict"); replace_contents() writes a valid indirect stream instead.
    import fitz
    from pypdf import PdfWriter

    src = tmp_path / "image_plus_text.pdf"
    doc = fitz.open()
    page = doc.new_page(width=420, height=595)
    pm = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 420, 595))
    pm.set_rect(pm.irect, (0, 80, 180))  # full-page (blue) background image
    page.insert_image(page.rect, pixmap=pm)
    page.insert_text((60, 300), "CLABE 002010077777777771", color=(1, 1, 1))
    doc.save(str(src))
    doc.close()

    reader = open_pdf(src)
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    service.redact(writer, categories={"clabe"}, names=[])

    out = tmp_path / "redacted.pdf"
    with out.open("wb") as f:
        writer.write(f)

    # The page still renders with its background — not a blank/corrupt page.
    rendered = fitz.open(str(out))
    pix = rendered[0].get_pixmap(dpi=40)
    samples = pix.samples
    nonwhite = sum(
        1 for i in range(0, len(samples), pix.n) if samples[i : i + 3] != b"\xff\xff\xff"
    )
    fraction = nonwhite / (pix.width * pix.height)
    rendered.close()
    assert fraction > 0.5, f"page rendered nearly blank ({fraction:.2f}) — over-redacted"

    # ...and the sensitive text is gone.
    assert "002010077777777771" not in open_pdf(out).pages[0].extract_text()
