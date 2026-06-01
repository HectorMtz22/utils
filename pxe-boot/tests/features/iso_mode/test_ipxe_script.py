from pxe_boot.features.iso_mode.ipxe_script import render_generic, render_ubuntu


class TestRenderUbuntu:
    def test_starts_with_shebang(self):
        s = render_ubuntu(
            ip="192.168.1.42", port=8080,
            iso_name="ubuntu-24.04.iso", iso_stem="ubuntu-24.04",
            kernel_rel="casper/vmlinuz", initrd_rel="casper/initrd",
        )
        assert s.startswith("#!ipxe\n")

    def test_kernel_tftp_url(self):
        s = render_ubuntu(
            ip="192.168.1.42", port=8080,
            iso_name="ubuntu-24.04.iso", iso_stem="ubuntu-24.04",
            kernel_rel="casper/vmlinuz", initrd_rel="casper/initrd",
        )
        assert "tftp://192.168.1.42/pxe-boot/ubuntu-24.04/casper/vmlinuz" in s

    def test_initrd_tftp_url(self):
        s = render_ubuntu(
            ip="192.168.1.42", port=8080,
            iso_name="ubuntu-24.04.iso", iso_stem="ubuntu-24.04",
            kernel_rel="casper/vmlinuz", initrd_rel="casper/initrd",
        )
        assert "tftp://192.168.1.42/pxe-boot/ubuntu-24.04/casper/initrd" in s

    def test_iso_url_present(self):
        s = render_ubuntu(
            ip="192.168.1.42", port=8080,
            iso_name="ubuntu-24.04.iso", iso_stem="ubuntu-24.04",
            kernel_rel="casper/vmlinuz", initrd_rel="casper/initrd",
        )
        assert "url=http://192.168.1.42:8080/ubuntu-24.04.iso" in s

    def test_ends_with_boot(self):
        s = render_ubuntu(
            ip="192.168.1.42", port=8080,
            iso_name="ubuntu-24.04.iso", iso_stem="ubuntu-24.04",
            kernel_rel="casper/vmlinuz", initrd_rel="casper/initrd",
        )
        assert s.rstrip().endswith("boot")


class TestRenderGeneric:
    def test_starts_with_shebang(self):
        s = render_generic(
            ip="10.0.0.1",
            iso_stem="distro",
            kernel_rel="boot/vmlinuz",
            initrd_rel="boot/initrd",
        )
        assert s.startswith("#!ipxe\n")

    def test_no_iso_url(self):
        s = render_generic(
            ip="10.0.0.1",
            iso_stem="distro",
            kernel_rel="boot/vmlinuz",
            initrd_rel="boot/initrd",
        )
        assert "url=" not in s
        assert "http://" not in s

    def test_kernel_and_initrd_lines(self):
        s = render_generic(
            ip="10.0.0.1",
            iso_stem="distro",
            kernel_rel="boot/vmlinuz",
            initrd_rel="boot/initrd",
        )
        assert "kernel tftp://10.0.0.1/pxe-boot/distro/boot/vmlinuz" in s
        assert "initrd tftp://10.0.0.1/pxe-boot/distro/boot/initrd" in s
