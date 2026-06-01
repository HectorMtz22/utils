import subprocess

import pytest

from pxe_boot.shared import tftp
from pxe_boot.shared.paths import TFTP_PLIST


@pytest.fixture
def capture_run(monkeypatch):
    seen: list[list[str]] = []

    def fake(cmd, **kw):
        seen.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("pxe_boot.shared.tftp.subprocess.run", fake)
    return seen


class TestIsEnabled:
    def test_uses_print_system_target(self, monkeypatch):
        seen: list[list[str]] = []

        def fake(cmd, **kw):
            seen.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout="...", stderr="")

        monkeypatch.setattr("pxe_boot.shared.tftp.subprocess.run", fake)
        assert tftp.is_enabled() is True
        assert seen[0] == ["sudo", "launchctl", "print", "system/com.apple.tftpd"]

    def test_non_zero_exit_means_not_enabled(self, monkeypatch):
        def fake(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not found")

        monkeypatch.setattr("pxe_boot.shared.tftp.subprocess.run", fake)
        assert tftp.is_enabled() is False


class TestEnable:
    def test_uses_bootstrap_system(self, capture_run):
        tftp.enable()
        assert capture_run[0] == [
            "sudo", "launchctl", "bootstrap", "system", str(TFTP_PLIST),
        ]

    def test_persist_kwarg_accepted(self, capture_run):
        tftp.enable(persist=True)
        # bootstrap is always persistent; we just accept the kwarg for API parity.
        assert capture_run[0] == [
            "sudo", "launchctl", "bootstrap", "system", str(TFTP_PLIST),
        ]


class TestDisable:
    def test_uses_bootout_system(self, capture_run):
        tftp.disable()
        assert capture_run[0] == [
            "sudo", "launchctl", "bootout", "system", str(TFTP_PLIST),
        ]
