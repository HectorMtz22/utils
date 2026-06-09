import pytest

from pdf_crop.features.crop.command import run, _redact_qr_in_place, _redact_ocr_in_place
from pdf_crop.features.qr_redact import service as qr_service
from pdf_crop.features.ocr_redact import service as ocr_service
from pdf_crop.shared.errors import PdfCropError
from pdf_crop.shared.pdf_io import open_pdf, page_count

CATS = {"clabe", "card", "rfc", "curp"}


def test_direct_mode_writes_cropped_file(ten_page_pdf, capsys):
    rc = run(ten_page_pdf, "1-3,5")
    assert rc == 0

    expected = ten_page_pdf.with_name("ten_cropped.pdf")
    assert expected.exists()
    assert page_count(open_pdf(expected)) == 4

    out = capsys.readouterr().out.strip()
    assert out == str(expected)


def test_direct_mode_auto_suffix_on_collision(ten_page_pdf, capsys):
    (ten_page_pdf.parent / "ten_cropped.pdf").write_bytes(b"%PDF-1.4\n")
    rc = run(ten_page_pdf, "1-3")
    assert rc == 0
    assert (ten_page_pdf.parent / "ten_cropped (1).pdf").exists()


def test_invalid_range_returns_2_and_writes_to_stderr(ten_page_pdf, capsys):
    rc = run(ten_page_pdf, "abc")
    assert rc == 2
    err = capsys.readouterr().err
    assert "error:" in err


def test_out_of_range_returns_2(ten_page_pdf, capsys):
    rc = run(ten_page_pdf, "100")
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_run_passes_strip_metadata_through(pdf_with_metadata, capsys):
    rc = run(pdf_with_metadata, "1", strip_metadata=True)
    assert rc == 0

    expected = pdf_with_metadata.with_name("with_metadata_xmp_cropped.pdf")
    out = open_pdf(expected)
    assert not out.metadata
    assert "/Metadata" not in out.trailer["/Root"]


def _one_finding(page=1):
    """A QrFindings with a single code so the redact path is reached."""
    f = qr_service.QrFindings()
    f.codes.append(
        qr_service.QrCode(page=page, symbology="QRCODE", payload="x", rect=None)
    )
    return f


def test_redact_qr_cleans_up_temp_on_redact_failure(ten_page_pdf, monkeypatch):
    """If redact raises after creating the temp file, no .qr-tmp.pdf is left and
    the source PDF is untouched."""
    dest = ten_page_pdf  # treat the existing file as the already-written crop
    original = dest.read_bytes()
    tmp = dest.with_name(f"{dest.stem}.qr-tmp.pdf")

    monkeypatch.setattr(qr_service, "scan", lambda *a, **k: _one_finding())

    def fake_redact(path, dest_path, findings):
        dest_path.write_bytes(b"%PDF-1.4\npartial")  # temp gets created...
        raise RuntimeError("boom")                   # ...then second pass fails

    monkeypatch.setattr(qr_service, "redact", fake_redact)

    with pytest.raises(PdfCropError):
        _redact_qr_in_place(dest)

    assert not tmp.exists()
    assert dest.read_bytes() == original


def test_redact_qr_translates_imaging_error_to_pdfcroperror(ten_page_pdf, monkeypatch):
    """A decode/imaging error in the second pass surfaces as a PdfCropError."""
    monkeypatch.setattr(qr_service, "scan", lambda *a, **k: _one_finding())

    def fake_redact(path, dest_path, findings):
        raise ValueError("pyzbar decode failure")

    monkeypatch.setattr(qr_service, "redact", fake_redact)

    with pytest.raises(PdfCropError):
        _redact_qr_in_place(ten_page_pdf)


def test_run_with_redact_qr_returns_2_on_second_pass_error(ten_page_pdf, monkeypatch, capsys):
    """CLI run() exits rc 2 with 'error:' when the QR second pass blows up."""
    monkeypatch.setattr(qr_service, "scan", lambda *a, **k: _one_finding())
    monkeypatch.setattr(
        qr_service, "redact",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("decode failure")),
    )

    rc = run(ten_page_pdf, "1-3", redact_qr=True)
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def _one_ocr_finding(page=1):
    """An OcrFindings with a single match so the redact path is reached."""
    f = ocr_service.OcrFindings()
    f.matches.append(
        ocr_service.OcrMatch(page=page, category="clabe", text="x", rects=())
    )
    return f


def test_redact_ocr_cleans_up_temp_on_redact_failure(ten_page_pdf, monkeypatch):
    """If OCR redact raises after creating the temp file, no .ocr-tmp.pdf is left
    and the source PDF is untouched."""
    dest = ten_page_pdf
    original = dest.read_bytes()
    tmp = dest.with_name(f"{dest.stem}.ocr-tmp.pdf")

    monkeypatch.setattr(ocr_service, "scan", lambda *a, **k: _one_ocr_finding())

    def fake_redact(path, dest_path, findings):
        dest_path.write_bytes(b"%PDF-1.4\npartial")  # temp gets created...
        raise RuntimeError("boom")                   # ...then second pass fails

    monkeypatch.setattr(ocr_service, "redact", fake_redact)

    with pytest.raises(PdfCropError):
        _redact_ocr_in_place(dest, categories=CATS, names=[])

    assert not tmp.exists()
    assert dest.read_bytes() == original


def test_redact_ocr_translates_tesseract_error_to_pdfcroperror(ten_page_pdf, monkeypatch):
    """A render/OCR error in the second pass surfaces as a PdfCropError."""
    def boom(*a, **k):
        raise ValueError("tesseract not found")

    monkeypatch.setattr(ocr_service, "scan", boom)

    with pytest.raises(PdfCropError):
        _redact_ocr_in_place(ten_page_pdf, categories=CATS, names=[])


def test_run_with_ocr_returns_2_on_second_pass_error(ten_page_pdf, monkeypatch, capsys):
    """CLI run() exits rc 2 with 'error:' when the OCR second pass blows up."""
    monkeypatch.setattr(ocr_service, "scan", lambda *a, **k: _one_ocr_finding())
    monkeypatch.setattr(
        ocr_service, "redact",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("ocr failure")),
    )

    rc = run(ten_page_pdf, "1-3", ocr=True)
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_run_passes_sanitize_through(pdf_with_metadata, capsys):
    from pdf_crop.features.sanitize.service import inventory

    rc = run(pdf_with_metadata, "1", sanitize=True)
    assert rc == 0

    expected = pdf_with_metadata.with_name("with_metadata_xmp_cropped.pdf")
    assert inventory(open_pdf(expected)).total() == 0
