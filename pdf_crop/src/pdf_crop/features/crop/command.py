from pathlib import Path
import os
import sys

from pdf_crop.features.redact import service as redact_service
from pdf_crop.shared import ranges, pdf_io, output_path
from pdf_crop.shared.errors import PdfCropError, QrRedactionFailed, OcrRedactionFailed

# Categories the OCR pass scans by default from the CLI when no --redact/--names
# was given. `name` needs a names list, so it's omitted from this legacy default
# (an explicit --redact/--names selection overrides it — see run()).
OCR_CLI_CATEGORIES = {"clabe", "account", "card", "rfc", "curp", "address"}


def run(
    src: Path,
    range_expr: str | None,
    *,
    sanitize: bool = False,
    strip_metadata: bool = False,
    redact_qr: bool = False,
    ocr: bool = False,
    output: str | None = None,
    categories: set[str] | None = None,
    names: list[str] | None = None,
    dry_run: bool = False,
) -> int:
    """Crop entry point. If range_expr is None, launch the TUI; otherwise direct mode.

    `strip_metadata` is a deprecated alias of `sanitize`. `output` is the raw
    --output value (folder, exact filename, or both); see output_path.resolve.
    `categories` are the parsed --redact categories and `names` the --names
    literals; text-layer redaction runs iff their union (with `name` implied by a
    non-empty `names`) is non-empty.
    """
    sanitize = sanitize or strip_metadata
    if range_expr is None:
        from pdf_crop.app import PdfCropApp
        return PdfCropApp(src, sanitize=sanitize, output=output).run() or 0

    categories = set(categories or ())
    names = list(names or ())
    # A non-empty --names implies the `name` category — detectors.detect gates the
    # entire name branch behind `"name" in categories`, so without this --names
    # would be silently ignored.
    effective = categories | ({"name"} if names else set())

    # OCR source: the effective selection when the user asked for redaction,
    # else the legacy automatic categories with no names (backward-compat).
    if effective:
        ocr_cats, ocr_names = effective, names
    else:
        ocr_cats, ocr_names = OCR_CLI_CATEGORIES, []

    try:
        reader = pdf_io.open_pdf(src)
        total = pdf_io.page_count(reader)
        pages = ranges.parse(range_expr, total)
        if dry_run:
            # Preview only: scan the SOURCE and report. Never resolve an output
            # path (that would mkdir), build a writer, or open a file for write.
            return _print_dry_run(
                reader,
                src,
                pages,
                effective=effective,
                names=names,
                redact_qr=redact_qr,
                ocr=ocr,
                ocr_cats=ocr_cats,
                ocr_names=ocr_names,
            )
        dest = output_path.resolve(src, output)

        writer = pdf_io.build_subset(reader, pages, sanitize=sanitize)
        breakdown: dict[str, int] = {}
        if effective:
            # Scan first for the per-category summary, then redact the writer in
            # place (same pages, so counts agree — no double redaction).
            breakdown = redact_service.scan(
                reader, pages, categories=effective, names=names
            ).summary()
            redact_service.redact(writer, categories=effective, names=names)
        with dest.open("wb") as f:
            writer.write(f)
        qr_removed = _redact_qr_in_place(dest) if redact_qr else 0
        ocr_removed = (
            _redact_ocr_in_place(dest, categories=ocr_cats, names=ocr_names)
            if ocr
            else 0
        )
    except PdfCropError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    _print_result(dest, breakdown, qr_removed, ocr_removed)
    return 0


def _print_result(dest, breakdown: dict[str, int], qr_removed: int, ocr_removed: int) -> None:
    """Report the outcome on stdout.

    When nothing was redacted, print just the dest path (the legacy terse output
    that tests pin). Otherwise print a one-line redaction summary.
    """
    text_total = sum(breakdown.values())
    if not (text_total or qr_removed or ocr_removed):
        print(dest)
        return

    parts = []
    if breakdown:
        parts.append(", ".join(f"{n} {cat}" for cat, n in sorted(breakdown.items())))
    if qr_removed:
        parts.append(f"{qr_removed} QR")
    if ocr_removed:
        parts.append(f"{ocr_removed} OCR")
    total = text_total + qr_removed + ocr_removed
    print(f"Redacted {total} items: {'; '.join(parts)} → {dest}")


def _print_dry_run(
    reader,
    src: Path,
    pages,
    *,
    effective: set[str],
    names: list[str],
    redact_qr: bool,
    ocr: bool,
    ocr_cats,
    ocr_names,
) -> int:
    """Preview what redaction WOULD remove from `pages` of the source; write nothing.

    Scans only the sections whose option is active (text/QR/OCR) and prints a
    terse report. Mirrors the error translation of the real passes: a
    non-PdfCropError QR/OCR failure becomes a PdfCropError so run()'s handler
    turns it into `error:` + exit 2 instead of a traceback. Returns 0.
    """
    if not (effective or redact_qr or ocr):
        print("Dry run: no redaction options selected (nothing to preview).")
        return 0

    print("Scan (no output written):")

    if effective:
        findings = redact_service.scan(reader, pages, categories=effective, names=names)
        summary = findings.summary()
        if summary:
            parts = ", ".join(f"{n} {cat}" for cat, n in sorted(summary.items()))
            total = sum(summary.values())
            print(f"  text: {parts} ({total} total)")
        else:
            print("  text: none found")
        if findings.skipped_pages:
            skipped = ", ".join(str(p) for p in findings.skipped_pages)
            print(f"  pages skipped (no text layer): {skipped}")

    if redact_qr:
        from pdf_crop.features.qr_redact import service as qr_service

        try:
            qr_findings = qr_service.scan(src, pages)
        except PdfCropError:
            raise
        except Exception as e:  # zbar missing / fitz render / decode failure
            raise QrRedactionFailed(f"QR/barcode scan failed: {e}") from e
        codes = qr_findings.codes
        if codes:
            print(f"  QR: {len(codes)} code{'s' if len(codes) != 1 else ''}")
            for c in codes:
                print(f"    {c.symbology} {c.payload!r}")
        else:
            print("  QR: none found")

    if ocr:
        from pdf_crop.features.ocr_redact import service as ocr_service

        try:
            ocr_findings = ocr_service.scan(src, pages, categories=ocr_cats, names=ocr_names)
        except PdfCropError:
            raise
        except Exception as e:  # fitz render / tesseract failure
            raise OcrRedactionFailed(f"OCR scan failed: {e}") from e
        summary = ocr_findings.summary()
        if summary:
            parts = ", ".join(f"{n} {cat}" for cat, n in sorted(summary.items()))
            total = sum(summary.values())
            print(f"  OCR: {parts} ({total} total)")
        else:
            print("  OCR: none found")

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
    if not categories:
        return 0  # no redaction categories selected → nothing to detect
        # NB: a name-only selection is NOT skipped — names are now auto-detected
        # from label cues during the OCR pass even with an empty manual list.

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
