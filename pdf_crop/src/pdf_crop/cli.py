from importlib.metadata import version
from pathlib import Path
import argparse
import sys

from pdf_crop.shared.errors import NotAPdf, SourceNotFound
from pdf_crop.features.crop.command import run as crop_run
from pdf_crop.features.sanitize import service as sanitize_service
from pdf_crop.shared import pdf_io

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
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('pdf-crop')}",
    )
    parser.add_argument("file", type=Path, help="PDF to crop")
    parser.add_argument(
        "range",
        nargs="?",
        default=None,
        help='Page expression like "1-5,8,11-13". Omit to open the TUI.',
    )
    parser.add_argument(
        "--list-metadata",
        action="store_true",
        help="Print an inventory of every metadata source and exit (no write).",
    )
    parser.add_argument(
        "--sanitize",
        action="store_true",
        help="Rebuild clean: strip all non-essential metadata, keep the text.",
    )
    parser.add_argument(
        "--remove-metadata",
        action="store_true",
        help="Deprecated alias of --sanitize.",
    )
    parser.add_argument(
        "--redact-qr",
        action="store_true",
        help="Detect and remove QR codes / barcodes from the output PDF.",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="OCR scanned/image-only pages and redact CLABE/card/RFC/CURP text.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Where to write the output: a folder, an exact .pdf filename, or "
        "both. Default: next to the source, as <stem>_cropped.pdf.",
    )
    args = parser.parse_args(argv)

    try:
        _validate_pdf(args.file)
    except (SourceNotFound, NotAPdf) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.list_metadata:
        reader = pdf_io.open_pdf(args.file)
        inv = sanitize_service.inventory(reader)
        summary = inv.summary()
        if not summary:
            print("No metadata found.")
        else:
            for source, count in summary.items():
                print(f"{source}: {count}")
            print(f"total: {inv.total()}")
        return 0

    sanitize = args.sanitize or args.remove_metadata
    return crop_run(
        args.file,
        args.range,
        sanitize=sanitize,
        redact_qr=args.redact_qr,
        ocr=args.ocr,
        output=args.output,
    )
