import shutil
import subprocess
from pathlib import Path

from pxe_boot.shared.errors import BrewMissing


def _brew() -> str:
    path = shutil.which("brew")
    if path is None:
        raise BrewMissing(
            "Homebrew not found; install from https://brew.sh and re-run"
        )
    return path


def prefix() -> Path:
    out = subprocess.run(
        [_brew(), "--prefix"], check=True, capture_output=True, text=True,
    ).stdout.strip()
    return Path(out)


def installed(formula: str) -> bool:
    res = subprocess.run(
        [_brew(), "list", "--formula", formula],
        capture_output=True, text=True,
    )
    return res.returncode == 0


def install(formula: str) -> None:
    subprocess.run([_brew(), "install", formula], check=True)


def uninstall(formula: str) -> None:
    subprocess.run([_brew(), "uninstall", formula], check=True)


def services_start(formula: str) -> None:
    subprocess.run(
        ["sudo", _brew(), "services", "start", formula], check=True,
    )


def services_stop(formula: str) -> None:
    subprocess.run(
        ["sudo", _brew(), "services", "stop", formula], check=True,
    )


def service_running(formula: str) -> bool:
    res = subprocess.run(
        [_brew(), "services", "list"], capture_output=True, text=True,
    )
    if res.returncode != 0:
        return False
    for line in res.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] == formula:
            return len(parts) > 1 and parts[1] == "started"
    return False
