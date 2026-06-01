from pathlib import Path

STATE_DIR = Path("/var/db/pxe-boot")
STATE_FILE = STATE_DIR / "state.json"
TFTP_ROOT = Path("/private/tftpboot")
TFTP_PXE_SUBDIR = TFTP_ROOT / "pxe-boot"
NETBOOT_XYZ_FILE = TFTP_ROOT / "netboot.xyz.kpxe"
NETBOOT_XYZ_URL = "https://boot.netboot.xyz/ipxe/netboot.xyz.kpxe"
HTTP_SERVED_DIR = STATE_DIR / "http"
TFTPBOOT_BACKUP = STATE_DIR / "tftpboot.backup.tar"
TFTP_PLIST = Path("/System/Library/LaunchDaemons/tftp.plist")
HTTP_PORT_START = 8080
HTTP_PORT_END = 8090
