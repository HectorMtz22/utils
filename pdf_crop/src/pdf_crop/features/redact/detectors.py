import re
import unicodedata
from dataclasses import dataclass

# \w boundaries so 18-digit runs embedded in alphanumeric tokens are not matched.
_CLABE_RE = re.compile(r"(?<!\w)\d{18}(?!\w)")

# Plain 16-digit alternative also uses \w boundaries to avoid matching inside
# alphanumeric tokens.
_CARD_RE = re.compile(r"(?<!\w)(?:\d{4}[ -]){3}\d{4}(?!\w)|(?<!\w)\d{16}(?!\w)")

_CURP_RE = re.compile(r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b")
_RFC_RE = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b")


@dataclass(frozen=True)
class Match:
    category: str
    start: int
    end: int
    text: str


def _luhn_ok(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _fold_with_map(s):
    """Lowercase + strip accents; return (folded, idx_map).

    idx_map[i] is the index in ``s`` of the source character that produced
    folded character i.  This lets callers map positions in the folded string
    back to positions in the original (possibly NFD-normalised) input.
    """
    folded = []
    idx_map = []
    for i, ch in enumerate(s):
        for c in unicodedata.normalize("NFKD", ch):
            if unicodedata.combining(c):
                continue
            folded.append(c.lower())
            idx_map.append(i)
    return "".join(folded), idx_map


def _merge(matches):
    # Among the current detector set, overlapping spans are always containment
    # relationships (a shorter span fully inside a longer one) rather than
    # partial cross-overlaps, so replacing with the longest span is safe and
    # does not lose any coverage.
    matches.sort(key=lambda m: (m.start, -(m.end - m.start)))
    merged = []
    for m in matches:
        if merged and m.start < merged[-1].end:
            if (m.end - m.start) > (merged[-1].end - merged[-1].start):
                merged[-1] = m
            continue
        merged.append(m)
    return merged


def detect(text, *, categories, names):
    matches = []

    if "clabe" in categories:
        for m in _CLABE_RE.finditer(text):
            matches.append(Match("clabe", m.start(), m.end(), m.group()))

    if "card" in categories:
        for m in _CARD_RE.finditer(text):
            digits = re.sub(r"\D", "", m.group())
            if len(digits) == 16 and _luhn_ok(digits):
                matches.append(Match("card", m.start(), m.end(), m.group()))

    if "curp" in categories:
        for m in _CURP_RE.finditer(text):
            matches.append(Match("curp", m.start(), m.end(), m.group()))

    if "rfc" in categories:
        for m in _RFC_RE.finditer(text):
            matches.append(Match("rfc", m.start(), m.end(), m.group()))

    if "name" in categories:
        folded_text, text_idx_map = _fold_with_map(text)
        for name in names:
            name = name.strip()
            if not name:
                continue
            needle, _ = _fold_with_map(name)
            pattern = r"\b" + re.escape(needle) + r"\b"
            for fm in re.finditer(pattern, folded_text):
                fstart, fend = fm.start(), fm.end()
                # Map folded positions back to positions in the original text.
                orig_start = text_idx_map[fstart]
                orig_end = text_idx_map[fend - 1] + 1
                matches.append(Match("name", orig_start, orig_end, text[orig_start:orig_end]))

    return _merge(matches)
