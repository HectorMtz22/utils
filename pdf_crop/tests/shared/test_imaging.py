import fitz

from pdf_crop.shared import imaging
import zbar_skip


def test_img_rect_to_pdf_scales_by_72_over_dpi():
    # At 144 dpi, image pixels are exactly 2x PDF points, so the mapping back
    # divides by 2 (72/144).
    rect = imaging.img_rect_to_pdf((100, 200, 300, 400), dpi=144)
    assert rect == fitz.Rect(50, 100, 150, 200)


def test_img_rect_to_pdf_identity_at_72_dpi():
    rect = imaging.img_rect_to_pdf((10, 20, 30, 40), dpi=72)
    assert rect == fitz.Rect(10, 20, 30, 40)


pytestmark = zbar_skip.SKIP


def _decode_page(doc, page_index, dpi):
    from PIL import Image
    from pyzbar.pyzbar import decode

    pix = doc[page_index].get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return decode(img)


def test_render_page_produces_a_decodable_image(qr_pdf_factory):
    from PIL import Image
    from pyzbar.pyzbar import decode

    src = qr_pdf_factory(["CLABE002010077777777771"])
    doc = fitz.open(str(src))
    img = imaging.render_page(doc[0], dpi=200)
    assert isinstance(img, Image.Image)
    assert [r.data for r in decode(img)] == [b"CLABE002010077777777771"]


def test_redact_rects_truly_removes_image_content(qr_pdf_factory):
    src = qr_pdf_factory(["CLABE002010077777777771"])
    doc = fitz.open(str(src))
    # The whole QR sits inside the 100..250pt rect it was inserted at; redact it.
    imaging.redact_rects(doc, 0, [fitz.Rect(90, 90, 260, 260)])
    assert _decode_page(doc, 0, dpi=200) == []

