import pytest

from pxe_boot.shared import errors


class TestExitCodes:
    def test_needs_root_exit_code_77(self):
        with pytest.raises(errors.NeedsRoot) as exc:
            raise errors.NeedsRoot("re-run with sudo")
        assert exc.value.exit_code == 77

    def test_brew_missing_exit_code_1(self):
        assert errors.BrewMissing.exit_code == 1

    def test_no_network_exit_code_1(self):
        assert errors.NoNetwork.exit_code == 1

    def test_port_in_use_carries_port(self):
        err = errors.PortInUse(67)
        assert err.exit_code == 1
        assert err.port == 67
        assert "67" in str(err)

    def test_iso_not_found_exit_code_1(self):
        assert errors.IsoNotFound.exit_code == 1

    def test_iso_invalid_exit_code_1(self):
        assert errors.IsoInvalid.exit_code == 1

    def test_boot_files_not_found_exit_code_1(self):
        assert errors.BootFilesNotFound.exit_code == 1

    def test_already_running_exit_code_1(self):
        assert errors.AlreadyRunning.exit_code == 1
