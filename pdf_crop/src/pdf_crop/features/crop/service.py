from pathlib import Path

from pdf_crop.shared import pdf_io


def crop_pdf(src: Path, pages: list[int], dest: Path) -> Path:
    """Extract `pages` (1-indexed) from src into dest. Returns dest."""
    reader = pdf_io.open_pdf(src)
    pdf_io.write_subset(reader, pages, dest)
    return dest
