import os
import sys

from pxe_boot.shared.errors import NeedsRoot


def require_root() -> None:
    if os.geteuid() != 0:
        argv = " ".join(sys.argv)
        raise NeedsRoot(f"this command needs sudo — re-run: sudo {argv}")
