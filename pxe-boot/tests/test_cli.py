import sys

import pytest

from pxe_boot import cli


def test_help_exits_zero(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pxe-boot", "--help"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--netboot" in out
    assert "--iso" in out
    assert "--cleanup" in out
    assert "--uninstall" in out
    assert "--status" in out
    assert "--iface" in out


def test_iface_flag_forwards_to_netboot(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pxe-boot", "--netboot", "--iface", "en0"])
    seen = []
    monkeypatch.setattr(
        "pxe_boot.features.netboot_mode.command.run",
        lambda args: seen.append(args.iface),
    )
    cli.main()
    assert seen == ["en0"]


def test_iface_flag_forwards_to_iso(monkeypatch, tmp_path):
    iso = tmp_path / "x.iso"
    iso.write_bytes(b"")
    monkeypatch.setattr(sys, "argv", ["pxe-boot", "--iso", str(iso), "--iface", "en0"])
    seen = []
    monkeypatch.setattr(
        "pxe_boot.features.iso_mode.command.run",
        lambda args: seen.append((args.iso, args.iface)),
    )
    cli.main()
    assert seen == [(str(iso), "en0")]


def test_iface_defaults_to_none(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pxe-boot", "--netboot"])
    seen = []
    monkeypatch.setattr(
        "pxe_boot.features.netboot_mode.command.run",
        lambda args: seen.append(args.iface),
    )
    cli.main()
    assert seen == [None]


def test_no_args_calls_interactive(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pxe-boot"])
    called = []
    monkeypatch.setattr(
        "pxe_boot.shared.prompts.select_mode", lambda: "netboot",
    )
    monkeypatch.setattr(
        "pxe_boot.features.netboot_mode.command.run",
        lambda args: called.append("netboot"),
    )
    cli.main()
    assert called == ["netboot"]


def test_netboot_flag_dispatches(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pxe-boot", "--netboot"])
    called = []
    monkeypatch.setattr(
        "pxe_boot.features.netboot_mode.command.run",
        lambda args: called.append("netboot"),
    )
    cli.main()
    assert called == ["netboot"]


def test_iso_flag_dispatches_with_path(monkeypatch, tmp_path):
    iso = tmp_path / "x.iso"
    iso.write_bytes(b"")
    monkeypatch.setattr(sys, "argv", ["pxe-boot", "--iso", str(iso)])
    seen = []
    monkeypatch.setattr(
        "pxe_boot.features.iso_mode.command.run",
        lambda args: seen.append(args.iso),
    )
    cli.main()
    assert seen == [str(iso)]


def test_cleanup_flag_dispatches(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pxe-boot", "--cleanup"])
    called = []
    monkeypatch.setattr(
        "pxe_boot.features.cleanup.command.run",
        lambda args: called.append("cleanup"),
    )
    cli.main()
    assert called == ["cleanup"]


def test_uninstall_flag_dispatches(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pxe-boot", "--uninstall"])
    called = []
    monkeypatch.setattr(
        "pxe_boot.features.uninstall.command.run",
        lambda args: called.append("uninstall"),
    )
    cli.main()
    assert called == ["uninstall"]


def test_status_flag_dispatches(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pxe-boot", "--status"])
    called = []
    monkeypatch.setattr(
        "pxe_boot.features.status.command.run",
        lambda args: called.append("status"),
    )
    cli.main()
    assert called == ["status"]


def test_mutually_exclusive_flags_error(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["pxe-boot", "--netboot", "--cleanup"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2


def test_typed_error_uses_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["pxe-boot", "--netboot"])
    from pxe_boot.shared.errors import NeedsRoot
    def boom(args):
        raise NeedsRoot("nope")
    monkeypatch.setattr("pxe_boot.features.netboot_mode.command.run", boom)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 77
    err = capsys.readouterr().err
    assert "nope" in err
