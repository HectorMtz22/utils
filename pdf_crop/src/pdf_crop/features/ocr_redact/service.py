"""Find and redact sensitive text on scanned / image-only PDF pages via OCR.

Scanned statements have no text layer, so the text-layer detectors find
nothing. This renders each page, OCRs it with tesseract (via pytesseract),
reconstructs the page text while tracking every word's char range, runs the
shared detectors over that text, maps each matched char-span back to the OCR
word boxes it overlaps, and applies a TRUE PyMuPDF redaction over each box so
the underlying image content is removed, not merely covered.

Mirrors the qr_redact feature: a second pass over an already-written file.
"""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import fitz

from pdf_crop.features.redact import detectors
from pdf_crop.shared import imaging

# Statement text is small; 200 dpi gives tesseract enough detail to read CLABE
# / card digits reliably without making rendering slow.
DPI = 200

# A page with at least this many extractable characters is treated as having a
# real text layer (so OCR isn't needed). Scanned pages strip to ~nothing.
_TEXT_THRESHOLD = 10


@dataclass(frozen=True)
class OcrMatch:
    page: int           # 1-indexed page number
    category: str       # detector category, e.g. "clabe", "card"
    text: str           # the matched text as OCR'd
    rects: tuple        # bounding boxes in PDF points (one per overlapping word)


@dataclass
class OcrFindings:
    matches: list[OcrMatch] = field(default_factory=list)

    def summary(self):
        return dict(Counter(m.category for m in self.matches))


def needs_ocr(page) -> bool:
    """True when `page` (a `fitz.Page`) has an empty/negligible text layer."""
    return len(page.get_text().strip()) < _TEXT_THRESHOLD


def _ocr_words(image):
    """OCR `image`, returning a list of (word, left, top, width, height).

    Boxes are in image pixels with a top-left origin (same convention as
    pyzbar). Blank/whitespace-only tokens are dropped.
    """
    import pytesseract

    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    words = []
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        words.append(
            (word, data["left"][i], data["top"][i], data["width"][i], data["height"][i])
        )
    return words


def _reconstruct(words):
    """Join OCR `words` into one text, tracking each word's char span.

    Returns (text, spans) where spans[i] = (start, end) is the char range of
    words[i][0] in `text`. A single space joins words so detector regexes that
    allow a separator (e.g. the spaced card format) still match across words.
    """
    parts = []
    spans = []
    pos = 0
    for idx, (word, *_box) in enumerate(words):
        if idx:
            parts.append(" ")
            pos += 1
        spans.append((pos, pos + len(word)))
        parts.append(word)
        pos += len(word)
    return "".join(parts), spans


def _boxes_for_span(start, end, words, spans):
    """Image-pixel boxes of every OCR word whose char span overlaps [start,end)."""
    boxes = []
    for (_word, left, top, width, height), (wstart, wend) in zip(words, spans):
        if wstart < end and start < wend:  # half-open overlap
            boxes.append((left, top, left + width, top + height))
    return boxes


def scan(path: Path, pages=None, *, categories, names) -> OcrFindings:
    """OCR-scan 1-indexed `pages` of the PDF at `path` for sensitive text.

    `pages=None` scans every page. For each page the text is reconstructed from
    the OCR words, run through the shared detectors, and each match mapped to
    the PDF-point boxes of the words it overlaps.
    """
    findings = OcrFindings()
    doc = fitz.open(str(path))
    try:
        if pages is None:
            pages = range(1, doc.page_count + 1)
        for page_number in pages:
            page = doc[page_number - 1]
            if not needs_ocr(page):
                continue  # real text layer — the text-layer redactor handles it
            image = imaging.render_page(page, dpi=DPI)
            words = _ocr_words(image)
            if not words:
                continue
            text, spans = _reconstruct(words)
            for m in detectors.detect(text, categories=categories, names=names):
                boxes = _boxes_for_span(m.start, m.end, words, spans)
                rects = tuple(imaging.img_rect_to_pdf(b, dpi=DPI) for b in boxes)
                findings.matches.append(
                    OcrMatch(page=page_number, category=m.category, text=m.text, rects=rects)
                )
    finally:
        doc.close()
    return findings


def redact(path: Path, dest: Path, findings: OcrFindings) -> int:
    """Redact every word box in `findings` from `path`, saving to `dest`.

    Returns the number of matches redacted. With no findings this just writes a
    cleaned copy. Uses PyMuPDF true redaction (content is removed, not covered).
    """
    doc = fitz.open(str(path))
    try:
        by_page: dict[int, list[fitz.Rect]] = {}
        for match in findings.matches:
            by_page.setdefault(match.page, []).extend(match.rects)
        for page_number, rects in by_page.items():
            imaging.redact_rects(doc, page_number - 1, rects)
        doc.save(str(dest), garbage=4, deflate=True)
    finally:
        doc.close()
    return len(findings.matches)
