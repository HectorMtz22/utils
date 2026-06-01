import re
import subprocess
from typing import Optional

from pxe_boot.shared.errors import NoNetwork


_IFACE_RE = re.compile(r"^\s*interface:\s*(\S+)\s*$", re.MULTILINE)
_INET_RE = re.compile(r"^\s*inet\s+(\d+\.\d+\.\d+\.\d+)\s+netmask", re.MULTILINE)


def parse_default_iface(route_output: str) -> Optional[str]:
    m = _IFACE_RE.search(route_output)
    return m.group(1) if m else None


def parse_ifconfig_inet(ifconfig_output: str) -> Optional[str]:
    m = _INET_RE.search(ifconfig_output)
    return m.group(1) if m else None


def detect_active_iface_and_ip() -> tuple[str, str]:
    """Run `route` + `ifconfig`; raise NoNetwork if either fails."""
    try:
        route_out = subprocess.run(
            ["route", "-n", "get", "default"],
            check=True, capture_output=True, text=True,
        ).stdout
    except subprocess.CalledProcessError as e:
        raise NoNetwork("no default IPv4 route") from e

    iface = parse_default_iface(route_out)
    if iface is None:
        raise NoNetwork("could not parse default interface")

    try:
        ifc_out = subprocess.run(
            ["ifconfig", iface],
            check=True, capture_output=True, text=True,
        ).stdout
    except subprocess.CalledProcessError as e:
        raise NoNetwork(f"could not read ifconfig for {iface}") from e

    ip = parse_ifconfig_inet(ifc_out)
    if ip is None:
        raise NoNetwork(f"no IPv4 address on {iface}")

    return iface, ip
