import subprocess

from pxe_boot.shared.paths import TFTP_PLIST


def is_enabled() -> bool:
    res = subprocess.run(
        ["sudo", "launchctl", "list"], capture_output=True, text=True,
    )
    if res.returncode != 0:
        return False
    return any("com.apple.tftpd" in line for line in res.stdout.splitlines())


def enable(*, persist: bool = False) -> None:
    cmd = ["sudo", "launchctl", "load"]
    if persist:
        cmd.append("-w")
    cmd.append(str(TFTP_PLIST))
    subprocess.run(cmd, check=True)


def disable(*, persist: bool = False) -> None:
    cmd = ["sudo", "launchctl", "unload"]
    if persist:
        cmd.append("-w")
    cmd.append(str(TFTP_PLIST))
    # unload of an already-unloaded daemon returns non-zero; tolerate it.
    subprocess.run(cmd, check=False)
