from pdf_crop.features.crop.command import run
from pdf_crop.shared.pdf_io import open_pdf, page_count


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
