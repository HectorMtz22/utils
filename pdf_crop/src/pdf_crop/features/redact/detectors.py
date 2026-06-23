import re
import unicodedata
from dataclasses import dataclass

# CLABE: 18 digits. A *contiguous* 18-digit run is distinctive enough to match
# anywhere. A *space-separated* run is only trusted right after a "CLABE" label
# cue — otherwise unrelated adjacent digit groups (refs, folios, phone+amount,
# dates) that happen to total 18 digits would be mis-redacted. The grouped
# capture is kept only if it normalises to exactly 18 digits.
_CLABE_RE = re.compile(r"(?<!\w)\d{18}(?!\w)")
_CLABE_SPACED_RE = re.compile(r"(?i)\bclabe\b[:\s]*(\d+(?: \d+)*)(?!\d)")

# Plain 16-digit alternative also uses \w boundaries to avoid matching inside
# alphanumeric tokens.
_CARD_RE = re.compile(r"(?<!\w)(?:\d{4}[ -]){3}\d{4}(?!\w)|(?<!\w)\d{16}(?!\w)")

_CURP_RE = re.compile(r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b")
_RFC_RE = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b")

# Bank account numbers collide with dates/amounts, so they are only detected
# when anchored to an account label. Per-bank account-number lengths researched
# (Jun 2026): BBVA 10, Hey Banco 10 (digital arm of Banregio), Santander ~11,
# Banregio 12 — so 10–12 digits is accepted. This window never reaches a 16-digit
# card or an 18-digit CLABE.
_ACCOUNT_MIN_DIGITS = 10
_ACCOUNT_MAX_DIGITS = 12

# Anchor cue: "Cuenta", "Cta", "No./Núm. de cuenta" (case/accent-insensitive),
# but NOT "Cuenta CLABE" (that 18-digit value is handled by the CLABE detector).
# Matched against accent-folded, lowercased text. A trailing run of 10–12 digits
# (single spaces tolerated) follows the cue; `(?!\d)` rejects longer runs so a
# 16-digit card / 18-digit CLABE behind a cue is not mis-matched as an account.
_ACCOUNT_RE = re.compile(
    # Leading (?<!\w) so a short cue like "cta" isn't matched as the tail of a
    # word (e.g. "recta", "directa"). Separator allows a trailing "." / ")" so
    # the common "Cta." / "Cuenta)" abbreviations are caught.
    r"(?<!\w)(?:no\.?\s*de\s+cuenta|num\.?\s*de\s+cuenta|cuenta|cta)\b"
    r"(?!\s+clabe)"
    r"[.:)\s]*"
    r"(\d+(?: \d+)*)(?!\d)"
)


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


def _digit_count(s):
    return sum(1 for c in s if c.isdigit())


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
        # Contiguous 18-digit CLABE anywhere.
        for m in _CLABE_RE.finditer(text):
            matches.append(Match("clabe", m.start(), m.end(), m.group()))
        # Space-grouped CLABE only right after a "CLABE" cue; keep it if it
        # normalises to exactly 18 digits (span covers the separating spaces).
        for m in _CLABE_SPACED_RE.finditer(text):
            if _digit_count(m.group(1)) == 18:
                matches.append(Match("clabe", m.start(1), m.end(1), m.group(1)))

    if "account" in categories:
        # Anchored to an account label so bare amounts/dates aren't matched.
        # Run the cue match on accent/case-folded text, then map the captured
        # digit-run span back to the original string.
        folded_text, text_idx_map = _fold_with_map(text)
        for am in _ACCOUNT_RE.finditer(folded_text):
            run = am.group(1)
            if not (_ACCOUNT_MIN_DIGITS <= _digit_count(run) <= _ACCOUNT_MAX_DIGITS):
                continue
            fstart, fend = am.start(1), am.end(1)
            orig_start = text_idx_map[fstart]
            orig_end = text_idx_map[fend - 1] + 1
            matches.append(
                Match("account", orig_start, orig_end, text[orig_start:orig_end])
            )

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
