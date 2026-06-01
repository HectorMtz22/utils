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


class TestStart:
    def test_spawns_dnsmasq_with_conf_and_pid_file(self, fake_prefix, fake_pid_file, monkeypatch):
        seen: list[list[str]] = []

        def fake(cmd, **kw):
            seen.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr("pxe_boot.shared.dnsmasq.subprocess.run", fake)
        dnsmasq.start()
        assert seen[0][0] == "/opt/homebrew/sbin/dnsmasq"
        assert f"--conf-file=/opt/homebrew/etc/dnsmasq.d/pxe-boot.conf" in seen[0]
        assert f"--pid-file={fake_pid_file}" in seen[0]

    def test_clears_stale_pid_file_before_spawning(self, fake_prefix, fake_pid_file, monkeypatch):
        fake_pid_file.write_text("99999")

        def fake(cmd, **kw):
            # By the time dnsmasq actually runs, the stale PID file should be gone.
            assert not fake_pid_file.exists()
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr("pxe_boot.shared.dnsmasq.subprocess.run", fake)
        dnsmasq.start()


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
