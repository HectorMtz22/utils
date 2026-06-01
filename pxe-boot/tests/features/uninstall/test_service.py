import shutil
import subprocess
from pathlib import Path

import pytest

from pxe_boot.features.uninstall import service


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr("pxe_boot.shared.state.STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(
        "pxe_boot.features.uninstall.service.TFTP_ROOT", tmp_path / "tftpboot",
    )
    monkeypatch.setattr(
        "pxe_boot.features.uninstall.service.TFTP_PXE_SUBDIR",
        tmp_path / "tftpboot" / "pxe-boot",
    )
    monkeypatch.setattr(
        "pxe_boot.features.uninstall.service.NETBOOT_XYZ_FILE",
        tmp_path / "tftpboot" / "netboot.xyz.kpxe",
    )
    monkeypatch.setattr(
        "pxe_boot.features.uninstall.service.TFTPBOOT_BACKUP", tmp_path / "backup.tar",
    )


def _record(monkeypatch):
    calls = {
        "stop": 0, "disable": [], "enable": [], "killed": [],
        "remove_dropin": 0, "revert_include": 0, "uninstalled": [],
    }
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.stop", lambda: calls.__setitem__("stop", calls["stop"] + 1))
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.remove_dropin", lambda: calls.__setitem__("remove_dropin", calls["remove_dropin"] + 1))
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.revert_conf_dir_include", lambda: calls.__setitem__("revert_include", calls["revert_include"] + 1))
    monkeypatch.setattr("pxe_boot.shared.brew.uninstall", lambda f: calls["uninstalled"].append(f))
    monkeypatch.setattr("pxe_boot.shared.tftp.disable", lambda **kw: calls["disable"].append(kw))
    monkeypatch.setattr("pxe_boot.shared.tftp.enable", lambda **kw: calls["enable"].append(kw))
    monkeypatch.setattr("pxe_boot.shared.http_server.is_alive", lambda pid: True)
    monkeypatch.setattr("pxe_boot.shared.http_server.stop", lambda pid: calls["killed"].append(pid))
    return calls


def test_no_state_best_effort(tmp_path, monkeypatch):
    calls = _record(monkeypatch)
    service.run()
    assert calls["remove_dropin"] == 1
    assert calls["revert_include"] == 1


def test_uninstalls_dnsmasq_if_we_installed_it(tmp_path, monkeypatch):
    calls = _record(monkeypatch)
    from pxe_boot.shared import state
    state.save(state.State(
        mode="netboot", iface="en0", ip="1.2.3.4",
        dnsmasq_installed_by_us=True, dnsmasq_main_conf_edited=True,
        tftp_was_enabled_before=False, started_at="x",
    ))
    service.run()
    assert calls["uninstalled"] == ["dnsmasq"]
    assert calls["disable"] == [{"persist": True}]
    assert state.load() is None


def test_preserves_dnsmasq_if_preexisting(tmp_path, monkeypatch):
    calls = _record(monkeypatch)
    from pxe_boot.shared import state
    state.save(state.State(
        mode="netboot", iface="en0", ip="1.2.3.4",
        dnsmasq_installed_by_us=False, dnsmasq_main_conf_edited=False,
        tftp_was_enabled_before=False, started_at="x",
    ))
    service.run()
    assert calls["uninstalled"] == []
    assert calls["revert_include"] == 0  # we didn't edit it, don't revert


def test_restores_tftp_if_was_enabled(tmp_path, monkeypatch):
    calls = _record(monkeypatch)
    from pxe_boot.shared import state
    state.save(state.State(
        mode="netboot", iface="en0", ip="1.2.3.4",
        dnsmasq_installed_by_us=False, dnsmasq_main_conf_edited=False,
        tftp_was_enabled_before=True, started_at="x",
    ))
    service.run()
    assert calls["enable"] == [{"persist": True}]


def test_restores_tftpboot_from_backup(tmp_path, monkeypatch):
    calls = _record(monkeypatch)
    tftp_root = tmp_path / "tftpboot"
    tftp_root.mkdir()
    (tftp_root / "netboot.xyz.kpxe").write_bytes(b"k")
    backup = tmp_path / "backup.tar"
    src = tmp_path / "src"
    src.mkdir()
    (src / "preexisting").write_text("hi")
    subprocess.run(["tar", "-cf", str(backup), "-C", str(src), "."], check=True)

    from pxe_boot.shared import state
    state.save(state.State(
        mode="netboot", iface="en0", ip="1.2.3.4",
        dnsmasq_installed_by_us=False, dnsmasq_main_conf_edited=False,
        tftp_was_enabled_before=False,
        tftpboot_backup_path=str(backup),
        started_at="x",
    ))
    service.run()
    assert (tftp_root / "preexisting").read_text() == "hi"
    assert not (tftp_root / "netboot.xyz.kpxe").exists()


def test_kills_http_pid(tmp_path, monkeypatch):
    calls = _record(monkeypatch)
    from pxe_boot.shared import state
    state.save(state.State(
        mode="iso", iface="en0", ip="1.2.3.4",
        dnsmasq_installed_by_us=False, dnsmasq_main_conf_edited=False,
        tftp_was_enabled_before=False,
        http_pid=4242, served_dir=str(tmp_path / "served"),
        started_at="x",
    ))
    (tmp_path / "served").mkdir()
    service.run()
    assert calls["killed"] == [4242]
    assert not (tmp_path / "served").exists()
