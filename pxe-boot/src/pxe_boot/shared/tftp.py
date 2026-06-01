import subprocess

from pxe_boot.shared.paths import TFTP_PLIST

_SERVICE_TARGET = "system/com.apple.tftpd"


def is_enabled() -> bool:
    """Return True if `com.apple.tftpd` is currently bootstrapped in the
    system domain."""
    res = subprocess.run(
        ["sudo", "launchctl", "print", _SERVICE_TARGET],
        capture_output=True, text=True,
    )
    return res.returncode == 0


def enable(*, persist: bool = False) -> None:
    """Bootstrap tftp into the system domain. `persist` is accepted for API
    symmetry but bootstrap is already persistent across reboots on macOS 14+."""
    cmd = ["sudo", "launchctl", "bootstrap", "system", str(TFTP_PLIST)]
    # bootstrap of an already-bootstrapped service errors; tolerate it so
    # repeated --netboot runs are idempotent.
    subprocess.run(cmd, check=False)


def disable(*, persist: bool = False) -> None:
    """Bootout tftp from the system domain."""
    cmd = ["sudo", "launchctl", "bootout", "system", str(TFTP_PLIST)]
    # bootout of an already-unloaded daemon errors; tolerate it.
    subprocess.run(cmd, check=False)
