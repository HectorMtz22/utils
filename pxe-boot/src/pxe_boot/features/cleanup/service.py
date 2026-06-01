from pxe_boot.shared import dnsmasq, http_server, state, tftp


def run() -> None:
    s = state.load()
    if s is None:
        print("pxe-boot: nothing to clean up (no active state).")
        return

    dnsmasq.stop()
    tftp.disable()
    if s.http_pid is not None:
        http_server.stop(s.http_pid)

    print("pxe-boot: services stopped. Re-run `pxe-boot --netboot` or `--iso` to start again.")
    print("pxe-boot: run `pxe-boot --uninstall` to remove everything permanently.")
