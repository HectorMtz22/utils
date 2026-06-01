from pathlib import Path

STATE_DIR = Path("/var/db/pxe-boot")
STATE_FILE = STATE_DIR / "state.json"
DNSMASQ_PID_FILE = STATE_DIR / "dnsmasq.pid"
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
# UEFI uses snponly.efi (rides the firmware's already-loaded SNP NIC driver),
# not ipxe.efi (whose built-in drivers don't cover every NIC).
UNDIONLY_KPXE_FILE = TFTP_ROOT / "undionly.kpxe"
UNDIONLY_KPXE_URL = "https://boot.ipxe.org/undionly.kpxe"
SNPONLY_EFI_FILE = TFTP_ROOT / "snponly.efi"
SNPONLY_EFI_URL = "https://boot.ipxe.org/x86_64-efi/snponly.efi"

# Backward-compatible aliases.
IPXE_EFI_FILE = SNPONLY_EFI_FILE
IPXE_EFI_URL = SNPONLY_EFI_URL

# Backward-compatible aliases (old code/tests reference these names).
NETBOOT_XYZ_FILE = NETBOOT_XYZ_FILE_BIOS
NETBOOT_XYZ_URL = NETBOOT_XYZ_URL_BIOS
