from pathlib import Path
import sys

from pdf_crop.shared import ranges, pdf_io, output_path
from pdf_crop.shared.errors import PdfCropError

from . import service as crop_service

# Categories the OCR pass scans by default from the CLI. `name` needs a names
# list the CLI can't provide, so it's omitted there (the TUI passes its own).
OCR_CLI_CATEGORIES = {"clabe", "card", "rfc", "curp"}


def run(
    src: Path,
    range_expr: str | None,
    *,
    sanitize: bool = False,
    strip_metadata: bool = False,
    redact_qr: bool = False,
    ocr: bool = False,
) -> int:
    """Crop entry point. If range_expr is None, launch the TUI; otherwise direct mode.

    `strip_metadata` is a deprecated alias of `sanitize`.
    """
    sanitize = sanitize or strip_metadata
    if range_expr is None:
        from pdf_crop.app import PdfCropApp
        return PdfCropApp(src, sanitize=sanitize).run() or 0

    try:
        reader = pdf_io.open_pdf(src)
        total = pdf_io.page_count(reader)
        pages = ranges.parse(range_expr, total)
        dest = output_path.resolve(src)
        # Reorder (UTILS-18): when QR/OCR is on, the fitz phase runs on the
        # original and pypdf finalizes last, so fitz never re-reads pypdf's
        # output. crop() handles both paths and guards the final page count.
        crop_service.crop(
            reader,
            src,
            pages,
            dest,
            sanitize=sanitize,
            redact_qr=redact_qr,
            ocr=ocr,
            categories=OCR_CLI_CATEGORIES if ocr else frozenset(),
            names=[],
        )
    except PdfCropError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(dest)
    return 0
