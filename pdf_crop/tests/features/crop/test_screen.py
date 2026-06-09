import fitz
import pytest

from pdf_crop.app import PdfCropApp
from pdf_crop.features.crop.screen import CropScreen
import zbar_skip


def test_screen_default_strip_metadata_false(three_page_pdf):
    screen = CropScreen(three_page_pdf)
    assert screen._strip_metadata_default is False


def test_screen_accepts_strip_metadata_kwarg(three_page_pdf):
    screen = CropScreen(three_page_pdf, strip_metadata=True)
    assert screen._strip_metadata_default is True


def test_app_threads_strip_metadata_to_screen(three_page_pdf):
    app = PdfCropApp(three_page_pdf, strip_metadata=True)
    assert app._strip_metadata is True


async def test_scan_then_redact_writes_clean_pdf(text_pdf_factory):
    src = text_pdf_factory(["CLABE 002010077777777771 fin"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#cat_clabe_chk").value = True
        await pilot.pause()
        await pilot.click("#scan_btn")
        await pilot.pause()
        preview = str(screen.query_one("#preview_msg").content)
        assert "1" in preview
        assert screen.query_one("#apply_redaction_chk").disabled is False
        screen.query_one("#apply_redaction_chk").value = True
        await pilot.click("#crop_btn")
        await pilot.pause()

    from pdf_crop.shared.pdf_io import open_pdf
    out = next(p for p in src.parent.glob("*_cropped*.pdf"))
    assert "002010077777777771" not in open_pdf(out).pages[0].extract_text()


async def test_scan_no_matches_keeps_apply_disabled(text_pdf_factory):
    src = text_pdf_factory(["nothing to see here"])
    app = PdfCropApp(src)
    async with app.run_test() as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#cat_clabe_chk").value = True
        await pilot.pause()
        await pilot.click("#scan_btn")
        await pilot.pause()
        assert screen.query_one("#apply_redaction_chk").disabled is True
        assert "nothing to redact" in str(screen.query_one("#preview_msg").content)


@zbar_skip.SKIP
async def test_scan_lists_found_qr_codes(qr_pdf_factory):
    src = qr_pdf_factory(["CLABE002010077777777771"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#redact_qr_chk").value = True
        await pilot.pause()
        await pilot.click("#scan_btn")
        await pilot.pause()
        preview = str(screen.query_one("#preview_msg").content)
        # The decoded payload is exposed so the user can verify it's their data.
        assert "CLABE002010077777777771" in preview


async def test_crop_shows_error_on_qr_second_pass_failure(text_pdf_factory, monkeypatch):
    # A decode/imaging failure in the QR second pass must surface as the red
    # error message (translated to PdfCropError), not an uncaught traceback.
    from pdf_crop.features.qr_redact import service as qr_service

    findings = qr_service.QrFindings()
    findings.codes.append(
        qr_service.QrCode(page=1, symbology="QRCODE", payload="x", rect=None)
    )
    monkeypatch.setattr(qr_service, "scan", lambda *a, **k: findings)

    def boom(*a, **k):
        raise ValueError("pyzbar decode failure")

    monkeypatch.setattr(qr_service, "redact", boom)

    src = text_pdf_factory(["no real qr here, redact is faked"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#redact_qr_chk").value = True
        await pilot.pause()
        await pilot.click("#crop_btn")
        await pilot.pause()
        error = str(screen.query_one("#error_msg").content)
        assert "QR" in error or "redaction failed" in error


@zbar_skip.SKIP
async def test_crop_with_redact_qr_removes_qr_from_output(qr_pdf_factory):
    from PIL import Image
    from pyzbar.pyzbar import decode

    src = qr_pdf_factory(["CLABE002010077777777771"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#redact_qr_chk").value = True
        await pilot.pause()
        await pilot.click("#crop_btn")
        await pilot.pause()

    out = next(p for p in src.parent.glob("*_cropped*.pdf"))
    doc = fitz.open(str(out))
    pix = doc[0].get_pixmap(dpi=200)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    assert decode(img) == []
