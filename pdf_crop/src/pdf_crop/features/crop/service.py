from pathlib import Path

from pypdf import PdfReader

from pdf_crop.shared import pdf_io


def crop_pdf(
    reader: PdfReader,
    pages: list[int],
    dest: Path,
    *,
    strip_metadata: bool = False,
) -> Path:
    """Write `pages` (1-indexed) from `reader` into `dest`. Returns dest."""
    pdf_io.write_subset(reader, pages, dest, strip_metadata=strip_metadata)
    return dest
