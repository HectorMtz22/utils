import subprocess

from pxe_boot.shared import dnsmasq, http_server, state, tftp


def run() -> None:
    s = state.load()
    if s is None:
        print("pxe-boot: nothing to clean up (no active state).")
        return

    try:
        dnsmasq.stop()
    except subprocess.CalledProcessError:
        pass
    tftp.disable()
    if s.http_pid is not None:
        http_server.stop(s.http_pid)

    # Drop the state file so the next --netboot/--iso run starts fresh.
    # Files (kpxe/efi binaries, dnsmasq.d/pxe-boot.conf) stay in place;
    # only --uninstall removes them.
    state.clear()

    print("pxe-boot: services stopped, state cleared. Re-run `pxe-boot --netboot` or `--iso` to start again.")
    print("pxe-boot: run `pxe-boot --uninstall` to remove everything permanently.")
