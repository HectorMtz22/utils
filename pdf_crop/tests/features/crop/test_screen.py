import pytest

from pdf_crop.app import PdfCropApp
from pdf_crop.features.crop.screen import CropScreen


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
