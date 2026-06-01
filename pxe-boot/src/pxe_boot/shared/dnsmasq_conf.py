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


def render(*, iface: str, ip: str, boot_file: str) -> str:
    return _TEMPLATE.format(iface=iface, ip=ip, boot_file=boot_file)
