import pytest

from pxe_boot.shared.errors import BootFilesNotFound
from pxe_boot.shared.iso_inspect import find_boot_files


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"")


class TestFindBootFiles:
    def test_ubuntu_casper_layout(self, tmp_path):
        _touch(tmp_path / "casper" / "vmlinuz")
        _touch(tmp_path / "casper" / "initrd")
        bf = find_boot_files(tmp_path)
        assert bf.kernel_rel == "casper/vmlinuz"
        assert bf.initrd_rel == "casper/initrd"
        assert bf.distro_hint == "ubuntu"

    def test_isolinux_fallback(self, tmp_path):
        _touch(tmp_path / "isolinux" / "vmlinuz")
        _touch(tmp_path / "isolinux" / "initrd.img")
        bf = find_boot_files(tmp_path)
        assert bf.kernel_rel == "isolinux/vmlinuz"
        assert bf.initrd_rel == "isolinux/initrd.img"
        assert bf.distro_hint == "generic"

    def test_empty_mount_raises(self, tmp_path):
        with pytest.raises(BootFilesNotFound):
            find_boot_files(tmp_path)

    def test_prefers_casper_over_isolinux(self, tmp_path):
        _touch(tmp_path / "casper" / "vmlinuz")
        _touch(tmp_path / "casper" / "initrd")
        _touch(tmp_path / "isolinux" / "vmlinuz")
        bf = find_boot_files(tmp_path)
        assert bf.distro_hint == "ubuntu"
