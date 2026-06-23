import fitz

from pdf_crop.cli import main
from pdf_crop.shared.pdf_io import open_pdf
import zbar_skip


def test_missing_file_returns_2(tmp_path, capsys):
    rc = main([str(tmp_path / "nope.pdf")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_wrong_extension_returns_2(tmp_path, capsys):
    bad = tmp_path / "thing.txt"
    bad.write_text("hi")
    rc = main([str(bad)])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_missing_pdf_header_returns_2(tmp_path, capsys):
    bad = tmp_path / "thing.pdf"
    bad.write_bytes(b"NOPE")
    rc = main([str(bad)])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_direct_mode_dispatches_to_crop(ten_page_pdf, capsys):
    rc = main([str(ten_page_pdf), "1-2"])
    assert rc == 0
    assert (ten_page_pdf.with_name("ten_cropped.pdf")).exists()


@zbar_skip.SKIP
def test_cli_redact_qr_flag_removes_qr_from_output(qr_pdf_factory, capsys):
    from PIL import Image
    from pyzbar.pyzbar import decode

    src = qr_pdf_factory(["CLABE002010077777777771"])
    rc = main([str(src), "1", "--redact-qr"])
    assert rc == 0

    out = src.with_name(f"{src.stem}_cropped.pdf")
    assert out.exists()
    doc = fitz.open(str(out))
    pix = doc[0].get_pixmap(dpi=200)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    assert decode(img) == []  # QR is gone from the rendered output


def test_cli_ocr_flag_runs_second_pass(ten_page_pdf, monkeypatch, capsys):
    """`--ocr` triggers the OCR second pass over the written output with the
    automatic categories (no per-category flags in the CLI)."""
    from pdf_crop.features.crop import command

    calls = {}

    def fake_ocr(dest, *, categories, names):
        calls["categories"] = categories
        calls["names"] = names
        return 0

    monkeypatch.setattr(command, "_redact_ocr_in_place", fake_ocr)

    rc = main([str(ten_page_pdf), "1-2", "--ocr"])
    assert rc == 0
    assert calls["categories"] == {"clabe", "account", "card", "rfc", "curp"}
    assert calls["names"] == []


def test_cli_ocr_flag_removes_clabe_from_image_pdf(image_pdf_factory):
    """End-to-end: --ocr redacts a CLABE that only exists in the image layer."""
    import pytest
    import tesseract_skip

    if not tesseract_skip.TESSERACT_AVAILABLE:
        pytest.skip("tesseract binary unavailable")

    import pytesseract
    from pdf_crop.shared import imaging

    clabe = "002010012345678903"
    src = image_pdf_factory([f"CLABE {clabe}"])
    rc = main([str(src), "1", "--ocr"])
    assert rc == 0

    out = src.with_name(f"{src.stem}_cropped.pdf")
    assert out.exists()
    doc = fitz.open(str(out))
    img = imaging.render_page(doc[0], dpi=200)
    doc.close()
    assert clabe not in pytesseract.image_to_string(img).replace(" ", "")


def test_cli_remove_metadata_flag_strips_info(pdf_with_metadata, capsys):
    rc = main([str(pdf_with_metadata), "1", "--remove-metadata"])
    assert rc == 0

    expected = pdf_with_metadata.with_name("with_metadata_xmp_cropped.pdf")
    out = open_pdf(expected)
    assert not out.metadata
    assert "/Metadata" not in out.trailer["/Root"]


def test_cli_list_metadata_prints_inventory(pdf_with_metadata, capsys):
    rc = main([str(pdf_with_metadata), "--list-metadata"])
    assert rc == 0

    printed = capsys.readouterr().out
    assert "info" in printed
    assert "annotations" in printed
    # --list-metadata must not write an output PDF.
    assert not pdf_with_metadata.with_name("with_metadata_xmp_cropped.pdf").exists()


def test_cli_sanitize_strips_everything(pdf_with_metadata, capsys):
    from pdf_crop.features.sanitize.service import inventory

    rc = main([str(pdf_with_metadata), "1", "--sanitize"])
    assert rc == 0

    out = open_pdf(pdf_with_metadata.with_name("with_metadata_xmp_cropped.pdf"))
    assert inventory(out).total() == 0
    assert "Page 1" in out.pages[0].extract_text()


def test_cli_remove_metadata_alias_strips_everything(pdf_with_metadata, capsys):
    from pdf_crop.features.sanitize.service import inventory

    rc = main([str(pdf_with_metadata), "1", "--remove-metadata"])
    assert rc == 0

    out = open_pdf(pdf_with_metadata.with_name("with_metadata_xmp_cropped.pdf"))
    assert inventory(out).total() == 0
