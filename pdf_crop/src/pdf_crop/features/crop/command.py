from pathlib import Path
import sys

from pdf_crop.shared import ranges, pdf_io, output_path
from pdf_crop.shared.errors import PdfCropError

from .service import crop_pdf


def run(
    src: Path,
    range_expr: str | None,
    *,
    sanitize: bool = False,
    strip_metadata: bool = False,
) -> int:
    """Crop entry point. If range_expr is None, launch the TUI; otherwise direct mode.

    `strip_metadata` is a deprecated alias of `sanitize`.
    """
    sanitize = sanitize or strip_metadata
    if range_expr is None:
        from pdf_crop.app import PdfCropApp
        return PdfCropApp(src, sanitize=sanitize).run() or 0

    try:
        reader = pdf_io.open_pdf(src)
        total = pdf_io.page_count(reader)
        pages = ranges.parse(range_expr, total)
        dest = output_path.resolve(src)
        result = crop_pdf(reader, pages, dest, sanitize=sanitize)
    except PdfCropError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(result)
    return 0
