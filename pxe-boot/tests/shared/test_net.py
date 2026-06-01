import pytest

from pxe_boot.shared.net import parse_default_iface, parse_ifconfig_inet


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
