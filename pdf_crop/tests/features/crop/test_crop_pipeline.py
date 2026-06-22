"""End-to-end tests for the reordered crop pipeline (UTILS-18).

The crop pipeline is cross-engine when QR/OCR redaction is requested: pypdf
writes the page subset, fitz reopens it for image-layer redaction. On some real
PDFs fitz mis-parses pypdf's output and silently lands on the wrong pages. The
fix runs the fitz phase on the *original* (via `fitz.select`) and lets pypdf
finalize last, so fitz never re-reads pypdf's output.

These tests pin the resulting invariants:
  * identity — the output pages are exactly the selected markers, in order,
    even for a non-contiguous selection with QR + OCR + sanitize together;
  * guard — a stage that drops a page makes the crop raise (no silent short file);
  * invariant — fitz is never asked to open the pypdf-written final `dest`.
"""

import io

import fitz
import pytest
from pypdf import PdfWriter

from pdf_crop.features.crop import command
from pdf_crop.shared.errors import PdfCropError
from pdf_crop.shared.pdf_io import open_pdf, page_count
from pdf_crop.features.redact import text_layer

import zbar_skip
import tesseract_skip

CATS = {"clabe", "card", "rfc", "curp"}


def _marker_pdf(tmp_path, n):
    """An n-page PDF, page k carrying extractable text 'PAGEMARKER-k'.

    Built with PyMuPDF text insertion so each page has a real (extractable)
    text layer the crop output can be checked against by identity, not count.
    """
    doc = fitz.open()
    for k in range(1, n + 1):
        page = doc.new_page(width=595, height=842)  # A4
        page.insert_text((72, 72), f"PAGEMARKER-{k}", fontsize=24)
    path = tmp_path / "markers.pdf"
    doc.save(str(path))
    doc.close()
    return path


def _qr_marker_pdf(tmp_path, n, *, payloads=None):
    """An n-page PDF: page k has text 'PAGEMARKER-k' AND a QR code.

    `payloads[k-1]` is the QR payload for page k (defaults to 'QR-PAGE-k'), so a
    cropped page's QR identity can be checked too.
    """
    import segno

    if payloads is None:
        payloads = [f"QR-PAGE-{k}" for k in range(1, n + 1)]
    doc = fitz.open()
    for k in range(1, n + 1):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"PAGEMARKER-{k}", fontsize=24)
        buf = io.BytesIO()
        segno.make(payloads[k - 1], error="h").save(buf, kind="png", scale=10, border=4)
        page.insert_image(fitz.Rect(100, 100, 250, 250), stream=buf.getvalue())
    path = tmp_path / "qr_markers.pdf"
    doc.save(str(path))
    doc.close()
    return path


def _page_markers(path):
    """The 'PAGEMARKER-k' tokens extracted from each page of `path`, in order."""
    reader = open_pdf(path)
    out = []
    for page in reader.pages:
        text, _ = text_layer.page_text(page)
        out.append("".join(text.split()))  # collapse whitespace for a clean match
    return out


def _decode_qr(path):
    """Every QR payload decoded from `path`, page by page (flattened)."""
    from PIL import Image
    from pyzbar.pyzbar import decode

    doc = fitz.open(str(path))
    payloads = []
    try:
        for i in range(doc.page_count):
            pix = doc[i].get_pixmap(dpi=200)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            payloads.extend(r.data.decode() for r in decode(img))
    finally:
        doc.close()
    return payloads


# --- identity: CLI run() ------------------------------------------------------


@zbar_skip.SKIP
def test_cli_crop_qr_sanitize_keeps_selected_pages_in_order(tmp_path, capsys):
    """Non-contiguous QR + sanitize crop: output pages are exactly the selected
    markers in order, and the QR codes were removed."""
    src = _qr_marker_pdf(tmp_path, 8)
    rc = command.run(src, "1,3,5", sanitize=True, redact_qr=True)
    assert rc == 0

    out = src.with_name("qr_markers_cropped.pdf")
    assert page_count(open_pdf(out)) == 3
    markers = ["".join(m.split()) for m in _page_markers(out)]
    assert markers == ["PAGEMARKER-1", "PAGEMARKER-3", "PAGEMARKER-5"]
    # QR redaction actually happened: nothing decodes off the output.
    assert _decode_qr(out) == []


