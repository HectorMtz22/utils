from argparse import Namespace

from pxe_boot.features.netboot_mode import service
from pxe_boot.shared.privileges import require_root


def run(args: Namespace) -> None:
    require_root()
    service.run(iface_override=getattr(args, "iface", None))
