from pathlib import Path
from typing import Tuple

from pxe_boot.shared import brew, dnsmasq_conf

DROPIN_NAME = "pxe-boot.conf"
CONF_DIR_LINE = "conf-dir=%s/etc/dnsmasq.d/,*.conf"


def dropin_path() -> Path:
    return brew.prefix() / "etc" / "dnsmasq.d" / DROPIN_NAME


def main_conf_path() -> Path:
    return brew.prefix() / "etc" / "dnsmasq.conf"


def ensure_installed() -> bool:
    """Returns True iff we installed it just now."""
    if brew.installed("dnsmasq"):
        return False
    brew.install("dnsmasq")
    return True


def ensure_conf_dir_include() -> bool:
    """Append `conf-dir=...` to main dnsmasq.conf iff missing. Returns True if we edited it."""
    main = main_conf_path()
    include_line = CONF_DIR_LINE % brew.prefix()
    if main.exists():
        text = main.read_text()
        if "conf-dir=" in text:
            return False
    else:
        text = ""
    main.parent.mkdir(parents=True, exist_ok=True)
    if text and not text.endswith("\n"):
        text += "\n"
    main.write_text(text + include_line + "\n")
    return True


def write_dropin(*, iface: str, ip: str, boot_file: str) -> None:
    """Write the single-boot-file dnsmasq config (Mode 1 legacy callers)."""
    write_dropin_text(dnsmasq_conf.render(iface=iface, ip=ip, boot_file=boot_file))


def write_dropin_text(text: str) -> None:
    """Write a pre-rendered drop-in config. Used by callers that need a
    multi-arch or chained config beyond the single-boot-file template."""
    path = dropin_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def remove_dropin() -> None:
    try:
        dropin_path().unlink()
    except FileNotFoundError:
        pass


def revert_conf_dir_include() -> None:
    """Strip the `conf-dir=...` line we appended from main dnsmasq.conf."""
    main = main_conf_path()
    if not main.exists():
        return
    include_line = CONF_DIR_LINE % brew.prefix()
    lines = main.read_text().splitlines(keepends=True)
    kept = [ln for ln in lines if ln.rstrip("\n") != include_line]
    main.write_text("".join(kept))


def start() -> None:
    brew.services_start("dnsmasq")


def stop() -> None:
    brew.services_stop("dnsmasq")


def running() -> bool:
    return brew.service_running("dnsmasq")
