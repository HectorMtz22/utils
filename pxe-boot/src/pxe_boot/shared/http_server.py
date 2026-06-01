import os
import socket
import subprocess
from pathlib import Path

from pxe_boot.shared.errors import PortInUse
from pxe_boot.shared.paths import HTTP_PORT_END, HTTP_PORT_START


def find_free_port(start: int = HTTP_PORT_START, end: int = HTTP_PORT_END) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
            except OSError:
                continue
            return port
    raise PortInUse(start)


def start(*, directory: Path, port: int) -> int:
    """Spawn python3 -m http.server, detached. Returns child PID."""
    proc = subprocess.Popen(
        ["python3", "-m", "http.server", str(port), "--directory", str(directory)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return proc.pid


def is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop(pid: int) -> None:
    try:
        os.kill(pid, 15)  # SIGTERM
    except ProcessLookupError:
        pass
