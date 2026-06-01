from argparse import Namespace

from pxe_boot.features.status import service


def run(args: Namespace) -> None:
    service.run()
