"""Module-level skip guard for tests that need the native `zbar` library.

`pyzbar` imports fine but raises ImportError at *call* time (and sometimes at
import time) when the `libzbar` shared library can't be loaded. On macOS the
Homebrew dylib lives outside the default search path, so CI or a bare machine
without `brew install zbar` (and `DYLD_LIBRARY_PATH`) would hard-fail. Tests
do `pytestmark = zbar_skip.SKIP` so the whole module skips cleanly instead.
"""

import pytest

try:
    from pyzbar.pyzbar import decode  # noqa: F401

    ZBAR_AVAILABLE = True
    _REASON = ""
except ImportError as e:  # pragma: no cover - env-dependent
    ZBAR_AVAILABLE = False
    _REASON = f"zbar shared library unavailable: {e}"

SKIP = pytest.mark.skipif(not ZBAR_AVAILABLE, reason=_REASON)
