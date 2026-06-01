import subprocess

import pytest

from pxe_boot.shared import brew


@pytest.fixture
def fake_brew(monkeypatch):
    monkeypatch.setattr("pxe_boot.shared.brew._brew", lambda: "/opt/homebrew/bin/brew")


@pytest.fixture
def capture_run(monkeypatch):
    seen: list[list[str]] = []

    def fake(cmd, **kw):
        seen.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("pxe_boot.shared.brew.subprocess.run", fake)
    return seen


class TestAsInvokingUserPrefix:
    def test_root_with_sudo_user_returns_prefix(self, monkeypatch):
        monkeypatch.setattr("pxe_boot.shared.brew.os.geteuid", lambda: 0)
        monkeypatch.setenv("SUDO_USER", "kilo")
        assert brew._as_invoking_user_prefix() == ["sudo", "-u", "kilo"]

    def test_root_without_sudo_user_returns_empty(self, monkeypatch):
        monkeypatch.setattr("pxe_boot.shared.brew.os.geteuid", lambda: 0)
        monkeypatch.delenv("SUDO_USER", raising=False)
        assert brew._as_invoking_user_prefix() == []

    def test_non_root_returns_empty(self, monkeypatch):
        monkeypatch.setattr("pxe_boot.shared.brew.os.geteuid", lambda: 501)
        monkeypatch.setenv("SUDO_USER", "kilo")
        assert brew._as_invoking_user_prefix() == []

    def test_root_with_sudo_user_root_returns_empty(self, monkeypatch):
        monkeypatch.setattr("pxe_boot.shared.brew.os.geteuid", lambda: 0)
        monkeypatch.setenv("SUDO_USER", "root")
        assert brew._as_invoking_user_prefix() == []


class TestInstall:
    def test_drops_root_via_sudo_user(self, fake_brew, capture_run, monkeypatch):
        monkeypatch.setattr("pxe_boot.shared.brew.os.geteuid", lambda: 0)
        monkeypatch.setenv("SUDO_USER", "kilo")
        brew.install("dnsmasq")
        assert capture_run[0] == [
            "sudo", "-u", "kilo", "/opt/homebrew/bin/brew", "install", "dnsmasq",
        ]

    def test_no_prefix_when_already_user(self, fake_brew, capture_run, monkeypatch):
        monkeypatch.setattr("pxe_boot.shared.brew.os.geteuid", lambda: 501)
        brew.install("dnsmasq")
        assert capture_run[0] == ["/opt/homebrew/bin/brew", "install", "dnsmasq"]


class TestUninstall:
    def test_drops_root_via_sudo_user(self, fake_brew, capture_run, monkeypatch):
        monkeypatch.setattr("pxe_boot.shared.brew.os.geteuid", lambda: 0)
        monkeypatch.setenv("SUDO_USER", "kilo")
        brew.uninstall("dnsmasq")
        assert capture_run[0] == [
            "sudo", "-u", "kilo", "/opt/homebrew/bin/brew", "uninstall", "dnsmasq",
        ]
