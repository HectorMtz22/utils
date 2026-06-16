from importlib.metadata import version

import pytest

from pdf_crop.cli import main


def test_version_flag_prints_version_and_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out == f"pdfcrop {version('pdf-crop')}\n"


def test_version_flag_works_without_file_argument(capsys):
    # `--version` fires during argparse like `--help`, so it must not require
    # the `file` positional and must not emit an error to stderr.
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().err == ""


def test_version_is_derived_from_git_tags_not_fallback():
    # hatch-vcs derives the version from git tags at build time. A real,
    # tag-derived version proves the plugin ran; the bare fallback "0.0.0"
    # means git describe found nothing (misconfigured tag-pattern/match).
    resolved = version("pdf-crop")
    assert resolved
    assert resolved != "0.0.0"
