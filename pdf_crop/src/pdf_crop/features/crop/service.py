from pathlib import Path
import os

import fitz
from pypdf import PdfReader

from pdf_crop.shared import pdf_io
from pdf_crop.shared.errors import PdfCropError, QrRedactionFailed, OcrRedactionFailed


def crop(
    reader: PdfReader,
    src: Path,
    pages: list[int],
    dest: Path,
    *,
    sanitize: bool = False,
    apply_redaction: bool = False,
    redact_qr: bool = False,
    ocr: bool = False,
    categories=frozenset(),
    names=(),
    redactor=None,
) -> dict:
    """Crop `pages` (1-indexed) of `src` into `dest`, applying redaction passes.

    Ordering matters (UTILS-18). When QR/OCR redaction is requested the pipeline
    is cross-engine, so fitz must only ever read the *original* `src` or its own
    output — never pypdf's. So:

      1. fitz phase on the original — `fitz.open(src)` + `select(pages)` gives the
         subset in selection order; QR and/or OCR redaction chain over it through
         intermediates.
      2. pypdf finalize — only if `sanitize`/`apply_redaction`: open the fitz
         intermediate, sanitize and/or text-layer redact, write `dest`. If
         neither, the fitz intermediate *becomes* `dest` (no needless pypdf hop).

    When neither QR nor OCR is requested, the pure-pypdf path is used (`reader`
    already opens `src`). Either way the final `dest` is guarded to have exactly
    `len(pages)` pages — identity is guaranteed by construction (select() order +
    each engine preserving page order), so only the count is checked.

    `redactor` is the text-layer redact callable (injected by the caller so the
    feature stays decoupled); it's only needed when `apply_redaction` is set.
    Returns counts: {"redacted", "qr_removed", "ocr_removed"}.
    """
    counts = {"redacted": 0, "qr_removed": 0, "ocr_removed": 0}

    if not (redact_qr or ocr):
        # Common case: pure pypdf. build_subset over the original reader.
        writer = pdf_io.build_subset(reader, pages, sanitize=sanitize)
        if apply_redaction and redactor is not None:
            counts["redacted"] = redactor(writer, categories=categories, names=names)
        with dest.open("wb") as f:
            writer.write(f)
        _assert_page_count(dest, len(pages))
        return counts

    # Cross-engine path: fitz first (on the original), pypdf last.
    intermediate = _fitz_subset(src, pages, dest)
    try:
        if redact_qr:
            counts["qr_removed"] = _redact_qr_chain(intermediate)
        if ocr:
            counts["ocr_removed"] = _redact_ocr_chain(
                intermediate, categories=categories, names=names
            )
        if sanitize or apply_redaction:
            # pypdf finalize: the intermediate is already the subset (in order),
            # so take all its pages — no re-selection.
            inter_reader = pdf_io.open_pdf(intermediate)
            all_pages = list(range(1, pdf_io.page_count(inter_reader) + 1))
            writer = pdf_io.build_subset(inter_reader, all_pages, sanitize=sanitize)
            if apply_redaction and redactor is not None:
                counts["redacted"] = redactor(
                    writer, categories=categories, names=names
                )
            with dest.open("wb") as f:
                writer.write(f)
            final_engine = "pypdf"
        else:
            os.replace(intermediate, dest)
            final_engine = "fitz"
    finally:
        Path(intermediate).unlink(missing_ok=True)

    _assert_page_count(dest, len(pages), engine=final_engine)
    return counts


def _fitz_subset(src: Path, pages: list[int], dest: Path) -> Path:
    """fitz.open(src) + select(pages) → a sibling intermediate (subset, in order)."""
    out = dest.with_name(f"{dest.stem}.fitz-tmp.pdf")
    doc = fitz.open(str(src))
    try:
        doc.select([p - 1 for p in pages])
        doc.save(str(out), garbage=4, deflate=True)
    finally:
        doc.close()
    return out


def _redact_qr_chain(path: Path) -> int:
    """Scan `path` for QR/barcodes and redact them in place. Returns the count.

    `path` is the fitz subset (re-indexed 1..N), so scan every page (pages=None).
    """
    from pdf_crop.features.qr_redact import service as qr_service

    try:
        findings = qr_service.scan(path)
        if not findings.codes:
            return 0
        tmp = path.with_name(f"{path.stem}.qr-tmp.pdf")
        try:
            qr_service.redact(path, tmp, findings)
            os.replace(tmp, path)  # atomic on success; clobbers temp
        finally:
            tmp.unlink(missing_ok=True)  # no orphan if redact/replace raised
    except PdfCropError:
        raise
    except Exception as e:  # fitz/pyzbar render or decode failure
        raise QrRedactionFailed(f"QR/barcode redaction failed: {e}") from e
    return len(findings.codes)


def _redact_ocr_chain(path: Path, *, categories, names) -> int:
    """OCR-scan `path` for sensitive text and redact it in place. Returns count.

    `path` is the fitz subset (re-indexed 1..N), so scan every page (pages=None).
    """
    if categories <= {"name"} and not names:
        return 0  # nothing OCR can detect → skip the costly render/OCR pass

    from pdf_crop.features.ocr_redact import service as ocr_service

    try:
        findings = ocr_service.scan(path, categories=categories, names=names)
        if not findings.matches:
            return 0
        tmp = path.with_name(f"{path.stem}.ocr-tmp.pdf")
        try:
            ocr_service.redact(path, tmp, findings)
            os.replace(tmp, path)  # atomic on success; clobbers temp
        finally:
            tmp.unlink(missing_ok=True)  # no orphan if redact/replace raised
    except PdfCropError:
        raise
    except Exception as e:  # fitz render or tesseract/OCR failure
        raise OcrRedactionFailed(f"OCR redaction failed: {e}") from e
    return len(findings.matches)


def _assert_page_count(dest: Path, expected: int, *, engine: str = "pypdf") -> None:
    """Guard: the written `dest` must have exactly `expected` pages.

    Count with the SAME `engine` that wrote `dest`: pypdf reopening a fitz-saved
    file (or vice versa) can mis-parse and false-fail, discarding a valid output
    — the very cross-engine hazard this reorder removes. Identity is guaranteed
    by construction (select() order + each engine preserving page order), so only
    the count is checked — never leave a silently-wrong file.
    """
    if engine == "fitz":
        doc = fitz.open(str(dest))
        try:
            got = doc.page_count
        finally:
            doc.close()
    else:
        got = pdf_io.page_count(pdf_io.open_pdf(dest))
    if got != expected:
        raise PdfCropError(
            f"crop produced {got} page(s), expected {expected} — output discarded"
        )
