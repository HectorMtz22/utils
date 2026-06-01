def render_ubuntu(
    *,
    ip: str,
    port: int,
    iso_name: str,
    iso_stem: str,
    kernel_rel: str,
    initrd_rel: str,
) -> str:
    return (
        "#!ipxe\n"
        f"kernel tftp://{ip}/pxe-boot/{iso_stem}/{kernel_rel}"
        f" initrd=initrd ip=dhcp url=http://{ip}:{port}/{iso_name}"
        " boot=casper only-ubiquity ---\n"
        f"initrd tftp://{ip}/pxe-boot/{iso_stem}/{initrd_rel}\n"
        "boot\n"
    )


def render_generic(
    *,
    ip: str,
    iso_stem: str,
    kernel_rel: str,
    initrd_rel: str,
) -> str:
    return (
        "#!ipxe\n"
        f"kernel tftp://{ip}/pxe-boot/{iso_stem}/{kernel_rel} ip=dhcp\n"
        f"initrd tftp://{ip}/pxe-boot/{iso_stem}/{initrd_rel}\n"
        "boot\n"
    )
