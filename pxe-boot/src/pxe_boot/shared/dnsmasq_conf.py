_TEMPLATE = """\
# pxe-boot drop-in
interface={iface}
bind-interfaces
port=0
dhcp-range={ip},proxy
dhcp-boot={boot_file}
pxe-prompt="Network boot",1
pxe-service=x86PC,"Boot from network",{boot_file}
enable-tftp
tftp-root=/private/tftpboot
log-dhcp
"""


_DUAL_ARCH_TEMPLATE = """\
# pxe-boot drop-in (arch-aware: BIOS + UEFI x64)
interface={iface}
bind-interfaces
port=0
dhcp-range={ip},proxy

# Differentiate BIOS PXE (arch 0) from UEFI x64 (arch 7 or 9) via DHCP option 93.
dhcp-match=set:bios,option:client-arch,0
dhcp-match=set:efi64,option:client-arch,7
dhcp-match=set:efi64,option:client-arch,9

dhcp-boot=tag:bios,{bios_boot}
dhcp-boot=tag:efi64,{efi_boot}
pxe-prompt="Network boot",1
pxe-service=x86PC,"BIOS PXE",{bios_boot}
pxe-service=X86-64_EFI,"UEFI PXE",{efi_boot}
enable-tftp
tftp-root=/private/tftpboot
log-dhcp
"""


_CHAINED_TEMPLATE = """\
# pxe-boot drop-in (arch-aware iPXE chainload — Mode 2)
interface={iface}
bind-interfaces
port=0
dhcp-range={ip},proxy

# Architecture detection (BIOS vs UEFI x64).
dhcp-match=set:bios,option:client-arch,0
dhcp-match=set:efi64,option:client-arch,7
dhcp-match=set:efi64,option:client-arch,9

# iPXE identifies itself via DHCP user-class "iPXE".
dhcp-userclass=set:ipxe,iPXE

# Stage 1: raw PXE clients get an iPXE binary for their arch.
dhcp-boot=tag:bios,tag:!ipxe,{bios_chainloader}
dhcp-boot=tag:efi64,tag:!ipxe,{efi_chainloader}

# Stage 2: once iPXE is running, hand it our script.
dhcp-boot=tag:ipxe,{ipxe_script}

pxe-prompt="Network boot",1
pxe-service=x86PC,"BIOS PXE",{bios_chainloader}
pxe-service=X86-64_EFI,"UEFI PXE",{efi_chainloader}
enable-tftp
tftp-root=/private/tftpboot
log-dhcp
"""


def render(*, iface: str, ip: str, boot_file: str) -> str:
    """Single-boot-file config (legacy callers / tests)."""
    return _TEMPLATE.format(iface=iface, ip=ip, boot_file=boot_file)


def render_dual_arch(*, iface: str, ip: str, bios_boot: str, efi_boot: str) -> str:
    """Mode 1: serve different prebuilt binaries by architecture."""
    return _DUAL_ARCH_TEMPLATE.format(
        iface=iface, ip=ip, bios_boot=bios_boot, efi_boot=efi_boot,
    )


def render_chained(
    *,
    iface: str,
    ip: str,
    bios_chainloader: str,
    efi_chainloader: str,
    ipxe_script: str,
) -> str:
    """Mode 2: chain raw-PXE clients into iPXE via arch-appropriate binary,
    then serve our `.ipxe` script once iPXE is talking back."""
    return _CHAINED_TEMPLATE.format(
        iface=iface,
        ip=ip,
        bios_chainloader=bios_chainloader,
        efi_chainloader=efi_chainloader,
        ipxe_script=ipxe_script,
    )
