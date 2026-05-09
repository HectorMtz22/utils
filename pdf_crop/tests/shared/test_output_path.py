from pathlib import Path

from pdf_crop.shared.output_path import resolve


def test_no_collision_returns_base(tmp_path):
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    assert resolve(src) == tmp_path / "Doc_cropped.pdf"


def test_one_collision_returns_suffixed(tmp_path):
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    (tmp_path / "Doc_cropped.pdf").write_bytes(b"existing")
    assert resolve(src) == tmp_path / "Doc_cropped (1).pdf"


def test_multiple_collisions_increment(tmp_path):
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    (tmp_path / "Doc_cropped.pdf").write_bytes(b"x")
    (tmp_path / "Doc_cropped (1).pdf").write_bytes(b"x")
    (tmp_path / "Doc_cropped (2).pdf").write_bytes(b"x")
    assert resolve(src) == tmp_path / "Doc_cropped (3).pdf"


def test_custom_suffix(tmp_path):
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    assert resolve(src, suffix="_extracted") == tmp_path / "Doc_extracted.pdf"
