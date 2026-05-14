from pdf_crop.cli import main
from pdf_crop.shared.pdf_io import open_pdf


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


def test_cli_remove_metadata_flag_strips_info(pdf_with_metadata, capsys):
    rc = main([str(pdf_with_metadata), "1", "--remove-metadata"])
    assert rc == 0

    expected = pdf_with_metadata.with_name("with_metadata_xmp_cropped.pdf")
    out = open_pdf(expected)
    assert not out.metadata
    assert "/Metadata" not in out.trailer["/Root"]
