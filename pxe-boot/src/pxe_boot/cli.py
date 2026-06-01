import argparse
import sys

from pxe_boot import __version__
from pxe_boot.features.cleanup import command as cleanup_cmd
from pxe_boot.features.iso_mode import command as iso_cmd
from pxe_boot.features.netboot_mode import command as netboot_cmd
from pxe_boot.features.status import command as status_cmd
from pxe_boot.features.uninstall import command as uninstall_cmd
from pxe_boot.shared import prompts
from pxe_boot.shared.errors import PxeBootError


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pxe-boot",
        description="Set up a PXE boot server on macOS (netboot.xyz or a local ISO).",
    )
    group = p.add_mutually_exclusive_group()
    group.add_argument("--netboot", action="store_true", help="Mode 1: netboot.xyz")
    group.add_argument("--iso", metavar="PATH", help="Mode 2: direct boot from a local ISO")
    group.add_argument("--cleanup", action="store_true", help="Stop services, keep installed")
    group.add_argument("--uninstall", action="store_true", help="Remove everything pxe-boot set up")
    group.add_argument("--status", action="store_true", help="Show current state")
    p.add_argument(
        "--iface", metavar="IFACE", default=None,
        help="Force this network interface (e.g. en0) instead of the default-route autodetect",
    )
    p.add_argument("--version", action="version", version=f"pxe-boot {__version__}")
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.iso:
            iso_cmd.run(args)
        elif args.netboot:
            netboot_cmd.run(args)
        elif args.cleanup:
            cleanup_cmd.run(args)
        elif args.uninstall:
            uninstall_cmd.run(args)
        elif args.status:
            status_cmd.run(args)
        else:
            mode = prompts.select_mode()
            if mode == "netboot":
                netboot_cmd.run(args)
            else:
                iso_path = input("Path to ISO: ").strip()
                args.iso = iso_path
                iso_cmd.run(args)
    except PxeBootError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(e.exit_code)
