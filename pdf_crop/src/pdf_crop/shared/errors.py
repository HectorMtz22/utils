class PdfCropError(Exception):
    """Base exception for all pdf_crop errors."""


class InvalidRangeSyntax(PdfCropError):
    """Range expression could not be parsed."""


class PageOutOfRange(PdfCropError):
    """Range references a page number outside the document."""


class NotAPdf(PdfCropError):
    """File is not a readable PDF."""


class SourceNotFound(PdfCropError):
    """Source file does not exist."""
