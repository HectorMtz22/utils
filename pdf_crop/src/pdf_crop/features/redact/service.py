from collections import Counter
from dataclasses import dataclass, field

from pdf_crop.features.redact import detectors, text_layer
from pdf_crop.features.redact.detectors import Match


@dataclass
class Findings:
    matches: list[Match] = field(default_factory=list)       # flat list of every Match
    by_page: dict[int, list[Match]] = field(default_factory=dict)  # 1-indexed page -> list[Match]
    skipped_pages: list[int] = field(default_factory=list)   # pages that failed to parse

    def summary(self):
        return dict(Counter(m.category for m in self.matches))


def scan(reader, pages, *, categories, names):
    """Scan 1-indexed `pages` of `reader`. Returns Findings."""
    findings = Findings()
    for page_number in pages:
        page = reader.pages[page_number - 1]
        try:
            text, _ = text_layer.page_text(page)
        except Exception:
            findings.skipped_pages.append(page_number)
            continue
        matches = detectors.detect(text, categories=categories, names=names)
        if matches:
            findings.by_page[page_number] = list(matches)
            findings.matches.extend(matches)
    return findings


def redact(writer, *, categories, names):
    """Detect and delete sensitive spans on every page of `writer` in place."""
    for page in writer.pages:
        text, _ = text_layer.page_text(page)
        matches = detectors.detect(text, categories=categories, names=names)
        if matches:
            text_layer.delete_spans(page, [(m.start, m.end) for m in matches])
