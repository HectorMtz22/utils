from pathlib import Path
from unittest.mock import patch

import pytest

from pxe_boot.features.netboot_mode import service
from pxe_boot.shared.errors import AlreadyRunning


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("pxe_boot.shared.state.STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr("pxe_boot.shared.paths.TFTP_ROOT", tmp_path / "tftpboot")
    monkeypatch.setattr("pxe_boot.shared.paths.NETBOOT_XYZ_FILE", tmp_path / "tftpboot" / "netboot.xyz.kpxe")
    monkeypatch.setattr("pxe_boot.shared.paths.TFTPBOOT_BACKUP", tmp_path / "backup.tar")
    monkeypatch.setattr(
        "pxe_boot.features.netboot_mode.service.NETBOOT_XYZ_FILE",
        tmp_path / "tftpboot" / "netboot.xyz.kpxe",
    )
    monkeypatch.setattr(
        "pxe_boot.features.netboot_mode.service.TFTP_ROOT",
        tmp_path / "tftpboot",
    )
    monkeypatch.setattr(
        "pxe_boot.features.netboot_mode.service.TFTPBOOT_BACKUP",
        tmp_path / "backup.tar",
    )


def _ok_stubs(monkeypatch):
    monkeypatch.setattr(
        "pxe_boot.features.netboot_mode.service.detect_active_iface_and_ip",
        lambda: ("en0", "192.168.1.42"),
    )
    monkeypatch.setattr(
        "pxe_boot.features.netboot_mode.service.download_kpxe",
        lambda dest: dest.parent.mkdir(parents=True, exist_ok=True) or dest.write_bytes(b"kpxe"),
    )
    monkeypatch.setattr("pxe_boot.shared.tftp.is_enabled", lambda: False)
    monkeypatch.setattr("pxe_boot.shared.tftp.enable", lambda **kw: None)
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.ensure_installed", lambda: True)
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.ensure_conf_dir_include", lambda: True)
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.write_dropin", lambda **kw: None)
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.start", lambda: None)
    monkeypatch.setattr("pxe_boot.shared.firewall.is_application_firewall_enabled", lambda: False)


def test_full_flow_writes_state(tmp_path, monkeypatch):
    _ok_stubs(monkeypatch)
    service.run()
    from pxe_boot.shared import state
    s = state.load()
    assert s is not None
    assert s.mode == "netboot"
    assert s.iface == "en0"
    assert s.ip == "192.168.1.42"
    assert s.dnsmasq_installed_by_us is True
    assert s.dnsmasq_main_conf_edited is True
    assert s.tftp_was_enabled_before is False
    assert s.http_pid is None


def test_refuses_when_state_exists(tmp_path, monkeypatch):
    _ok_stubs(monkeypatch)
    from pxe_boot.shared import state
    state.save(state.State(
        mode="netboot", iface="en0", ip="1.2.3.4",
        dnsmasq_installed_by_us=False, dnsmasq_main_conf_edited=False,
        tftp_was_enabled_before=False, started_at="x",
    ))
    with pytest.raises(AlreadyRunning):
        service.run()


def test_records_prior_tftp_state_true(tmp_path, monkeypatch):
    _ok_stubs(monkeypatch)
    monkeypatch.setattr("pxe_boot.shared.tftp.is_enabled", lambda: True)
    service.run()
    from pxe_boot.shared import state
    assert state.load().tftp_was_enabled_before is True


def test_skips_kpxe_download_if_present(tmp_path, monkeypatch):
    _ok_stubs(monkeypatch)
    dest = tmp_path / "tftpboot" / "netboot.xyz.kpxe"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"already here")
    calls = []
    monkeypatch.setattr(
        "pxe_boot.features.netboot_mode.service.download_kpxe",
        lambda d: calls.append(d),
    )
    service.run()
    assert calls == []
