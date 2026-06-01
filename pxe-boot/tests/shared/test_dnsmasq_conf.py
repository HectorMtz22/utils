from pxe_boot.shared.dnsmasq_conf import render, render_chained, render_dual_arch


class TestRender:
    def test_contains_iface(self):
        text = render(iface="en0", ip="192.168.1.42", boot_file="netboot.xyz.kpxe")
        assert "interface=en0" in text

    def test_contains_proxy_dhcp_range(self):
        text = render(iface="en0", ip="192.168.1.42", boot_file="netboot.xyz.kpxe")
        assert "dhcp-range=192.168.1.42,proxy" in text

    def test_contains_boot_file(self):
        text = render(iface="en0", ip="1.2.3.4", boot_file="pxe-boot/ubuntu/ipxe.script")
        assert "dhcp-boot=pxe-boot/ubuntu/ipxe.script" in text
        assert "pxe-service=x86PC,\"Boot from network\",pxe-boot/ubuntu/ipxe.script" in text

    def test_disables_dns(self):
        text = render(iface="en0", ip="1.2.3.4", boot_file="x")
        assert "port=0" in text

    def test_enables_tftp(self):
        text = render(iface="en0", ip="1.2.3.4", boot_file="x")
        assert "enable-tftp" in text
        assert "tftp-root=/private/tftpboot" in text

    def test_bind_interfaces(self):
        text = render(iface="en0", ip="1.2.3.4", boot_file="x")
        assert "bind-interfaces" in text

    def test_no_placeholder_substring(self):
        text = render(iface="en0", ip="1.2.3.4", boot_file="x")
        assert "{" not in text and "}" not in text


class TestRenderDualArch:
    def test_arch_tags_present(self):
        text = render_dual_arch(
            iface="en0", ip="1.2.3.4",
            bios_boot="netboot.xyz.kpxe", efi_boot="netboot.xyz.efi",
        )
        assert "dhcp-match=set:bios,option:client-arch,0" in text
        assert "dhcp-match=set:efi64,option:client-arch,7" in text
        assert "dhcp-match=set:efi64,option:client-arch,9" in text

    def test_bios_and_efi_dhcp_boot_lines(self):
        text = render_dual_arch(
            iface="en0", ip="1.2.3.4",
            bios_boot="netboot.xyz.kpxe", efi_boot="netboot.xyz.efi",
        )
        assert "dhcp-boot=tag:bios,netboot.xyz.kpxe" in text
        assert "dhcp-boot=tag:efi64,netboot.xyz.efi" in text

    def test_pxe_service_lines_for_both_archs(self):
        text = render_dual_arch(
            iface="en0", ip="1.2.3.4",
            bios_boot="netboot.xyz.kpxe", efi_boot="netboot.xyz.efi",
        )
        assert 'pxe-service=x86PC,"BIOS PXE",netboot.xyz.kpxe' in text
        assert 'pxe-service=X86-64_EFI,"UEFI PXE",netboot.xyz.efi' in text

    def test_no_placeholder_substring(self):
        text = render_dual_arch(
            iface="en0", ip="1.2.3.4",
            bios_boot="a.kpxe", efi_boot="b.efi",
        )
        assert "{" not in text and "}" not in text


class TestRenderChained:
    def test_ipxe_userclass_set(self):
        text = render_chained(
            iface="en0", ip="1.2.3.4",
            bios_chainloader="undionly.kpxe", efi_chainloader="ipxe.efi",
            ipxe_script="pxe-boot/x/ipxe.script",
        )
        assert "dhcp-userclass=set:ipxe,iPXE" in text

    def test_stage1_chainloaders_gated_on_not_ipxe(self):
        text = render_chained(
            iface="en0", ip="1.2.3.4",
            bios_chainloader="undionly.kpxe", efi_chainloader="ipxe.efi",
            ipxe_script="pxe-boot/x/ipxe.script",
        )
        assert "dhcp-boot=tag:bios,tag:!ipxe,undionly.kpxe" in text
        assert "dhcp-boot=tag:efi64,tag:!ipxe,ipxe.efi" in text

    def test_stage2_serves_script_to_ipxe_clients(self):
        text = render_chained(
            iface="en0", ip="1.2.3.4",
            bios_chainloader="undionly.kpxe", efi_chainloader="ipxe.efi",
            ipxe_script="pxe-boot/x/ipxe.script",
        )
        assert "dhcp-boot=tag:ipxe,pxe-boot/x/ipxe.script" in text

    def test_no_placeholder_substring(self):
        text = render_chained(
            iface="en0", ip="1.2.3.4",
            bios_chainloader="a", efi_chainloader="b", ipxe_script="c",
        )
        assert "{" not in text and "}" not in text
