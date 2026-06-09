from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from pdf_crop.features.sanitize import service as sanitize_service
from pdf_crop.shared.errors import NotAPdf, SourceNotFound


def open_pdf(path: Path) -> PdfReader:
    """Open a PDF and return its reader. Raises SourceNotFound or NotAPdf."""
    if not path.exists():
        raise SourceNotFound(f"file not found: {path}")
    try:
        return PdfReader(str(path))
    except (PdfReadError, OSError) as e:
        raise NotAPdf(f"could not read PDF '{path}': {e}") from e


def page_count(reader: PdfReader) -> int:
    return len(reader.pages)


def _clear_metadata(writer: PdfWriter) -> None:
    # Exhaustive scrub lives in the sanitize feature; delegate, don't duplicate.
    sanitize_service.sanitize(writer)


def build_subset(
    reader: PdfReader,
    pages: list[int],
    *,
    strip_metadata: bool = False,
    sanitize: bool = False,
) -> PdfWriter:
    """Build and return a PdfWriter with the selected 1-indexed pages.

    `sanitize` (or its deprecated alias `strip_metadata`) rebuilds the subset
    clean, stripping all non-essential metadata while keeping the text layer.
    """
    writer = PdfWriter()
    for page_number in pages:
        writer.add_page(reader.pages[page_number - 1])
    if sanitize or strip_metadata:
        _clear_metadata(writer)
    return writer


def write_subset(
    reader: PdfReader,
    pages: list[int],
    dest: Path,
    *,
    strip_metadata: bool = False,
    sanitize: bool = False,
) -> None:
    """Write a new PDF containing the selected 1-indexed pages, in given order."""
    writer = build_subset(reader, pages, strip_metadata=strip_metadata, sanitize=sanitize)
    with dest.open("wb") as f:
        writer.write(f)
