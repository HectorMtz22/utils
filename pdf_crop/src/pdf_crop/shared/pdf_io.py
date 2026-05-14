from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from pypdf.generic import NameObject

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
    # pypdf 5.x/6.x: no public API to clear /Info or drop the catalog's XMP stream.
    info = writer._info.get_object() if writer._info is not None else None
    if info is not None:
        for key in list(info.keys()):
            del info[key]
    root = writer._root_object
    if NameObject("/Metadata") in root:
        del root[NameObject("/Metadata")]


def write_subset(
    reader: PdfReader,
    pages: list[int],
    dest: Path,
    *,
    strip_metadata: bool = False,
) -> None:
    """Write a new PDF containing the selected 1-indexed pages, in given order."""
    writer = PdfWriter()
    for page_number in pages:
        writer.add_page(reader.pages[page_number - 1])
    if strip_metadata:
        _clear_metadata(writer)
    with dest.open("wb") as f:
        writer.write(f)
