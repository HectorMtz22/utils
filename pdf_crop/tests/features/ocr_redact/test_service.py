import fitz

from pdf_crop.features.ocr_redact import service
import tesseract_skip

# Categories the OCR pass scans automatically (no per-category UI in the CLI).
# A valid-format 18-digit CLABE without long identical-digit runs, which OCR
# (tesseract) reads reliably across font sizes / DPI in the synthetic fixture.
CATS = {"clabe", "card", "rfc", "curp"}
CLABE = "002010012345678903"


def _ocr_text(path, page_index=0, dpi=service.DPI):
    """Re-OCR a rendered page and return the recovered text (for assertions)."""
    import pytesseract

    from pdf_crop.shared import imaging

    doc = fitz.open(str(path))
    try:
        img = imaging.render_page(doc[page_index], dpi=dpi)
        return pytesseract.image_to_string(img)
    finally:
        doc.close()


def test_needs_ocr_detects_image_page(image_pdf_factory):
    src = image_pdf_factory([f"CLABE {CLABE}"])
    doc = fitz.open(str(src))
    try:
        assert service.needs_ocr(doc[0]) is True
    finally:
        doc.close()


def test_needs_ocr_false_for_text_page(text_pdf_factory):
    src = text_pdf_factory([f"CLABE {CLABE} end"])
    doc = fitz.open(str(src))
    try:
        assert service.needs_ocr(doc[0]) is False
    finally:
        doc.close()


def test_scan_skips_text_layer_pages(text_pdf_factory):
    # Pages with a real text layer are handled by the text-layer redactor, so
    # the OCR pass must skip them (the needs_ocr gate) — no OCR findings even
    # when the page text contains a CLABE. Runs without tesseract: the gate
    # short-circuits before any OCR call.
    src = text_pdf_factory([f"CLABE {CLABE} end"])
    findings = service.scan(src, categories=CATS, names=[])
    assert findings.matches == []


@tesseract_skip.SKIP
def test_ocr_scan_finds_clabe(image_pdf_factory):
    src = image_pdf_factory([f"CLABE {CLABE}"])
    findings = service.scan(src, categories=CATS, names=[])
    assert any(f.category == "clabe" and CLABE in f.text for f in findings.matches)


@tesseract_skip.SKIP
def test_ocr_redact_removes_clabe(image_pdf_factory, tmp_path):
    src = image_pdf_factory([f"CLABE {CLABE}"])
    # Confirm the CLABE really is OCR-readable before redaction.
    assert CLABE in _ocr_text(src).replace(" ", "")
    findings = service.scan(src, categories=CATS, names=[])
    dest = tmp_path / "ocr_redacted.pdf"
    count = service.redact(src, dest, findings)
    assert count >= 1
    # After redaction, re-OCR of the output must no longer contain the CLABE.
    assert CLABE not in _ocr_text(dest).replace(" ", "")
