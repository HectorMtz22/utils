from dataclasses import asdict
from pathlib import Path

import pytest

from pxe_boot.shared.state import State, clear, load, save


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    monkeypatch.setattr("pxe_boot.shared.state.STATE_FILE", path)
    return path


class TestState:
    def test_load_missing_returns_none(self, state_file):
        assert load() is None

    def test_save_then_load_round_trip(self, state_file):
        s = State(
            mode="netboot",
            iface="en0",
            ip="192.168.1.42",
            dnsmasq_installed_by_us=True,
            dnsmasq_main_conf_edited=False,
            tftp_was_enabled_before=False,
            tftpboot_backup_path=None,
            http_pid=None,
            served_dir=None,
            iso_name=None,
            started_at="2026-06-01T12:34:56Z",
        )
        save(s)
        loaded = load()
        assert loaded == s

    def test_save_creates_parent_dir(self, tmp_path, monkeypatch):
        nested = tmp_path / "deep" / "deeper" / "state.json"
        monkeypatch.setattr("pxe_boot.shared.state.STATE_FILE", nested)
        s = State(
            mode="iso",
            iface="en0",
            ip="10.0.0.1",
            dnsmasq_installed_by_us=False,
            dnsmasq_main_conf_edited=True,
            tftp_was_enabled_before=True,
            tftpboot_backup_path="/var/db/pxe-boot/tftpboot.backup.tar",
            http_pid=12345,
            served_dir="/var/db/pxe-boot/http",
            iso_name="ubuntu.iso",
            started_at="2026-06-01T00:00:00Z",
        )
        save(s)
        assert nested.exists()

    def test_load_tolerates_missing_optional_keys(self, state_file):
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            '{"mode":"netboot","iface":"en0","ip":"1.2.3.4",'
            '"dnsmasq_installed_by_us":false,"dnsmasq_main_conf_edited":false,'
            '"tftp_was_enabled_before":false,"started_at":"x"}'
        )
        loaded = load()
        assert loaded is not None
        assert loaded.mode == "netboot"
        assert loaded.http_pid is None
        assert loaded.iso_name is None

    def test_clear_removes_file(self, state_file):
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("{}")
        clear()
        assert not state_file.exists()

    def test_clear_is_idempotent(self, state_file):
        clear()  # nothing to remove, must not raise
