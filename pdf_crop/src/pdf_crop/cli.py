from pathlib import Path
import argparse
import sys

from pdf_crop.shared.errors import NotAPdf, SourceNotFound
from pdf_crop.features.crop.command import run as crop_run

PDF_MAGIC = b"%PDF"


def _validate_pdf(path: Path) -> None:
    if not path.exists():
        raise SourceNotFound(f"file not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise NotAPdf(f"not a PDF file (extension): {path}")
    with path.open("rb") as f:
        header = f.read(4)
    if header != PDF_MAGIC:
        raise NotAPdf(f"file missing PDF header: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pdfcrop",
        description="Extract a page range from a PDF.",
    )
    parser.add_argument("file", type=Path, help="PDF to crop")
    parser.add_argument(
        "range",
        nargs="?",
        default=None,
        help='Page expression like "1-5,8,11-13". Omit to open the TUI.',
    )
    args = parser.parse_args(argv)

    try:
        _validate_pdf(args.file)
    except (SourceNotFound, NotAPdf) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    return crop_run(args.file, args.range)
