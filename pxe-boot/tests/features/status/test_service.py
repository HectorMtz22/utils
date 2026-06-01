import pytest

from pxe_boot.features.status import service


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr("pxe_boot.shared.state.STATE_FILE", tmp_path / "state.json")


def test_no_state(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.running", lambda: False)
    monkeypatch.setattr("pxe_boot.shared.tftp.is_enabled", lambda: False)
    monkeypatch.setattr("pxe_boot.shared.http_server.is_alive", lambda pid: False)
    service.run()
    out = capsys.readouterr().out
    assert "no active state" in out.lower() or "not running" in out.lower()


def test_with_state(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.running", lambda: True)
    monkeypatch.setattr("pxe_boot.shared.tftp.is_enabled", lambda: True)
    monkeypatch.setattr("pxe_boot.shared.http_server.is_alive", lambda pid: True)
    from pxe_boot.shared import state
    state.save(state.State(
        mode="iso", iface="en0", ip="192.168.1.42",
        dnsmasq_installed_by_us=True, dnsmasq_main_conf_edited=True,
        tftp_was_enabled_before=False,
        http_pid=4242, served_dir="/tmp/x", iso_name="ubuntu.iso",
        started_at="2026-06-01T00:00:00Z",
    ))
    service.run()
    out = capsys.readouterr().out
    assert "iso" in out.lower()
    assert "192.168.1.42" in out
    assert "ubuntu.iso" in out
    assert "dnsmasq" in out.lower()
