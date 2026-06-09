import fitz

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