@zbar_skip.SKIP
@tesseract_skip.SKIP
def test_cli_crop_qr_ocr_sanitize_keeps_selected_pages_in_order(tmp_path):
    """QR + OCR + sanitize together over a non-contiguous selection: identity of
    the output pages is preserved (count + markers, in order)."""
    src = _qr_marker_pdf(tmp_path, 8)
    rc = command.run(src, "1,3,5", sanitize=True, redact_qr=True, ocr=True)
    assert rc == 0

    out = src.with_name("qr_markers_cropped.pdf")
    markers = ["".join(m.split()) for m in _page_markers(out)]
    assert markers == ["PAGEMARKER-1", "PAGEMARKER-3", "PAGEMARKER-5"]


# --- identity: TUI worker -----------------------------------------------------


@zbar_skip.SKIP
async def test_tui_crop_qr_sanitize_keeps_selected_pages_in_order(tmp_path):
    from pdf_crop.app import PdfCropApp

    src = _qr_marker_pdf(tmp_path, 8)
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1,3,5"
        screen.query_one("#redact_qr_chk").value = True
        screen.query_one("#sanitize_chk").value = True
        await pilot.pause()
        await pilot.click("#crop_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()

    out = next(p for p in src.parent.glob("*_cropped*.pdf"))
    markers = ["".join(m.split()) for m in _page_markers(out)]
    assert markers == ["PAGEMARKER-1", "PAGEMARKER-3", "PAGEMARKER-5"]
    assert _decode_qr(out) == []


# --- guard: a dropped page must raise -----------------------------------------


@zbar_skip.SKIP
def test_cli_crop_raises_when_a_stage_drops_a_page(tmp_path, monkeypatch):
    """If a redaction stage silently drops a page, the count guard raises a
    PdfCropError rather than leaving a wrong-length file."""
    from pdf_crop.features.qr_redact import service as qr_service

    src = _qr_marker_pdf(tmp_path, 8)

    real_redact = qr_service.redact

    def dropping_redact(path, dest, findings):
        # Redact normally, then re-save dropping the last page so the result is
        # one page short — exactly the "wrong file" failure the guard must catch.
        real_redact(path, dest, findings)
        doc = fitz.open(str(dest))
        try:
            doc.delete_page(doc.page_count - 1)
            tmp = dest.with_name(dest.stem + ".short.pdf")
            doc.save(str(tmp))
        finally:
            doc.close()
        tmp.replace(dest)
        return len(findings.codes)

    monkeypatch.setattr(qr_service, "redact", dropping_redact)

    rc = command.run(src, "1,3,5", redact_qr=True)
    assert rc == 2  # CLI translates PdfCropError to exit code 2


def test_crop_pipeline_guard_raises_on_wrong_page_count(tmp_path, monkeypatch):
    """The guard is engine-agnostic: a final file with the wrong page count
    raises PdfCropError even when no exception came from a stage. Uses a
    pypdf-only path (no QR/OCR) so it runs without zbar/tesseract."""
    from pdf_crop.features.crop import service as crop_service
    from pdf_crop.shared import pdf_io

    src = _marker_pdf(tmp_path, 8)
    reader = open_pdf(src)
    dest = tmp_path / "guarded_cropped.pdf"

    # Make the writer emit one fewer page than requested.
    real_build = pdf_io.build_subset

    def short_build(reader, pages, **kw):
        return real_build(reader, pages[:-1], **kw)

    monkeypatch.setattr(crop_service.pdf_io, "build_subset", short_build)

    with pytest.raises(PdfCropError):
        crop_service.crop(reader, src, [1, 3, 5], dest, sanitize=False)


# --- invariant: fitz never opens the pypdf-written final dest -----------------


@zbar_skip.SKIP
def test_fitz_never_reopens_pypdf_final_output(tmp_path, monkeypatch):
    """Regression guard for the actual fix: with QR + sanitize on, every
    fitz.open call targets the source or an intermediate — never the final
    pypdf-written `dest`."""
    src = _qr_marker_pdf(tmp_path, 8)
    dest = src.with_name("qr_markers_cropped.pdf")

    opened = []
    real_open = fitz.open

    def spy_open(arg=None, *a, **k):
        if arg is not None:
            opened.append(str(arg))
        return real_open(arg, *a, **k)

    monkeypatch.setattr(fitz, "open", spy_open)

    rc = command.run(src, "1,3,5", sanitize=True, redact_qr=True)
    assert rc == 0
    assert dest.exists()

    # fitz opened things (source + intermediates) but never the final dest.
    assert opened, "expected fitz to open the source/intermediates"
    assert str(dest) not in opened
