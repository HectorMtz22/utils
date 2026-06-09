import fitz
import pytest

from pdf_crop.app import PdfCropApp
from pdf_crop.features.crop.screen import CropScreen
import zbar_skip


def test_screen_default_sanitize_false(three_page_pdf):
    screen = CropScreen(three_page_pdf)
    assert screen._sanitize_default is False


def test_screen_accepts_sanitize_kwarg(three_page_pdf):
    screen = CropScreen(three_page_pdf, sanitize=True)
    assert screen._sanitize_default is True


def test_app_threads_sanitize_to_screen(three_page_pdf):
    app = PdfCropApp(three_page_pdf, sanitize=True)
    assert app._sanitize is True


async def test_list_metadata_button_renders_inventory(pdf_with_metadata):
    app = PdfCropApp(pdf_with_metadata)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        await pilot.click("#list_metadata_btn")
        await pilot.pause()
        msg = str(screen.query_one("#metadata_msg").content)
        assert "Metadata:" in msg
        assert "total" in msg


async def test_sanitize_checkbox_strips_on_crop(pdf_with_metadata):
    from pdf_crop.features.sanitize.service import inventory
    from pdf_crop.shared.pdf_io import open_pdf

    app = PdfCropApp(pdf_with_metadata)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#sanitize_chk").value = True
        await pilot.pause()
        await pilot.click("#crop_btn")
        await pilot.pause()

    out = pdf_with_metadata.with_name("with_metadata_xmp_cropped.pdf")
    assert inventory(open_pdf(out)).total() == 0


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


async def test_crop_runs_ocr_second_pass_with_selected_categories(text_pdf_factory, monkeypatch):
    # When #ocr_chk is ticked, the OCR second pass runs over the written file
    # using the selected category checkboxes + names input.
    from pdf_crop.features.crop import command

    calls = {}

    def fake_ocr(dest, *, categories, names):
        calls["dest"] = dest
        calls["categories"] = categories
        calls["names"] = names
        return 0

    monkeypatch.setattr(command, "_redact_ocr_in_place", fake_ocr)

    src = text_pdf_factory(["some text"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#ocr_chk").value = True
        screen.query_one("#cat_clabe_chk").value = True
        screen.query_one("#names_input").value = "Jane Doe"
        screen.query_one("#cat_name_chk").value = True
        await pilot.pause()
        await pilot.click("#crop_btn")
        await pilot.pause()

    assert calls["categories"] == {"clabe", "name"}
    assert calls["names"] == ["Jane Doe"]


async def test_crop_shows_error_on_ocr_second_pass_failure(text_pdf_factory, monkeypatch):
    # An OCR/tesseract failure in the second pass must surface as the red error
    # message (translated to PdfCropError), not an uncaught traceback.
    from pdf_crop.features.ocr_redact import service as ocr_service

    def boom(*a, **k):
        raise ValueError("tesseract failure")

    monkeypatch.setattr(ocr_service, "scan", boom)

    src = text_pdf_factory(["no ocr here, scan is faked"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#ocr_chk").value = True
        await pilot.pause()
        await pilot.click("#crop_btn")
        await pilot.pause()
        error = str(screen.query_one("#error_msg").content)
        assert "OCR" in error or "redaction failed" in error


async def test_scan_shows_error_on_qr_preview_failure(text_pdf_factory, monkeypatch):
    # A decode/imaging failure while scanning QR for the preview must surface as
    # the red error message, not crash the TUI.
    from pdf_crop.features.qr_redact import service as qr_service

    def boom(*a, **k):
        raise ValueError("pyzbar decode failure")

    monkeypatch.setattr(qr_service, "scan", boom)

    src = text_pdf_factory(["no real qr here, scan is faked"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#redact_qr_chk").value = True
        await pilot.pause()
        await pilot.click("#scan_btn")
        await pilot.pause()
        error = str(screen.query_one("#error_msg").content)
        assert "QR" in error or "scan failed" in error


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
