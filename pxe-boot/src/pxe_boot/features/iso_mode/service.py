import datetime
import shutil
import subprocess
from pathlib import Path

from pxe_boot.features.iso_mode import ipxe_script
from pxe_boot.shared import dnsmasq, firewall, http_server, iso_mount, state, tftp
from pxe_boot.shared.errors import AlreadyRunning, IsoNotFound
from pxe_boot.shared.iso_inspect import find_boot_files
from pxe_boot.shared.net import detect_active_iface_and_ip
from pxe_boot.shared.paths import (
    HTTP_SERVED_DIR, TFTPBOOT_BACKUP, TFTP_PXE_SUBDIR, TFTP_ROOT,
)


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


def run(iso_path: Path) -> None:
    if state.load() is not None:
        raise AlreadyRunning("pxe-boot is already running; use --cleanup or --status")
    if not iso_path.is_file():
        raise IsoNotFound(f"{iso_path} not found")

    iface, ip = detect_active_iface_and_ip()
    backup = _backup_tftpboot_if_nonempty()

    iso_stem = iso_path.stem
    iso_name = iso_path.name

    mountpoint = iso_mount.attach(iso_path)
    try:
        bf = find_boot_files(mountpoint)
        pxe_dir = TFTP_PXE_SUBDIR / iso_stem
        (pxe_dir / Path(bf.kernel_rel).parent).mkdir(parents=True, exist_ok=True)
        (pxe_dir / Path(bf.initrd_rel).parent).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(mountpoint / bf.kernel_rel, pxe_dir / bf.kernel_rel)
        shutil.copyfile(mountpoint / bf.initrd_rel, pxe_dir / bf.initrd_rel)

        HTTP_SERVED_DIR.mkdir(parents=True, exist_ok=True)
        served_iso = HTTP_SERVED_DIR / iso_name
        shutil.copyfile(iso_path, served_iso)
    finally:
        iso_mount.detach(mountpoint)

    port = http_server.find_free_port()
    if bf.distro_hint == "ubuntu":
        script = ipxe_script.render_ubuntu(
            ip=ip, port=port, iso_name=iso_name, iso_stem=iso_stem,
            kernel_rel=bf.kernel_rel, initrd_rel=bf.initrd_rel,
        )
    else:
        script = ipxe_script.render_generic(
            ip=ip, iso_stem=iso_stem,
            kernel_rel=bf.kernel_rel, initrd_rel=bf.initrd_rel,
        )
    (pxe_dir / "ipxe.script").write_text(script)

    pid = http_server.start(directory=HTTP_SERVED_DIR, port=port)

    boot_file = f"pxe-boot/{iso_stem}/ipxe.script"
    tftp_was_enabled = tftp.is_enabled()
    if not tftp_was_enabled:
        tftp.enable()
    installed_now = dnsmasq.ensure_installed()
    main_edited = dnsmasq.ensure_conf_dir_include()
    dnsmasq.write_dropin(iface=iface, ip=ip, boot_file=boot_file)
    dnsmasq.start()

    state.save(state.State(
        mode="iso",
        iface=iface,
        ip=ip,
        dnsmasq_installed_by_us=installed_now,
        dnsmasq_main_conf_edited=main_edited,
        tftp_was_enabled_before=tftp_was_enabled,
        tftpboot_backup_path=str(backup) if backup else None,
        http_pid=pid,
        served_dir=str(HTTP_SERVED_DIR),
        iso_name=iso_name,
        started_at=datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
    ))

    print(f"pxe-boot: mode=iso iface={iface} ip={ip}")
    print(f"  ISO: {iso_name} (hint: {bf.distro_hint})")
    print(f"  TFTP boot file: {boot_file}")
    print(f"  HTTP serving {served_iso.name} at http://{ip}:{port}/")
    if bf.distro_hint == "generic":
        print("  WARNING: non-Ubuntu ISO — boot is best-effort.")
    if firewall.is_application_firewall_enabled():
        print("  WARNING: macOS Application Firewall is enabled — allow 67/UDP, 69/UDP, " + str(port) + "/TCP.")
