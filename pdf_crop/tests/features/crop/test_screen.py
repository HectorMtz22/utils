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
