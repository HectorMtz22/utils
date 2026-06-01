from pxe_boot.shared.dnsmasq_conf import render


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
