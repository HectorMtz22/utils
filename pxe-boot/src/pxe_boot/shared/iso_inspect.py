from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pxe_boot.shared.errors import BootFilesNotFound


@dataclass(frozen=True)
class BootFiles:
    kernel_rel: str
    initrd_rel: str
    distro_hint: Literal["ubuntu", "generic"]


# Ordered: most-specific first. Each entry: (kernel_rel, initrd_rel, hint).
_CANDIDATES = [
    ("casper/vmlinuz", "casper/initrd", "ubuntu"),
    ("isolinux/vmlinuz", "isolinux/initrd.img", "generic"),
    ("boot/vmlinuz", "boot/initrd.img", "generic"),
]


def find_boot_files(root: Path) -> BootFiles:
    for kernel_rel, initrd_rel, hint in _CANDIDATES:
        if (root / kernel_rel).is_file() and (root / initrd_rel).is_file():
            return BootFiles(kernel_rel=kernel_rel, initrd_rel=initrd_rel, distro_hint=hint)
    searched = ", ".join(f"{k}+{i}" for k, i, _ in _CANDIDATES)
    raise BootFilesNotFound(f"no boot files found under {root} (searched: {searched})")
