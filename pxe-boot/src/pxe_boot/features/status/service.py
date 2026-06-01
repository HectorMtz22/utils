from pxe_boot.shared import dnsmasq, http_server, state, tftp


def run() -> None:
    s = state.load()
    if s is None:
        print("pxe-boot: no active state (not running).")
        return

    print(f"pxe-boot status:")
    print(f"  mode      : {s.mode}")
    print(f"  iface     : {s.iface}")
    print(f"  ip        : {s.ip}")
    if s.iso_name:
        print(f"  iso       : {s.iso_name}")
    if s.http_pid is not None:
        alive = http_server.is_alive(s.http_pid)
        print(f"  http pid  : {s.http_pid} ({'alive' if alive else 'dead'})")
    print(f"  dnsmasq   : {'running' if dnsmasq.running() else 'stopped'}")
    print(f"  tftp      : {'enabled' if tftp.is_enabled() else 'disabled'}")
    print(f"  started   : {s.started_at}")
