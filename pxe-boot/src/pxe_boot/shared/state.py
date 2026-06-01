import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Optional

from pxe_boot.shared.paths import STATE_FILE


@dataclass
class State:
    mode: Literal["netboot", "iso"]
    iface: str
    ip: str
    dnsmasq_installed_by_us: bool
    dnsmasq_main_conf_edited: bool
    tftp_was_enabled_before: bool
    started_at: str
    tftpboot_backup_path: Optional[str] = None
    http_pid: Optional[int] = None
    served_dir: Optional[str] = None
    iso_name: Optional[str] = None


def load() -> Optional[State]:
    if not STATE_FILE.exists():
        return None
    raw = json.loads(STATE_FILE.read_text())
    return State(**raw)


def save(state: State) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(asdict(state), indent=2, sort_keys=True))


def clear() -> None:
    try:
        STATE_FILE.unlink()
    except FileNotFoundError:
        pass
