import os
import signal
import subprocess
from pathlib import Path

from pxe_boot.shared import brew, dnsmasq_conf
from pxe_boot.shared.paths import DNSMASQ_PID_FILE

DROPIN_NAME = "pxe-boot.conf"
CONF_DIR_LINE = "conf-dir=%s/etc/dnsmasq.d/,*.conf"


def dropin_path() -> Path:
    return brew.prefix() / "etc" / "dnsmasq.d" / DROPIN_NAME


def main_conf_path() -> Path:
    return brew.prefix() / "etc" / "dnsmasq.conf"


def _binary() -> Path:
    return brew.prefix() / "sbin" / "dnsmasq"


def ensure_installed() -> bool:
    """Returns True iff we installed it just now."""
    if brew.installed("dnsmasq"):
        return False
    brew.install("dnsmasq")
    return True


def ensure_conf_dir_include() -> bool:
    """Append `conf-dir=...` to main dnsmasq.conf iff missing. Returns True if we edited it.
    Kept for backward compatibility — `start()` now points dnsmasq directly at our drop-in
    so this is not load-bearing for runtime, but is still called by callers for state tracking."""
    main = main_conf_path()
    include_line = CONF_DIR_LINE % brew.prefix()
    if main.exists():
        text = main.read_text()
        if "conf-dir=" in text:
            return False
    else:
        text = ""
    main.parent.mkdir(parents=True, exist_ok=True)
    if text and not text.endswith("\n"):
        text += "\n"
    main.write_text(text + include_line + "\n")
    return True


def write_dropin(*, iface: str, ip: str, boot_file: str) -> None:
    """Write the single-boot-file dnsmasq config (Mode 1 legacy callers)."""
    write_dropin_text(dnsmasq_conf.render(iface=iface, ip=ip, boot_file=boot_file))


def write_dropin_text(text: str) -> None:
    """Write a pre-rendered drop-in config. Used by callers that need a
    multi-arch or chained config beyond the single-boot-file template."""
    path = dropin_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def remove_dropin() -> None:
    try:
        dropin_path().unlink()
    except FileNotFoundError:
        pass


def revert_conf_dir_include() -> None:
    """Strip the `conf-dir=...` line we appended from main dnsmasq.conf."""
    main = main_conf_path()
    if not main.exists():
        return
    include_line = CONF_DIR_LINE % brew.prefix()
    lines = main.read_text().splitlines(keepends=True)
    kept = [ln for ln in lines if ln.rstrip("\n") != include_line]
    main.write_text("".join(kept))


def _kill_any_dnsmasq() -> None:
    """Kill any lingering dnsmasq before we (re)start ours. Covers three
    cases: a stale process from our own PID file, a brew-services-managed
    instance left over from an older pxe-boot version, and any other
    dnsmasq holding port 67. The pkill is broad but safe in our context —
    pxe-boot owns this dnsmasq for the duration of a session."""
    # 1. Ours (PID-file path).
    stop()
    # 2. Brew-services-managed instance, if any. Errors are silenced.
    try:
        subprocess.run(
            ["sudo", "brew", "services", "stop", "dnsmasq"],
            check=False, capture_output=True,
        )
    except FileNotFoundError:
        pass
    # 3. Stragglers (e.g. from a manual brew install + launchd plist).
    subprocess.run(["pkill", "-f", "dnsmasq"], check=False, capture_output=True)


def start() -> None:
    """Spawn dnsmasq directly with our drop-in config. dnsmasq daemonizes itself
    and writes its PID to DNSMASQ_PID_FILE. We bypass `brew services` to avoid
    Homebrew formula-service quirks (e.g. missing #plist in some installs)."""
    _kill_any_dnsmasq()

    DNSMASQ_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    # If a stale PID file is there from a prior failed run, remove it so
    # dnsmasq's startup doesn't refuse.
    try:
        DNSMASQ_PID_FILE.unlink()
    except FileNotFoundError:
        pass
    subprocess.run(
        [
            str(_binary()),
            f"--conf-file={dropin_path()}",
            f"--pid-file={DNSMASQ_PID_FILE}",
        ],
        check=True,
    )


def stop() -> None:
    """Kill the dnsmasq we started, if any, then drop the PID file."""
    if not DNSMASQ_PID_FILE.exists():
        return
    try:
        pid = int(DNSMASQ_PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
    except (ValueError, ProcessLookupError):
        pass
    try:
        DNSMASQ_PID_FILE.unlink()
    except FileNotFoundError:
        pass


def running() -> bool:
    """True iff the PID in DNSMASQ_PID_FILE corresponds to a live process."""
    if not DNSMASQ_PID_FILE.exists():
        return False
    try:
        pid = int(DNSMASQ_PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, OSError):
        return False
