from pypdf import PdfWriter
from pypdf.generic import ArrayObject, ContentStream, NameObject, NumberObject, TextStringObject

from pdf_crop.shared.pdf_io import open_pdf
from pdf_crop.features.redact import detectors, text_layer


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


# ---------------------------------------------------------------------------
# Geometry-aware reconstruction (UTILS-22): table cells positioned by Tm with
# no break op between them must NOT fuse into one digit run.
# ---------------------------------------------------------------------------


def test_tm_positioned_cells_get_a_space(raw_content_stream):
    """Two same-line cells laid out by Tm (no break op) reconstruct with a space."""
    cs = raw_content_stream(
        b"BT /F1 12 Tf 1 0 0 1 72 720 Tm (12345) Tj "
        b"1 0 0 1 200 720 Tm (67890) Tj ET"
    )
    text, charmap = text_layer._walk(cs)
    assert text == "12345 67890"
    assert len(charmap) == len(text)


def test_tm_positioned_cells_both_numbers_detected(raw_content_stream):
    """The comma-separated Names field (and number detectors) match each cell."""
    cs = raw_content_stream(
        b"BT /F1 12 Tf 1 0 0 1 72 720 Tm (12345) Tj "
        b"1 0 0 1 200 720 Tm (67890) Tj ET"
    )
    text, _ = text_layer._walk(cs)
    assert detectors.detect(text, categories={"name"}, names=["12345"])
    assert detectors.detect(text, categories={"name"}, names=["67890"])


def test_tj_large_kern_inserts_space_small_kern_does_not(raw_content_stream):
    """A large TJ kerning gap separates groups; a small intra-number kern does not."""
    # gap = -nnum/1000 * font_size(12) * scale(1) -> -5000 => 60pt (>6 -> space)
    big = raw_content_stream(
        b"BT /F1 12 Tf 1 0 0 1 72 720 Tm [(12345) -5000 (67890)] TJ ET"
    )
    text_big, _ = text_layer._walk(big)
    assert text_big == "12345 67890"

    # -100 => 1.2pt (<6 -> no space): a contiguous value is preserved.
    small = raw_content_stream(
        b"BT /F1 12 Tf 1 0 0 1 72 720 Tm [(123) -100 (45678)] TJ ET"
    )
    text_small, _ = text_layer._walk(small)
    assert text_small == "12345678"
    assert detectors.detect(text_small, categories={"name"}, names=["12345678"])


def test_horizontal_only_td_is_a_space_not_a_newline(raw_content_stream):
    """A Td with dy=0 moving right is a same-line gap (space), never a row break."""
    cs = raw_content_stream(
        b"BT /F1 12 Tf 1 0 0 1 72 720 Tm (12345) Tj 128 0 Td (67890) Tj ET"
    )
    text, _ = text_layer._walk(cs)
    assert text == "12345 67890"
    assert "\n" not in text


def test_vertical_td_and_tstar_newline_separate_rows(raw_content_stream):
    """Td with dy!=0, and T*, separate rows with a newline."""
    td = raw_content_stream(
        b"BT /F1 12 Tf 1 0 0 1 72 720 Tm (row1) Tj 0 -20 Td (row2) Tj ET"
    )
    text_td, _ = text_layer._walk(td)
    assert text_td == "row1\nrow2"

    tstar = raw_content_stream(
        b"BT /F1 12 Tf 1 0 0 1 72 720 Tm 14 TL (row1) Tj T* (row2) Tj ET"
    )
    text_ts, _ = text_layer._walk(tstar)
    assert text_ts == "row1\nrow2"


def test_adjacent_tm_runs_at_pen_stay_contiguous(raw_content_stream):
    """One number drawn as two Tm runs with ~no gap stays a single value."""
    # First run "123" at x=72; 3 glyphs * 0.5em * 12 = 18pt -> pen at x=90.
    # Second Tm at x=90 (== pen) -> continuation, no separator.
    cs = raw_content_stream(
        b"BT /F1 12 Tf 1 0 0 1 72 720 Tm (123) Tj "
        b"1 0 0 1 90 720 Tm (45678) Tj ET"
    )
    text, _ = text_layer._walk(cs)
    assert text == "12345678"
    assert detectors.detect(text, categories={"name"}, names=["12345678"])


def test_clabe_in_adjacent_tm_cell_is_detected(raw_content_stream):
    """An 18-digit CLABE in a Tm cell next to another number is still detected."""
    cs = raw_content_stream(
        b"BT /F1 12 Tf 1 0 0 1 72 720 Tm (002010077777777771) Tj "
        b"1 0 0 1 400 720 Tm (9999) Tj ET"
    )
    text, _ = text_layer._walk(cs)
    matches = detectors.detect(text, categories={"clabe"}, names=[])
    assert any(m.text == "002010077777777771" for m in matches)


