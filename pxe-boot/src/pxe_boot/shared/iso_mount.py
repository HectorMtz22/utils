import plistlib
import subprocess
from pathlib import Path

from pxe_boot.shared.errors import IsoInvalid, IsoNotFound


def attach(iso_path: Path) -> Path:
    if not iso_path.is_file():
        raise IsoNotFound(f"{iso_path} not found")
    try:
        out = subprocess.run(
            ["hdiutil", "attach", "-nobrowse", "-readonly", "-plist", str(iso_path)],
            check=True, capture_output=True,
        ).stdout
    except subprocess.CalledProcessError as e:
        raise IsoInvalid(f"hdiutil attach failed: {e.stderr.decode(errors='replace')}") from e
    info = plistlib.loads(out)
    for entity in info.get("system-entities", []):
        mp = entity.get("mount-point")
        if mp:
            return Path(mp)
    raise IsoInvalid("hdiutil attach produced no mount-point")


def detach(mountpoint: Path) -> None:
    subprocess.run(
        ["hdiutil", "detach", str(mountpoint)],
        check=False,
    )
