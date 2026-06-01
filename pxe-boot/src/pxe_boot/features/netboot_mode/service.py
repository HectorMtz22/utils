import datetime
import shutil
import subprocess
import urllib.request
from pathlib import Path

from pxe_boot.shared import dnsmasq, dnsmasq_conf, firewall, state, tftp
from pxe_boot.shared.errors import AlreadyRunning
from pxe_boot.shared.net import detect_active_iface_and_ip
from pxe_boot.shared.paths import (
    NETBOOT_XYZ_FILE_BIOS, NETBOOT_XYZ_URL_BIOS,
    NETBOOT_XYZ_FILE_EFI, NETBOOT_XYZ_URL_EFI,
    TFTPBOOT_BACKUP, TFTP_ROOT,
)

BOOT_FILE_BIOS = "netboot.xyz.kpxe"
BOOT_FILE_EFI = "netboot.xyz.efi"


def download_to(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as r, dest.open("wb") as f:
        shutil.copyfileobj(r, f)


# Kept for backward compatibility with existing tests.
def download_kpxe(dest: Path) -> None:
    download_to(NETBOOT_XYZ_URL_BIOS, dest)


def _backup_tftpboot_if_nonempty() -> Path | None:
    if not TFTP_ROOT.exists():
        TFTP_ROOT.mkdir(parents=True, exist_ok=True)
        return None
    if not any(TFTP_ROOT.iterdir()):
        return None
    TFTPBOOT_BACKUP.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["tar", "-cf", str(TFTPBOOT_BACKUP), "-C", str(TFTP_ROOT), "."],
        check=True,
    )
    return TFTPBOOT_BACKUP


def _ensure(url: str, dest: Path) -> None:
    if not dest.exists() or dest.stat().st_size == 0:
        download_to(url, dest)


def run(*, iface_override: str | None = None) -> None:
    if state.load() is not None:
        raise AlreadyRunning("pxe-boot is already running; use --cleanup or --status")

    iface, ip = detect_active_iface_and_ip(iface_override)
    backup = _backup_tftpboot_if_nonempty()

    _ensure(NETBOOT_XYZ_URL_BIOS, NETBOOT_XYZ_FILE_BIOS)
    _ensure(NETBOOT_XYZ_URL_EFI, NETBOOT_XYZ_FILE_EFI)

    tftp_was_enabled = tftp.is_enabled()
    if not tftp_was_enabled:
        tftp.enable()

    installed_now = dnsmasq.ensure_installed()
    main_edited = dnsmasq.ensure_conf_dir_include()
    dnsmasq.write_dropin_text(
        dnsmasq_conf.render_dual_arch(
            iface=iface, ip=ip,
            bios_boot=BOOT_FILE_BIOS,
            efi_boot=BOOT_FILE_EFI,
        )
    )
    dnsmasq.start()

    state.save(state.State(
        mode="netboot",
        iface=iface,
        ip=ip,
        dnsmasq_installed_by_us=installed_now,
        dnsmasq_main_conf_edited=main_edited,
        tftp_was_enabled_before=tftp_was_enabled,
        tftpboot_backup_path=str(backup) if backup else None,
        http_pid=None,
        served_dir=None,
        iso_name=None,
        started_at=datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
    ))

    print(f"pxe-boot: mode=netboot iface={iface} ip={ip}")
    print(f"  TFTP serving {BOOT_FILE_BIOS} (BIOS) + {BOOT_FILE_EFI} (UEFI) from {TFTP_ROOT}")
    print(f"  dnsmasq running in proxy-DHCP mode")
    print(f"  PC should see the netboot.xyz iPXE menu after PXE handshake.")
    if firewall.is_application_firewall_enabled():
        print("  WARNING: macOS Application Firewall is enabled — allow ports 67/UDP, 69/UDP, 80/TCP.")