def test_charmap_length_matches_text_with_synthetic_separators(raw_content_stream):
    """len(charmap) == len(text) holds across spaces and newlines (synthetic)."""
    cs = raw_content_stream(
        b"BT /F1 12 Tf 1 0 0 1 72 720 Tm (12345) Tj "
        b"1 0 0 1 200 720 Tm (67890) Tj 0 -20 Td (33333) Tj ET"
    )
    text, charmap = text_layer._walk(cs)
    assert len(charmap) == len(text)
    assert " " in text and "\n" in text
    # Each inserted separator is synthetic and never deleted.
    for i, ch in enumerate(text):
        if ch in (" ", "\n"):
            assert charmap[i] == (-1, -1, -1)


def test_tm_cells_in_separate_bt_blocks_get_a_space(tmp_path):
    """A real reportlab page where each cell is its own BT…ET block (Tm only).

    This is the production shape: drawString emits one BT/Tf/Tm/Tj/T*/ET block per
    call. Stripping the T* leaves two Tm-positioned cells in adjacent blocks with
    no break op — the original fusion bug — and they must reconstruct with a space.
    """
    from reportlab.pdfgen.canvas import Canvas

    path = tmp_path / "table.pdf"
    c = Canvas(str(path))
    c.setFont("Helvetica", 12)
    c.drawString(72, 720, "12345")
    c.drawString(200, 720, "67890")
    c.showPage()
    c.save()

    page = open_pdf(path).pages[0]
    cs = text_layer._content_stream(page)
    cs.operations = [
        (o, op) for (o, op) in cs.operations if op not in (b"T*", b"Td", b"TD")
    ]
    text, charmap = text_layer._walk(cs)
    assert text == "12345 67890"
    assert len(charmap) == len(text)
    assert detectors.detect(text, categories={"name"}, names=["12345"])
    assert detectors.detect(text, categories={"name"}, names=["67890"])


def test_delete_one_fused_cell_keeps_neighbor(raw_content_stream, tmp_path):
    """Redacting one cell's number leaves the neighbouring cell intact."""
    cs = raw_content_stream(
        b"BT /F1 12 Tf 1 0 0 1 72 720 Tm (12345) Tj "
        b"1 0 0 1 200 720 Tm (67890) Tj ET"
    )
    w = PdfWriter()
    page = w.add_blank_page(width=600, height=800)
    page[NameObject("/Contents")] = cs

    text, _ = text_layer.page_text(page)
    start = text.index("67890")
    text_layer.delete_spans(page, [(start, start + 5)])

    text2, _ = text_layer.page_text(page)
    assert "67890" not in text2
    assert "12345" in text2


# ---------------------------------------------------------------------------
# Geometry-aware reconstruction: deliberate trade-offs the review flagged.
# ---------------------------------------------------------------------------


def test_spaced_account_matches_across_separate_tm_cells(raw_content_stream):
    """A cue-anchored value split across separate Tm cells is now matched.

    Geometry-aware spacing is deliberately recall-favouring for the cue-anchored
    "spaced" detectors: an account number split across separate table cells (each
    its own Tm) reconstructs with single spaces after the cue, so the account
    detector matches it. The old fused output "Cuenta0123456789" has no word
    boundary after the cue and matched nothing. Pins this intended behaviour (the
    precision trade-off is noted in the PR).
    """
    cs = raw_content_stream(
        b"BT /F1 12 Tf 1 0 0 1 72 720 Tm (Cuenta) Tj "
        b"1 0 0 1 160 720 Tm (012345) Tj "
        b"1 0 0 1 230 720 Tm (6789) Tj ET"
    )
    text, _ = text_layer._walk(cs)
    assert text == "Cuenta 012345 6789"
    matches = detectors.detect(text, categories={"account"}, names=[])
    assert [m.text for m in matches] == ["012345 6789"]


def test_leftward_same_line_cell_is_a_known_fusion_limitation(raw_content_stream):
    """Right-to-left / leftward cells on one baseline fuse — a documented limit.

    The separator logic assumes left-to-right column order: a run whose Tm origin
    sits at or left of where the previous run's pen ended on the SAME baseline is
    treated as continuation, so the two cells fuse back into one digit run. This
    pins that known limitation (see the comment in `_walk`'s gap_sep).
    """
    cs = raw_content_stream(
        b"BT /F1 12 Tf 1 0 0 1 400 720 Tm (12345) Tj "
        b"1 0 0 1 72 720 Tm (67890) Tj ET"
    )
    text, _ = text_layer._walk(cs)
    assert text == "1234567890"  # fused — known limitation, not a regression
