from argparse import Namespace
from pathlib import Path

from pxe_boot.features.iso_mode import service
from pxe_boot.shared.privileges import require_root


def run(args: Namespace) -> None:
    require_root()
    service.run(Path(args.iso))
