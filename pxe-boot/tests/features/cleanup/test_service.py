import subprocess

import pytest

from pxe_boot.features.cleanup import service


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr("pxe_boot.shared.state.STATE_FILE", tmp_path / "state.json")


def _record(monkeypatch):
    calls = {"stop": 0, "disable": 0, "killed": []}
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.stop", lambda: calls.__setitem__("stop", calls["stop"] + 1))
    monkeypatch.setattr("pxe_boot.shared.tftp.disable", lambda **kw: calls.__setitem__("disable", calls["disable"] + 1))
    monkeypatch.setattr("pxe_boot.shared.http_server.is_alive", lambda pid: True)
    monkeypatch.setattr("pxe_boot.shared.http_server.stop", lambda pid: calls["killed"].append(pid))
    return calls


def test_no_state_returns_quietly(tmp_path, monkeypatch, capsys):
    calls = _record(monkeypatch)
    service.run()
    assert calls["stop"] == 0
    assert calls["disable"] == 0
    out = capsys.readouterr().out
    assert "nothing" in out.lower()


def test_with_state_stops_everything(tmp_path, monkeypatch):
    calls = _record(monkeypatch)
    from pxe_boot.shared import state
    state.save(state.State(
        mode="iso", iface="en0", ip="1.2.3.4",
        dnsmasq_installed_by_us=False, dnsmasq_main_conf_edited=False,
        tftp_was_enabled_before=False,
        http_pid=12345, served_dir="/tmp/x", iso_name="x.iso",
        started_at="x",
    ))
    service.run()
    assert calls["stop"] == 1
    assert calls["disable"] == 1
    assert calls["killed"] == [12345]


def test_skips_http_kill_when_pid_none(tmp_path, monkeypatch):
    calls = _record(monkeypatch)
    from pxe_boot.shared import state
    state.save(state.State(
        mode="netboot", iface="en0", ip="1.2.3.4",
        dnsmasq_installed_by_us=False, dnsmasq_main_conf_edited=False,
        tftp_was_enabled_before=False,
        started_at="x",
    ))
    service.run()
    assert calls["killed"] == []


def test_tolerates_already_stopped_dnsmasq(tmp_path, monkeypatch):
    calls = _record(monkeypatch)

    def boom():
        raise subprocess.CalledProcessError(1, ["brew", "services", "stop", "dnsmasq"])

    monkeypatch.setattr("pxe_boot.shared.dnsmasq.stop", boom)
    from pxe_boot.shared import state
    state.save(state.State(
        mode="netboot", iface="en0", ip="1.2.3.4",
        dnsmasq_installed_by_us=False, dnsmasq_main_conf_edited=False,
        tftp_was_enabled_before=False,
        started_at="x",
    ))
    service.run()  # must not raise
    assert calls["disable"] == 1
