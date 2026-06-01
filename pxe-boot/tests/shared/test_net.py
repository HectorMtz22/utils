import subprocess

import pytest

from pxe_boot.shared.errors import NoNetwork
from pxe_boot.shared.net import (
    detect_active_iface_and_ip,
    parse_default_iface,
    parse_ifconfig_inet,
)


ROUTE_OUTPUT_INTEL = """\
   route to: default
destination: default
       mask: default
    gateway: 192.168.1.1
  interface: en0
      flags: <UP,GATEWAY,DONE,STATIC,PRCLONING>
"""

ROUTE_OUTPUT_APPLE_SILICON = """\
   route to: default
destination: default
       mask: default
    gateway: 10.0.0.1
  interface: en1
      flags: <UP,GATEWAY,DONE,STATIC,PRCLONING>
"""

IFCONFIG_EN0 = """\
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
\tether ac:de:48:00:11:22
\tinet6 fe80::1c4b:abcd:ef01:2345%en0 prefixlen 64 secured scopeid 0x6
\tinet 192.168.1.42 netmask 0xffffff00 broadcast 192.168.1.255
\tnd6 options=201<PERFORMNUD,DAD>
\tmedia: autoselect
\tstatus: active
"""

IFCONFIG_NO_INET = """\
en9: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
\tether ac:de:48:00:11:22
\tstatus: inactive
"""


class TestParseDefaultIface:
    def test_intel(self):
        assert parse_default_iface(ROUTE_OUTPUT_INTEL) == "en0"

    def test_apple_silicon(self):
        assert parse_default_iface(ROUTE_OUTPUT_APPLE_SILICON) == "en1"

    def test_missing_returns_none(self):
        assert parse_default_iface("destination: default\n") is None


class TestParseIfconfigInet:
    def test_extracts_ipv4(self):
        assert parse_ifconfig_inet(IFCONFIG_EN0) == "192.168.1.42"

    def test_missing_returns_none(self):
        assert parse_ifconfig_inet(IFCONFIG_NO_INET) is None


def _fake_run(plan):
    """Return a fake subprocess.run that returns canned stdout per cmd[0]."""
    calls = []

    def fake(cmd, check=True, capture_output=True, text=True, **kw):
        calls.append(list(cmd))
        key = cmd[0]
        if key not in plan:
            raise AssertionError(f"unexpected subprocess call: {cmd}")
        return subprocess.CompletedProcess(cmd, 0, stdout=plan[key], stderr="")

    return fake, calls


class TestDetectActiveIfaceAndIp:
    def test_without_override_uses_route_then_ifconfig(self, monkeypatch):
        fake, calls = _fake_run({"route": ROUTE_OUTPUT_INTEL, "ifconfig": IFCONFIG_EN0})
        monkeypatch.setattr("pxe_boot.shared.net.subprocess.run", fake)
        iface, ip = detect_active_iface_and_ip()
        assert (iface, ip) == ("en0", "192.168.1.42")
        assert [c[0] for c in calls] == ["route", "ifconfig"]

    def test_with_override_skips_route(self, monkeypatch):
        fake, calls = _fake_run({"ifconfig": IFCONFIG_EN0})
        monkeypatch.setattr("pxe_boot.shared.net.subprocess.run", fake)
        iface, ip = detect_active_iface_and_ip(iface_override="en0")
        assert (iface, ip) == ("en0", "192.168.1.42")
        assert [c[0] for c in calls] == ["ifconfig"]
        assert calls[0] == ["ifconfig", "en0"]

    def test_override_uses_requested_iface_even_if_route_says_otherwise(self, monkeypatch):
        fake, calls = _fake_run({"ifconfig": IFCONFIG_EN0})
        monkeypatch.setattr("pxe_boot.shared.net.subprocess.run", fake)
        iface, _ip = detect_active_iface_and_ip(iface_override="en0")
        assert iface == "en0"
        assert "route" not in [c[0] for c in calls]

    def test_override_with_no_ipv4_raises(self, monkeypatch):
        fake, _ = _fake_run({"ifconfig": IFCONFIG_NO_INET})
        monkeypatch.setattr("pxe_boot.shared.net.subprocess.run", fake)
        with pytest.raises(NoNetwork):
            detect_active_iface_and_ip(iface_override="en9")
