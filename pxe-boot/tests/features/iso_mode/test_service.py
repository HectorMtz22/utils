from pathlib import Path

import pytest

from pxe_boot.features.iso_mode import service
from pxe_boot.shared.errors import AlreadyRunning, IsoNotFound
from pxe_boot.shared.iso_inspect import BootFiles


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("pxe_boot.shared.state.STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr("pxe_boot.features.iso_mode.service.TFTP_ROOT", tmp_path / "tftpboot")
    monkeypatch.setattr("pxe_boot.features.iso_mode.service.TFTP_PXE_SUBDIR", tmp_path / "tftpboot" / "pxe-boot")
    monkeypatch.setattr("pxe_boot.features.iso_mode.service.HTTP_SERVED_DIR", tmp_path / "http")
    monkeypatch.setattr("pxe_boot.features.iso_mode.service.TFTPBOOT_BACKUP", tmp_path / "backup.tar")
    monkeypatch.setattr(
        "pxe_boot.features.iso_mode.service.UNDIONLY_KPXE_FILE",
        tmp_path / "tftpboot" / "undionly.kpxe",
    )
    monkeypatch.setattr(
        "pxe_boot.features.iso_mode.service.SNPONLY_EFI_FILE",
        tmp_path / "tftpboot" / "snponly.efi",
    )


def _ubuntu_iso(tmp_path) -> Path:
    iso = tmp_path / "ubuntu-24.04.iso"
    iso.write_bytes(b"fake iso bytes")
    return iso


def _stub_mount(monkeypatch, tmp_path):
    mp = tmp_path / "mnt"
    (mp / "casper").mkdir(parents=True)
    (mp / "casper" / "vmlinuz").write_bytes(b"K")
    (mp / "casper" / "initrd").write_bytes(b"I")
    monkeypatch.setattr("pxe_boot.shared.iso_mount.attach", lambda p: mp)
    monkeypatch.setattr("pxe_boot.shared.iso_mount.detach", lambda p: None)
    return mp


def _ok_stubs(monkeypatch, tmp_path, captured_override=None):
    _stub_mount(monkeypatch, tmp_path)

    def _detect(iface_override=None):
        if captured_override is not None:
            captured_override.append(iface_override)
        return ("en0", "192.168.1.42")

    monkeypatch.setattr(
        "pxe_boot.features.iso_mode.service.detect_active_iface_and_ip",
        _detect,
    )
    # Stub network download so tests don't hit the internet.
    monkeypatch.setattr(
        "pxe_boot.features.iso_mode.service.download_to",
        lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True), dest.write_bytes(b"x"))[1],
    )
    monkeypatch.setattr("pxe_boot.shared.tftp.is_enabled", lambda: False)
    monkeypatch.setattr("pxe_boot.shared.tftp.enable", lambda **kw: None)
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.ensure_installed", lambda: False)
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.ensure_conf_dir_include", lambda: False)
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.write_dropin_text", lambda text: None)
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.write_dropin", lambda **kw: None)
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.start", lambda: None)
    monkeypatch.setattr("pxe_boot.shared.firewall.is_application_firewall_enabled", lambda: False)
    monkeypatch.setattr("pxe_boot.shared.http_server.find_free_port", lambda: 8080)
    monkeypatch.setattr("pxe_boot.shared.http_server.start", lambda directory, port: 99999)


def test_full_flow_writes_state_and_files(tmp_path, monkeypatch):
    iso = _ubuntu_iso(tmp_path)
    _ok_stubs(monkeypatch, tmp_path)
    service.run(iso)

    from pxe_boot.shared import state
    s = state.load()
    assert s.mode == "iso"
    assert s.iso_name == "ubuntu-24.04.iso"
    assert s.http_pid == 99999
    assert s.served_dir == str(tmp_path / "http")

    pxe_dir = tmp_path / "tftpboot" / "pxe-boot" / "ubuntu-24.04"
    assert (pxe_dir / "casper" / "vmlinuz").exists()
    assert (pxe_dir / "casper" / "initrd").exists()
    ipxe = pxe_dir / "ipxe.script"
    assert ipxe.exists()
    body = ipxe.read_text()
    assert "url=http://192.168.1.42:8080/ubuntu-24.04.iso" in body

    served_iso = tmp_path / "http" / "ubuntu-24.04.iso"
    assert served_iso.exists()
    assert served_iso.read_bytes() == b"fake iso bytes"


def test_refuses_when_state_exists(tmp_path, monkeypatch):
    iso = _ubuntu_iso(tmp_path)
    _ok_stubs(monkeypatch, tmp_path)
    from pxe_boot.shared import state
    state.save(state.State(
        mode="iso", iface="en0", ip="1.2.3.4",
        dnsmasq_installed_by_us=False, dnsmasq_main_conf_edited=False,
        tftp_was_enabled_before=False, started_at="x",
    ))
    with pytest.raises(AlreadyRunning):
        service.run(iso)


def test_missing_iso_raises(tmp_path, monkeypatch):
    _ok_stubs(monkeypatch, tmp_path)
    with pytest.raises(IsoNotFound):
        service.run(tmp_path / "nope.iso")


def test_iface_override_is_forwarded(tmp_path, monkeypatch):
    iso = _ubuntu_iso(tmp_path)
    seen: list[str | None] = []
    _ok_stubs(monkeypatch, tmp_path, captured_override=seen)
    service.run(iso, iface_override="en0")
    assert seen == ["en0"]
