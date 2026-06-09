"""Detect and redact QR codes / barcodes in a PDF's image layer.

Mexican bank statements embed CLABE / account / payment data in QR codes and
barcodes that the text-layer detectors never see. This runs as a second pass
over an already-written (cropped) file: render each page, decode every symbol
with pyzbar, and apply a TRUE PyMuPDF redaction over each detected box so the
underlying image content is removed, not merely covered.
"""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import fitz

from pdf_crop.shared import imaging

# Codes are small; 200 dpi is enough for pyzbar to decode QR/EAN/Code128
# reliably without making rendering slow.
DPI = 200


@dataclass(frozen=True)
class QrCode:
    page: int           # 1-indexed page number
    symbology: str      # pyzbar type, e.g. "QRCODE", "EAN13", "CODE128"
    payload: str        # decoded text
    rect: fitz.Rect     # bounding box in PDF points


@dataclass
class QrFindings:
    codes: list[QrCode] = field(default_factory=list)

    def summary(self):
        return dict(Counter(c.symbology for c in self.codes))


def scan(path: Path, pages=None) -> QrFindings:
    """Scan 1-indexed `pages` of the PDF at `path` for QR codes / barcodes.

    `pages=None` scans every page.
    """
    from pyzbar.pyzbar import decode

    findings = QrFindings()
    doc = fitz.open(str(path))
    try:
        if pages is None:
            pages = range(1, doc.page_count + 1)
        for page_number in pages:
            image = imaging.render_page(doc[page_number - 1], dpi=DPI)
            for sym in decode(image):
                r = sym.rect  # left, top, width, height in image pixels
                rect = imaging.img_rect_to_pdf(
                    (r.left, r.top, r.left + r.width, r.top + r.height), dpi=DPI
                )
                findings.codes.append(
                    QrCode(
                        page=page_number,
                        symbology=sym.type,
                        payload=sym.data.decode("utf-8", "replace"),
                        rect=rect,
                    )
                )
    finally:
        doc.close()
    return findings


def redact(path: Path, dest: Path, findings: QrFindings) -> int:
    """Redact every detected code in `findings` from `path`, saving to `dest`.

    Returns the number of codes redacted. With no findings this just writes a
    cleaned copy. Uses PyMuPDF true redaction (content is removed, not covered).
    """
    doc = fitz.open(str(path))
    try:
        by_page: dict[int, list[fitz.Rect]] = {}
        for code in findings.codes:
            by_page.setdefault(code.page, []).append(code.rect)
        for page_number, rects in by_page.items():
            imaging.redact_rects(doc, page_number - 1, rects)
        doc.save(str(dest), garbage=4, deflate=True)
    finally:
        doc.close()
    return len(findings.codes)
