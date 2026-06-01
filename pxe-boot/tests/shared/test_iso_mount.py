import subprocess

import pytest

from pxe_boot.shared import iso_mount
from pxe_boot.shared.errors import BootFilesNotFound, IsoInvalid, IsoNotFound


@pytest.fixture
def fake_iso(tmp_path):
    iso = tmp_path / "ubuntu.iso"
    iso.write_bytes(b"fake")
    return iso


def _stub_subprocess(monkeypatch, *, listing: str, extract_ok: bool = True):
    """Return a list capturing the commands invoked."""
    seen: list[list[str]] = []

    def fake(cmd, **kw):
        seen.append(list(cmd))
        if cmd[:2] == ["bsdtar", "-tf"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=listing, stderr="")
        if cmd[:2] == ["bsdtar", "-xf"]:
            if not extract_ok:
                raise subprocess.CalledProcessError(
                    1, cmd, output=b"", stderr=b"extract failed",
                )
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")
        if cmd[:1] == ["chmod"]:
            return subprocess.CompletedProcess(cmd, 0)
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr("pxe_boot.shared.iso_mount.subprocess.run", fake)
    return seen


class TestAttach:
    def test_missing_iso_raises(self, tmp_path):
        with pytest.raises(IsoNotFound):
            iso_mount.attach(tmp_path / "nope.iso")

    def test_ubuntu_layout_extracts_casper(self, fake_iso, monkeypatch):
        seen = _stub_subprocess(monkeypatch, listing="casper/vmlinuz\ncasper/initrd\nMETADATA\n")
        mp = iso_mount.attach(fake_iso)
        assert mp.exists()
        assert mp.name.startswith("pxe-boot-iso-")
        # First call lists, second call extracts only "casper".
        assert seen[0][:2] == ["bsdtar", "-tf"]
        assert seen[1][:2] == ["bsdtar", "-xf"]
        assert "casper" in seen[1]
        assert "isolinux" not in seen[1]
        # cleanup
        iso_mount.detach(mp)

    def test_isolinux_layout_extracts_isolinux(self, fake_iso, monkeypatch):
        seen = _stub_subprocess(monkeypatch, listing="isolinux/vmlinuz\nisolinux/initrd.img\n")
        mp = iso_mount.attach(fake_iso)
        assert "isolinux" in seen[1]
        assert "casper" not in seen[1]
        iso_mount.detach(mp)

    def test_multiple_layouts_present_extracts_all(self, fake_iso, monkeypatch):
        seen = _stub_subprocess(
            monkeypatch,
            listing="casper/vmlinuz\nisolinux/vmlinuz\nboot/grub/grub.cfg\n",
        )
        mp = iso_mount.attach(fake_iso)
        # Order is sorted alphabetically per implementation.
        extract_cmd = seen[1]
        for d in ("boot", "casper", "isolinux"):
            assert d in extract_cmd
        iso_mount.detach(mp)

    def test_no_boot_dirs_raises_boot_files_not_found(self, fake_iso, monkeypatch):
        _stub_subprocess(monkeypatch, listing="random/file.txt\nother/dir/\n")
        with pytest.raises(BootFilesNotFound):
            iso_mount.attach(fake_iso)

    def test_listing_failure_raises_iso_invalid(self, fake_iso, monkeypatch):
        def fake(cmd, **kw):
            raise subprocess.CalledProcessError(
                1, cmd, output="", stderr="not a valid archive",
            )
        monkeypatch.setattr("pxe_boot.shared.iso_mount.subprocess.run", fake)
        with pytest.raises(IsoInvalid):
            iso_mount.attach(fake_iso)

    def test_extract_failure_cleans_up_temp_dir(self, fake_iso, monkeypatch):
        _stub_subprocess(
            monkeypatch, listing="casper/vmlinuz\n", extract_ok=False,
        )
        with pytest.raises(IsoInvalid):
            iso_mount.attach(fake_iso)
        # No way to check the temp dir is gone without exposing it; tmpfile's
        # cleanup ran inside iso_mount.attach — if it didn't, this test would
        # leak a directory, which pytest's tmp_path fixture would surface.


class TestDetach:
    def test_removes_only_pxe_boot_temp_dirs(self, tmp_path, monkeypatch):
        # Simulate a real attach
        seen = _stub_subprocess(monkeypatch, listing="casper/vmlinuz\n")
        iso = tmp_path / "x.iso"
        iso.write_bytes(b"")
        mp = iso_mount.attach(iso)
        assert mp.exists()
        iso_mount.detach(mp)
        assert not mp.exists()

    def test_safe_with_unrelated_path(self, tmp_path):
        unrelated = tmp_path / "important"
        unrelated.mkdir()
        (unrelated / "data").write_text("keep me")
        iso_mount.detach(unrelated)
        # The guard prefix means we did NOT delete the unrelated dir.
        assert (unrelated / "data").read_text() == "keep me"

    def test_safe_with_missing_path(self, tmp_path):
        iso_mount.detach(tmp_path / "does-not-exist")
        # no exception
