from pathlib import Path

import pytest

from pdf_crop.shared.errors import OutputPathError
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


def test_empty_output_uses_default_next_to_source(tmp_path):
    # A blank --output (e.g. `-o ""` or an unset shell var) falls back to the
    # default next-to-source name, not Path(".")/the current working directory.
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    assert resolve(src, "") == tmp_path / "Doc_cropped.pdf"


def test_whitespace_output_uses_default_next_to_source(tmp_path):
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    assert resolve(src, "   ") == tmp_path / "Doc_cropped.pdf"


def test_folder_target_creates_dir_and_uses_default_stem(tmp_path):
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    folder = tmp_path / "out"
    assert not folder.exists()
    result = resolve(src, str(folder))
    assert result == folder / "Doc_cropped.pdf"
    assert folder.is_dir()


def test_folder_target_trailing_slash(tmp_path):
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    folder = tmp_path / "out"
    result = resolve(src, f"{folder}/")
    assert result == folder / "Doc_cropped.pdf"


def test_file_target_exact_name_no_suffix(tmp_path, monkeypatch):
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    monkeypatch.chdir(tmp_path)
    result = resolve(src, "report.pdf")
    assert result == Path("report.pdf")
    assert result.resolve() == tmp_path / "report.pdf"


def test_file_target_in_folder_creates_dir(tmp_path):
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    folder = tmp_path / "out"
    result = resolve(src, str(folder / "report.pdf"))
    assert result == folder / "report.pdf"
    assert folder.is_dir()


def test_uppercase_pdf_extension_is_file_target(tmp_path):
    # `.PDF` (any case) triggers the file-target branch; the produced filename
    # extension itself is still normalized to lowercase `.pdf` by _non_colliding.
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    result = resolve(src, str(tmp_path / "REPORT.PDF"))
    assert result == tmp_path / "REPORT.pdf"


def test_non_pdf_dot_in_folder_path_is_folder_target(tmp_path):
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    folder = tmp_path / "reports" / "v1.2"
    result = resolve(src, str(folder))
    assert result == folder / "Doc_cropped.pdf"
    assert folder.is_dir()


def test_collision_on_explicit_filename(tmp_path):
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    (tmp_path / "report.pdf").write_bytes(b"existing")
    result = resolve(src, str(tmp_path / "report.pdf"))
    assert result == tmp_path / "report (1).pdf"


def test_collision_on_folder_default(tmp_path):
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    folder = tmp_path / "out"
    folder.mkdir()
    (folder / "Doc_cropped.pdf").write_bytes(b"existing")
    result = resolve(src, str(folder))
    assert result == folder / "Doc_cropped (1).pdf"


def test_tilde_expansion(tmp_path, monkeypatch):
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = resolve(src, "~/out")
    assert result == home / "out" / "Doc_cropped.pdf"


def test_mkdir_failure_raises_output_path_error(tmp_path):
    src = tmp_path / "Doc.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"not a directory")
    with pytest.raises(OutputPathError):
        resolve(src, str(blocker / "sub"))
