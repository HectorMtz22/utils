from pathlib import Path
import os
import sys

from pdf_crop.shared import ranges, pdf_io, output_path
from pdf_crop.shared.errors import PdfCropError, QrRedactionFailed, OcrRedactionFailed

from .service import crop_pdf

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
        result = crop_pdf(reader, pages, dest, sanitize=sanitize)
        if redact_qr:
            _redact_qr_in_place(dest)
        if ocr:
            _redact_ocr_in_place(dest, categories=OCR_CLI_CATEGORIES, names=[])
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
        findings = qr_service.scan(dest)
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


def _redact_ocr_in_place(dest: Path, *, categories, names) -> int:
    """Second pass: OCR-scan the written PDF for sensitive text and redact it.

    Mirrors `_redact_qr_in_place`: redact into a sibling temp file and atomically
    replace `dest` (PyMuPDF can't garbage-collect a save back over the source).
    Returns the number of matches removed.
    """
    if categories <= {"name"} and not names:
        return 0  # nothing OCR can detect → skip the costly render/OCR pass

    from pdf_crop.features.ocr_redact import service as ocr_service

    try:
        findings = ocr_service.scan(dest, categories=categories, names=names)
        if not findings.matches:
            return 0
        tmp = dest.with_name(f"{dest.stem}.ocr-tmp.pdf")
        try:
            ocr_service.redact(dest, tmp, findings)
            os.replace(tmp, dest)  # atomic on success; clobbers temp
        finally:
            tmp.unlink(missing_ok=True)  # no orphan if redact/replace raised
    except PdfCropError:
        raise
    except Exception as e:  # fitz render or tesseract/OCR failure
        raise OcrRedactionFailed(f"OCR redaction failed: {e}") from e
    return len(findings.matches)
