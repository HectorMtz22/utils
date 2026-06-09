"""Module-level skip guard for tests that need the native `tesseract` binary.

`pytesseract` imports fine but fails at *call* time when the `tesseract`
executable isn't on PATH (raising TesseractNotFoundError). On a bare machine or
in CI without `brew install tesseract` the OCR pass can't run, so tests do
`pytestmark = tesseract_skip.SKIP` to skip the whole module cleanly instead of
hard-failing.
"""

import pytest

try:
    import pytesseract
except ImportError as e:  # pragma: no cover - env-dependent
    TESSERACT_AVAILABLE = False
    _REASON = f"pytesseract not installed: {e}"
else:
    try:
        pytesseract.get_tesseract_version()  # raises if the binary is missing
        TESSERACT_AVAILABLE = True
        _REASON = ""
    except pytesseract.TesseractNotFoundError as e:  # pragma: no cover - env-dependent
        TESSERACT_AVAILABLE = False
        _REASON = f"tesseract binary unavailable: {e}"

SKIP = pytest.mark.skipif(not TESSERACT_AVAILABLE, reason=_REASON)
