import io

import fitz
import segno

from pdf_crop.features.qr_redact import service
import zbar_skip

pytestmark = zbar_skip.SKIP


def _decode_payloads(path, page_index=0, dpi=200):
    from PIL import Image
    from pyzbar.pyzbar import decode

    doc = fitz.open(str(path))
    pix = doc[page_index].get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return [r.data for r in decode(img)]


def _qr_pdf_at(tmp_path, placements):
    """Build a one-page A4 PDF with each (payload, rect) QR placed at `rect`.

    `placements` is a list of (payload, fitz.Rect). Unlike the shared
    qr_pdf_factory (fixed centred rect), this lets a test pin a code to an exact
    position so the coordinate mapping is exercised off-centre and for multiples.
    """
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    for payload, rect in placements:
        buf = io.BytesIO()
        segno.make(payload, error="h").save(buf, kind="png", scale=10, border=4)
        page.insert_image(rect, stream=buf.getvalue())
    path = tmp_path / "qr_placed.pdf"
    doc.save(str(path))
    doc.close()
    return path


def test_scan_finds_qr(qr_pdf_factory):
    src = qr_pdf_factory(["CLABE002010077777777771"])
    findings = service.scan(src, [1])
    assert len(findings.codes) == 1
    code = findings.codes[0]
    assert code.page == 1
    assert code.payload == "CLABE002010077777777771"
    assert code.symbology == "QRCODE"


def test_scan_only_reports_requested_pages(qr_pdf_factory):
    src = qr_pdf_factory(["PAGE-ONE-DATA", "PAGE-TWO-DATA"])
    findings = service.scan(src, [2])
    assert [c.payload for c in findings.codes] == ["PAGE-TWO-DATA"]
    assert findings.codes[0].page == 2


def test_scan_empty_when_no_codes(text_pdf_factory):
    src = text_pdf_factory(["just some text, no barcode"])
    findings = service.scan(src, [1])
    assert findings.codes == []


def test_redact_removes_qr(qr_pdf_factory, tmp_path):
    src = qr_pdf_factory(["CLABE002010077777777771"])
    findings = service.scan(src, [1])
    dest = tmp_path / "redacted.pdf"
    service.redact(src, dest, findings)
    # After redaction, decoding the rendered output must find NOTHING.
    assert _decode_payloads(dest) == []


def test_redact_noop_when_no_findings(qr_pdf_factory, tmp_path):
    # A page with a QR but empty findings: redact writes a copy, QR still there.
    src = qr_pdf_factory(["STILL-HERE"])
    dest = tmp_path / "copy.pdf"
    service.redact(src, dest, service.QrFindings())
    assert _decode_payloads(dest) == [b"STILL-HERE"]


def test_redact_removes_off_center_qr(tmp_path):
    # A QR pinned near the top-left corner (far from centre) must still map to
    # the right box and be removed — guards against a y-flip / scaling slip.
    src = _qr_pdf_at(tmp_path, [("CORNER-CODE", fitz.Rect(40, 40, 160, 160))])
    findings = service.scan(src, [1])
    assert len(findings.codes) == 1
    dest = tmp_path / "off_center.pdf"
    service.redact(src, dest, findings)
    assert _decode_payloads(dest) == []


def test_redact_removes_both_codes_on_one_page(tmp_path):
    # Two codes on a single page, placed apart: BOTH must be detected and gone.
    src = _qr_pdf_at(
        tmp_path,
        [
            ("TOP-LEFT-CODE", fitz.Rect(40, 40, 160, 160)),
            ("BOTTOM-RIGHT-CODE", fitz.Rect(420, 660, 540, 780)),
        ],
    )
    findings = service.scan(src, [1])
    assert {c.payload for c in findings.codes} == {"TOP-LEFT-CODE", "BOTTOM-RIGHT-CODE"}
    dest = tmp_path / "two_codes.pdf"
    service.redact(src, dest, findings)
    assert _decode_payloads(dest) == []
