import pytest

from pdf_crop.features.crop.command import (
    run,
    OCR_CLI_CATEGORIES,
    _redact_qr_in_place,
    _redact_ocr_in_place,
)
from pdf_crop.features.qr_redact import service as qr_service
from pdf_crop.features.ocr_redact import service as ocr_service
from pdf_crop.shared.errors import PdfCropError
from pdf_crop.shared.pdf_io import open_pdf, page_count

CATS = {"clabe", "card", "rfc", "curp"}


def test_ocr_cli_categories_includes_account():
    # UTILS-19: the CLI OCR pass scans label-anchored account numbers too.
    assert "account" in OCR_CLI_CATEGORIES


def test_ocr_cli_categories_includes_address():
    # UTILS-20: the CLI OCR pass scans Mexican addresses (CP + street lines) too.
    assert "address" in OCR_CLI_CATEGORIES


def test_direct_mode_writes_cropped_file(ten_page_pdf, capsys):
    rc = run(ten_page_pdf, "1-3,5")
    assert rc == 0

    expected = ten_page_pdf.with_name("ten_cropped.pdf")
    assert expected.exists()
    assert page_count(open_pdf(expected)) == 4

    out = capsys.readouterr().out.strip()
    assert out == str(expected)


def test_direct_mode_output_kwarg_threads_through(ten_page_pdf, tmp_path, capsys):
    folder = tmp_path / "out"
    rc = run(ten_page_pdf, "1-3,5", output=str(folder))
    assert rc == 0

    expected = folder / "ten_cropped.pdf"
    assert expected.exists()
    assert page_count(open_pdf(expected)) == 4
    assert capsys.readouterr().out.strip() == str(expected)


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


def test_redact_ocr_skips_only_when_no_categories(ten_page_pdf, monkeypatch):
    """OCR pass is skipped (no render/OCR, no avoidable error) ONLY when no
    categories are selected. A name-only selection is NOT skipped: names are now
    auto-detected from label cues during the OCR pass even with an empty manual
    names list, so scan() must run for it."""
    def fail(*a, **k):
        raise AssertionError("OCR scan must not run when no category is selected")

    monkeypatch.setattr(ocr_service, "scan", fail)
    assert _redact_ocr_in_place(ten_page_pdf, categories=set(), names=[]) == 0

    # name-only now drives label-anchored auto-detection → scan() must run (here
    # it happens to find nothing, so the pass still returns 0 without rendering).
    calls = []

    def record(*a, **k):
        calls.append((a, k))
        return ocr_service.OcrFindings()  # no matches → returns 0, no render

    monkeypatch.setattr(ocr_service, "scan", record)
    assert _redact_ocr_in_place(ten_page_pdf, categories={"name"}, names=[]) == 0
    assert len(calls) == 1


def test_run_with_categories_redacts_text_layer(text_pdf_factory, capsys):
    src = text_pdf_factory(["CLABE 002010077777777771"])
    rc = run(src, "1", categories={"clabe"})
    assert rc == 0

    out = src.with_name(f"{src.stem}_cropped.pdf")
    assert "002010077777777771" not in open_pdf(out).pages[0].extract_text()


def test_run_names_only_implies_name_category(text_pdf_factory, monkeypatch):
    """Passing `names` but no `categories` still redacts the `name` category —
    detectors gate the whole name branch behind `"name" in categories`."""
    from pdf_crop.features.redact import service as redact_service

    calls = {}

    def fake_redact(writer, *, categories, names):
        calls["categories"] = categories
        return 0

    monkeypatch.setattr(redact_service, "redact", fake_redact)

    src = text_pdf_factory(["hello"])
    rc = run(src, "1", names=["Zoe"])
    assert rc == 0
    assert "name" in calls["categories"]


def test_run_without_redaction_flags_is_terse_and_skips_redact(text_pdf_factory, monkeypatch, capsys):
    """No categories/names → plain crop: redact_service.redact is never called and
    stdout is exactly the dest path (byte-for-byte legacy behavior)."""
    from pdf_crop.features.redact import service as redact_service

    def boom(*a, **k):
        raise AssertionError("redact must not run without categories/names")

    monkeypatch.setattr(redact_service, "redact", boom)

    src = text_pdf_factory(["CLABE 002010077777777771"])
    rc = run(src, "1")
    assert rc == 0
    assert capsys.readouterr().out.strip() == str(src.with_name(f"{src.stem}_cropped.pdf"))


def test_run_dry_run_writes_nothing_and_skips_redact(text_pdf_factory, monkeypatch, capsys):
    """`dry_run=True` scans for the preview but never builds/writes/redacts: the
    writer pipeline (build_subset, redact) must not run and no file is created."""
    from pdf_crop.features.redact import service as redact_service
    from pdf_crop.shared import pdf_io

    def no_build(*a, **k):
        raise AssertionError("build_subset must not run in dry-run")

    def no_redact(*a, **k):
        raise AssertionError("redact must not run in dry-run")

    monkeypatch.setattr(pdf_io, "build_subset", no_build)
    monkeypatch.setattr(redact_service, "redact", no_redact)

    src = text_pdf_factory(["CLABE 002010077777777771"])
    rc = run(src, "1", categories={"clabe"}, dry_run=True)
    assert rc == 0
    assert not src.with_name(f"{src.stem}_cropped.pdf").exists()


def test_run_passes_sanitize_through(pdf_with_metadata, capsys):
    from pdf_crop.features.sanitize.service import inventory

    rc = run(pdf_with_metadata, "1", sanitize=True)
    assert rc == 0

    expected = pdf_with_metadata.with_name("with_metadata_xmp_cropped.pdf")
    assert inventory(open_pdf(expected)).total() == 0
