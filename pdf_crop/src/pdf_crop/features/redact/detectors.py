import re
import unicodedata
from dataclasses import dataclass

CATEGORIES = ("clabe", "card", "rfc", "curp", "name")

_CLABE_RE = re.compile(r"(?<!\d)\d{18}(?!\d)")

_CARD_RE = re.compile(r"(?<!\d)(?:\d{4}[ -]){3}\d{4}(?!\d)|(?<!\d)\d{16}(?!\d)")

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


def _fold(s):
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _merge(matches):
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
        folded_text = _fold(text)
        for name in names:
            name = name.strip()
            if not name:
                continue
            needle = _fold(name)
            start = folded_text.find(needle)
            while start != -1:
                end = start + len(needle)
                matches.append(Match("name", start, end, text[start:end]))
                start = folded_text.find(needle, end)

    return _merge(matches)
