import shutil
import subprocess
import tempfile
from pathlib import Path

from pxe_boot.shared.errors import BootFilesNotFound, IsoInvalid, IsoNotFound

# Top-level directories that may contain kernel + initrd. Matched against
# `iso_inspect._CANDIDATES` — only these directories are extracted so we
# don't spill 3 GB onto disk for a 10 MB kernel.
_BOOT_DIRS = ("casper", "isolinux", "boot")

_TMP_PREFIX = "pxe-boot-iso-"


def attach(iso_path: Path) -> Path:
    """Extract the recognised boot directories of an ISO9660 image into a
    fresh temp dir and return that dir. Replaces `hdiutil attach`, which on
    macOS 14+ refuses to auto-mount hybrid GPT+ISO9660 images like Ubuntu
    Server. `bsdtar` reads ISO9660 directly and works on every valid ISO.

    The returned path behaves like a mountpoint to the rest of the code
    (`iso_inspect.find_boot_files`, `iso_mode.service` shutil.copyfile).
    Call `detach()` when done to remove the temp dir.
    """
    if not iso_path.is_file():
        raise IsoNotFound(f"{iso_path} not found")

    try:
        listing = subprocess.run(
            ["bsdtar", "-tf", str(iso_path)],
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
    except subprocess.CalledProcessError as e:
        raise IsoInvalid(
            f"bsdtar could not read {iso_path.name}: {e.stderr or '(no stderr)'}"
        ) from e

    present = sorted({d for d in _BOOT_DIRS if any(p.startswith(d + "/") for p in listing)})
    if not present:
        raise BootFilesNotFound(
            f"no recognised boot dirs in {iso_path.name} "
            f"(looked for: {', '.join(_BOOT_DIRS)})"
        )

    temp_dir = Path(tempfile.mkdtemp(prefix=_TMP_PREFIX))
    try:
        subprocess.run(
            # --no-same-permissions: don't preserve the ISO9660 read-only mode,
            # otherwise rmtree on detach fails with PermissionError when bsdtar
            # was run as root (Homebrew/sudo case).
            ["bsdtar", "-xf", str(iso_path), "--no-same-permissions",
             "-C", str(temp_dir), *present],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        _force_rmtree(temp_dir)
        raise IsoInvalid(
            f"bsdtar extraction failed: {e.stderr.decode(errors='replace') or '(no stderr)'}"
        ) from e

    return temp_dir


def detach(mountpoint: Path) -> None:
    """Remove the temp dir created by `attach()`. Guarded by the prefix so
    we never rmtree something we didn't create."""
    if mountpoint.exists() and mountpoint.name.startswith(_TMP_PREFIX):
        _force_rmtree(mountpoint)


def _force_rmtree(path: Path) -> None:
    """rmtree that survives read-only files/dirs left over from a partial
    extract."""
    subprocess.run(["chmod", "-R", "u+rwX", str(path)], check=False)
    shutil.rmtree(path, ignore_errors=True)
