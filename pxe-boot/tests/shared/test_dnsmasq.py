import os
import signal
import subprocess
from pathlib import Path

import pytest

from pxe_boot.shared import dnsmasq


@pytest.fixture
def fake_prefix(monkeypatch):
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.brew.prefix", lambda: Path("/opt/homebrew"))


@pytest.fixture
def fake_pid_file(tmp_path, monkeypatch):
    pid_file = tmp_path / "dnsmasq.pid"
    monkeypatch.setattr("pxe_boot.shared.dnsmasq.DNSMASQ_PID_FILE", pid_file)
    return pid_file


def _find_dnsmasq_spawn(commands: list[list[str]]) -> list[str]:
    """Find the dnsmasq spawn command (with --conf-file) among the captured calls."""
    for cmd in commands:
        if cmd and cmd[0].endswith("/dnsmasq"):
            return cmd
    raise AssertionError(f"no dnsmasq spawn found in: {commands}")


class TestStart:
    def test_spawns_dnsmasq_with_conf_and_pid_file(self, fake_prefix, fake_pid_file, monkeypatch):
        seen: list[list[str]] = []

        def fake(cmd, **kw):
            seen.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr("pxe_boot.shared.dnsmasq.subprocess.run", fake)
        dnsmasq.start()
        spawn = _find_dnsmasq_spawn(seen)
        assert spawn[0] == "/opt/homebrew/sbin/dnsmasq"
        assert "--conf-file=/opt/homebrew/etc/dnsmasq.d/pxe-boot.conf" in spawn
        assert f"--pid-file={fake_pid_file}" in spawn

    def test_clears_stale_pid_file_before_spawning(self, fake_prefix, fake_pid_file, monkeypatch):
        fake_pid_file.write_text("99999")

        def fake(cmd, **kw):
            if cmd and cmd[0].endswith("/dnsmasq"):
                # By the time dnsmasq actually runs, the stale PID file should be gone.
                assert not fake_pid_file.exists()
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr("pxe_boot.shared.dnsmasq.subprocess.run", fake)
        dnsmasq.start()

    def test_kills_stragglers_before_spawning(self, fake_prefix, fake_pid_file, monkeypatch):
        seen: list[list[str]] = []

        def fake(cmd, **kw):
            seen.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr("pxe_boot.shared.dnsmasq.subprocess.run", fake)
        dnsmasq.start()
        # Some call must be a pkill -f dnsmasq before the dnsmasq spawn.
        pkill_idx = next(i for i, c in enumerate(seen) if c[:2] == ["pkill", "-f"])
        spawn_idx = next(i for i, c in enumerate(seen) if c and c[0].endswith("/dnsmasq"))
        assert pkill_idx < spawn_idx


class TestStop:
    def test_no_pid_file_is_noop(self, fake_pid_file):
        # Missing PID file: nothing to kill, no error.
        dnsmasq.stop()

    def test_sends_sigterm_then_removes_pid_file(self, fake_pid_file, monkeypatch):
        fake_pid_file.write_text("12345")
        killed: list[tuple[int, int]] = []
        monkeypatch.setattr("pxe_boot.shared.dnsmasq.os.kill", lambda pid, sig: killed.append((pid, sig)))
        dnsmasq.stop()
        assert killed == [(12345, signal.SIGTERM)]
        assert not fake_pid_file.exists()

    def test_dead_pid_is_tolerated(self, fake_pid_file, monkeypatch):
        fake_pid_file.write_text("99999")

        def fake_kill(pid, sig):
            raise ProcessLookupError("no such process")

        monkeypatch.setattr("pxe_boot.shared.dnsmasq.os.kill", fake_kill)
        dnsmasq.stop()  # must not raise
        assert not fake_pid_file.exists()

    def test_garbage_pid_file_is_tolerated(self, fake_pid_file):
        fake_pid_file.write_text("not-a-number")
        dnsmasq.stop()
        assert not fake_pid_file.exists()


class TestRunning:
    def test_no_pid_file_returns_false(self, fake_pid_file):
        assert dnsmasq.running() is False

    def test_live_pid_returns_true(self, fake_pid_file, monkeypatch):
        fake_pid_file.write_text(str(os.getpid()))
        # The current Python process is definitely alive.
        assert dnsmasq.running() is True

    def test_dead_pid_returns_false(self, fake_pid_file, monkeypatch):
        fake_pid_file.write_text("99999")

        def fake_kill(pid, sig):
            raise ProcessLookupError("no such process")

        monkeypatch.setattr("pxe_boot.shared.dnsmasq.os.kill", fake_kill)
        assert dnsmasq.running() is False
