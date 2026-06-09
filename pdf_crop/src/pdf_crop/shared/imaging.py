"""Thin helpers over PyMuPDF (`fitz`) for image-layer detection/redaction.

These let a feature render a page to a raster, locate something in image-pixel
space (e.g. a QR code), map that box back to PDF points, and apply a *true*
redaction that removes the underlying content rather than drawing a box over it.
"""

import fitz
from PIL import Image


def render_page(page, dpi):
    """Render a `fitz.Page` to a PIL RGB image at `dpi`."""
    pix = page.get_pixmap(dpi=dpi)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def img_rect_to_pdf(rect, dpi):
    """Map an image-pixel bbox (x0, y0, x1, y1) at `dpi` to a PDF-point Rect.

    A page rendered at `dpi` has `dpi/72` pixels per PDF point, so the inverse
    scale is `72/dpi`.
    """
    scale = 72 / dpi
    x0, y0, x1, y1 = rect
    return fitz.Rect(x0 * scale, y0 * scale, x1 * scale, y1 * scale)


def redact_rects(doc, page_index, rects, *, fill=(1, 1, 1)):
    """Truly redact each PDF-point `rect` on `doc[page_index]`.

    Adds a redaction annotation per rect and applies them, which *removes* the
    underlying image/text content covered by the box (not merely a drawn cover),
    filling the area with `fill` (white by default).
    """
    page = doc[page_index]
    for rect in rects:
        page.add_redact_annot(rect, fill=fill)
    page.apply_redactions()
