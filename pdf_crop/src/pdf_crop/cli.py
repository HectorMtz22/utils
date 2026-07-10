from importlib.metadata import version
from pathlib import Path
import argparse
import sys

from pdf_crop.shared.errors import InvalidRedactCategory, NotAPdf, SourceNotFound
from pdf_crop.features.crop.command import run as crop_run
from pdf_crop.features.sanitize import service as sanitize_service
from pdf_crop.shared import pdf_io

PDF_MAGIC = b"%PDF"

# The canonical text-layer redaction categories (mirrors detectors.detect).
CANONICAL_CATEGORIES = {"clabe", "account", "card", "rfc", "curp", "address", "name"}


def _validate_pdf(path: Path) -> None:
    if not path.exists():
        raise SourceNotFound(f"file not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise NotAPdf(f"not a PDF file (extension): {path}")
    with path.open("rb") as f:
        header = f.read(4)
    if header != PDF_MAGIC:
        raise NotAPdf(f"file missing PDF header: {path}")


def _parse_categories(value: str) -> set[str]:
    """Parse a --redact value into a set of canonical categories.

    "all" (case-insensitive) expands to every category. Otherwise the value is a
    comma-separated, case-insensitive list; whitespace is stripped. An unknown
    token raises InvalidRedactCategory.
    """
    if value.strip().lower() == "all":
        return set(CANONICAL_CATEGORIES)
    result: set[str] = set()
    for token in value.split(","):
        token = token.strip().lower()
        if not token:
            continue
        if token not in CANONICAL_CATEGORIES:
            valid = ", ".join(sorted(CANONICAL_CATEGORIES))
            raise InvalidRedactCategory(
                f"unknown redact category: {token!r} (valid: {valid}, all)"
            )
        result.add(token)
    return result


def _parse_names(value: str | None) -> list[str] | None:
    """Split a --names value into stripped, non-empty literals (None → None)."""
    if value is None:
        return None
    return [name.strip() for name in value.split(",") if name.strip()]


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
        "--redact",
        nargs="?",
        const="all",
        default=None,
        metavar="CATS",
        help="Redact PII from the text layer. Bare or 'all' redacts every "
        "category; or pass a comma-separated subset of "
        "clabe,account,card,rfc,curp,address,name.",
    )
    parser.add_argument(
        "--names",
        default=None,
        metavar='"A,B"',
        help="Comma-separated literal names to delete (implies the 'name' "
        "category).",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="OCR scanned/image-only pages and redact sensitive text "
        "(CLABE/account/card/RFC/CURP/address, or the --redact selection).",
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

    try:
        categories = _parse_categories(args.redact) if args.redact is not None else None
    except InvalidRedactCategory as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    sanitize = args.sanitize or args.remove_metadata
    return crop_run(
        args.file,
        args.range,
        sanitize=sanitize,
        redact_qr=args.redact_qr,
        ocr=args.ocr,
        output=args.output,
        categories=categories,
        names=_parse_names(args.names),
    )
