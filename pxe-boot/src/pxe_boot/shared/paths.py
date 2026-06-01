from pathlib import Path

STATE_DIR = Path("/var/db/pxe-boot")
STATE_FILE = STATE_DIR / "state.json"
TFTP_ROOT = Path("/private/tftpboot")
TFTP_PXE_SUBDIR = TFTP_ROOT / "pxe-boot"
HTTP_SERVED_DIR = STATE_DIR / "http"
TFTPBOOT_BACKUP = STATE_DIR / "tftpboot.backup.tar"
TFTP_PLIST = Path("/System/Library/LaunchDaemons/tftp.plist")
HTTP_PORT_START = 8080
HTTP_PORT_END = 8090

# Mode 1 — netboot.xyz prebuilt iPXE binaries.
NETBOOT_XYZ_FILE_BIOS = TFTP_ROOT / "netboot.xyz.kpxe"
NETBOOT_XYZ_URL_BIOS = "https://boot.netboot.xyz/ipxe/netboot.xyz.kpxe"
NETBOOT_XYZ_FILE_EFI = TFTP_ROOT / "netboot.xyz.efi"
NETBOOT_XYZ_URL_EFI = "https://boot.netboot.xyz/ipxe/netboot.xyz.efi"

# Mode 2 — generic iPXE chainloaders (we run our own script).
UNDIONLY_KPXE_FILE = TFTP_ROOT / "undionly.kpxe"
UNDIONLY_KPXE_URL = "https://boot.ipxe.org/undionly.kpxe"
IPXE_EFI_FILE = TFTP_ROOT / "ipxe.efi"
IPXE_EFI_URL = "https://boot.ipxe.org/x86_64-efi/ipxe.efi"

# Backward-compatible aliases (old code/tests reference these names).
NETBOOT_XYZ_FILE = NETBOOT_XYZ_FILE_BIOS
NETBOOT_XYZ_URL = NETBOOT_XYZ_URL_BIOS
