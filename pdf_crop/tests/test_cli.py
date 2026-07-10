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


def test_cli_output_folder_option_writes_into_folder(ten_page_pdf, tmp_path, capsys):
    folder = tmp_path / "out"
    rc = main([str(ten_page_pdf), "1-2", "-o", str(folder)])
    assert rc == 0

    expected = folder / "ten_cropped.pdf"
    assert expected.exists()
    assert capsys.readouterr().out.strip() == str(expected)


def test_cli_output_file_option_writes_exact_name(ten_page_pdf, tmp_path, capsys):
    dest = tmp_path / "report.pdf"
    rc = main([str(ten_page_pdf), "1-2", "--output", str(dest)])
    assert rc == 0
    assert dest.exists()
    assert capsys.readouterr().out.strip() == str(dest)


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
    assert calls["categories"] == {"clabe", "account", "card", "rfc", "curp", "address"}
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


def test_cli_redact_all_removes_all_categories(text_pdf_factory, capsys):
    """`--redact all` (and bare `--redact`) redacts every category present."""
    src = text_pdf_factory([
        "CLABE 002010077777777771",
        "Card 4111111111111111",
        "RFC PECJ800101AB1",
    ])
    rc = main([str(src), "1-3", "--redact", "all"])
    assert rc == 0

    out = src.with_name(f"{src.stem}_cropped.pdf")
    text = "".join(p.extract_text() for p in open_pdf(out).pages)
    assert "002010077777777771" not in text
    assert "4111111111111111" not in text
    assert "PECJ800101AB1" not in text


def test_cli_redact_bare_flag_removes_clabe(text_pdf_factory, capsys):
    """Bare `--redact` behaves like `--redact all` (const='all')."""
    src = text_pdf_factory(["CLABE 002010077777777771"])
    rc = main([str(src), "1", "--redact"])
    assert rc == 0

    out = src.with_name(f"{src.stem}_cropped.pdf")
    text = "".join(p.extract_text() for p in open_pdf(out).pages)
    assert "002010077777777771" not in text


def test_cli_redact_subset_keeps_unselected_category(text_pdf_factory, capsys):
    """`--redact clabe,card` removes only those; a non-selected RFC survives."""
    src = text_pdf_factory([
        "CLABE 002010077777777771",
        "Card 4111111111111111",
        "RFC PECJ800101AB1",
    ])
    rc = main([str(src), "1-3", "--redact", "clabe,card"])
    assert rc == 0

    out = src.with_name(f"{src.stem}_cropped.pdf")
    text = "".join(p.extract_text() for p in open_pdf(out).pages)
    assert "002010077777777771" not in text
    assert "4111111111111111" not in text
    assert "PECJ800101AB1" in text  # rfc not selected → survives


def test_cli_redact_passes_effective_categories_and_names(text_pdf_factory, monkeypatch):
    """The parsed categories (∪ implied `name`) and names reach redact_service."""
    from pdf_crop.features.redact import service as redact_service

    calls = {}

    def fake_redact(writer, *, categories, names):
        calls["categories"] = categories
        calls["names"] = names
        return 1

    monkeypatch.setattr(redact_service, "redact", fake_redact)

    src = text_pdf_factory(["CLABE 002010077777777771"])
    rc = main([str(src), "1", "--redact", "clabe,name", "--names", "Juan Perez"])
    assert rc == 0
    assert calls["categories"] == {"clabe", "name"}
    assert calls["names"] == ["Juan Perez"]


def test_cli_redact_unknown_category_returns_2_and_writes_nothing(text_pdf_factory, capsys):
    src = text_pdf_factory(["hello"])
    rc = main([str(src), "1", "--redact", "bogus"])
    assert rc == 2
    assert "error:" in capsys.readouterr().err
    assert not src.with_name(f"{src.stem}_cropped.pdf").exists()


def test_cli_names_without_redact_deletes_literal(text_pdf_factory, capsys):
    """`--names` alone enables name redaction (implies the `name` category); a
    non-selected CLABE survives because only names were requested."""
    src = text_pdf_factory(["CLABE 002010077777777771 de JOSE PEREZ"])
    rc = main([str(src), "1", "--names", "Jose Perez"])
    assert rc == 0

    out = src.with_name(f"{src.stem}_cropped.pdf")
    text = "".join(p.extract_text() for p in open_pdf(out).pages)
    assert "JOSE PEREZ" not in text
    assert "002010077777777771" in text  # clabe not selected → survives


def test_cli_names_imply_name_category(text_pdf_factory, monkeypatch):
    """`--names` without `--redact` still passes `name` in the categories."""
    from pdf_crop.features.redact import service as redact_service

    calls = {}

    def fake_redact(writer, *, categories, names):
        calls["categories"] = categories
        calls["names"] = names
        return 1

    monkeypatch.setattr(redact_service, "redact", fake_redact)

    src = text_pdf_factory(["A nombre de JOSE PEREZ"])
    rc = main([str(src), "1", "--names", "Jose Perez"])
    assert rc == 0
    assert "name" in calls["categories"]
    assert calls["names"] == ["Jose Perez"]


def test_cli_ocr_with_redact_drives_ocr_with_effective(ten_page_pdf, monkeypatch, capsys):
    """`--ocr --redact clabe,name --names X` runs OCR with the effective
    categories ({clabe,name}) and the names list."""
    from pdf_crop.features.crop import command

    calls = {}

    def fake_ocr(dest, *, categories, names):
        calls["categories"] = categories
        calls["names"] = names
        return 0

    monkeypatch.setattr(command, "_redact_ocr_in_place", fake_ocr)

    rc = main([str(ten_page_pdf), "1-2", "--ocr", "--redact", "clabe,name", "--names", "X"])
    assert rc == 0
    assert calls["categories"] == {"clabe", "name"}
    assert calls["names"] == ["X"]


def test_cli_redact_prints_summary_line(text_pdf_factory, capsys):
    src = text_pdf_factory(["CLABE 002010077777777771"])
    rc = main([str(src), "1", "--redact", "clabe"])
    assert rc == 0

    out = capsys.readouterr().out
    dest = src.with_name(f"{src.stem}_cropped.pdf")
    assert out.startswith("Redacted")
    assert "clabe" in out
    assert str(dest) in out


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
