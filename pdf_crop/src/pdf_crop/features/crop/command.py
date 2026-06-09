from pathlib import Path
import os
import sys

from pdf_crop.shared import ranges, pdf_io, output_path
from pdf_crop.shared.errors import PdfCropError, QrRedactionFailed

from .service import crop_pdf


def run(
    src: Path,
    range_expr: str | None,
    *,
    sanitize: bool = False,
    strip_metadata: bool = False,
    redact_qr: bool = False,
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
        result = crop_pdf(reader, pages, dest, sanitize=sanitize)
        if redact_qr:
            _redact_qr_in_place(dest)
    except PdfCropError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(result)
    return 0


def _redact_qr_in_place(dest: Path) -> int:
    """Second pass: scan the written PDF for QR/barcodes and redact them all.

    PyMuPDF can't garbage-collect a save back over the source, so redact into a
    sibling temp file and atomically replace `dest`. Returns the number removed.
    """
    from pdf_crop.features.qr_redact import service as qr_service

    try:
        total = pdf_io.page_count(pdf_io.open_pdf(dest))
        findings = qr_service.scan(dest, list(range(1, total + 1)))
        if not findings.codes:
            return 0
        tmp = dest.with_name(f"{dest.stem}.qr-tmp.pdf")
        try:
            qr_service.redact(dest, tmp, findings)
            os.replace(tmp, dest)  # atomic on success; clobbers temp
        finally:
            tmp.unlink(missing_ok=True)  # no orphan if redact/replace raised
    except PdfCropError:
        raise
    except Exception as e:  # fitz/pyzbar render or decode failure
        raise QrRedactionFailed(f"QR/barcode redaction failed: {e}") from e
    return len(findings.codes)
