import shutil
import subprocess
from pathlib import Path

from pxe_boot.shared import brew, dnsmasq, http_server, state, tftp
from pxe_boot.shared.paths import (
    NETBOOT_XYZ_FILE, TFTPBOOT_BACKUP, TFTP_PXE_SUBDIR, TFTP_ROOT,
)


def _wipe_our_tftp_files() -> None:
    try:
        NETBOOT_XYZ_FILE.unlink()
    except FileNotFoundError:
        pass
    if TFTP_PXE_SUBDIR.exists():
        shutil.rmtree(TFTP_PXE_SUBDIR)


def _restore_backup(backup: Path) -> None:
    TFTP_ROOT.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["tar", "-xf", str(backup), "-C", str(TFTP_ROOT)],
        check=False,
    )
    try:
        backup.unlink()
    except FileNotFoundError:
        pass


def run() -> None:
    s = state.load()

    # Best-effort stop, even if no state exists.
    try:
        dnsmasq.stop()
    except subprocess.CalledProcessError:
        pass
    if s and s.http_pid is not None:
        http_server.stop(s.http_pid)

    # Drop-in conf is always removed.
    dnsmasq.remove_dropin()

    # Only revert the main-conf edit if state says we made it (or if no state, best-effort).
    if s is None or s.dnsmasq_main_conf_edited:
        dnsmasq.revert_conf_dir_include()

    # Uninstall the brew formula only if we installed it.
    if s and s.dnsmasq_installed_by_us:
        try:
            brew.uninstall("dnsmasq")
            print("pxe-boot: dnsmasq uninstalled.")
        except subprocess.CalledProcessError:
            print("pxe-boot: warning — `brew uninstall dnsmasq` failed (leaving it).")
    elif s is not None:
        print("pxe-boot: dnsmasq left in place (was already installed before pxe-boot).")

    # Remove served dir and our tftpboot contents.
    if s and s.served_dir:
        served = Path(s.served_dir)
        if served.exists():
            shutil.rmtree(served)
    _wipe_our_tftp_files()

    # Restore tftpboot backup, if any.
    if s and s.tftpboot_backup_path:
        _restore_backup(Path(s.tftpboot_backup_path))

    # TFTP daemon: disable persistently unless it was on before us.
    if s and s.tftp_was_enabled_before:
        tftp.enable(persist=True)
        print("pxe-boot: TFTP daemon restored (was enabled before).")
    else:
        tftp.disable(persist=True)
        print("pxe-boot: TFTP daemon disabled.")

    state.clear()
    print("pxe-boot: Mac restored. Nothing left behind.")
