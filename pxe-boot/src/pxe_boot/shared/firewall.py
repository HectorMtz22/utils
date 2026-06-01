import subprocess

SOCKETFILTERFW = "/usr/libexec/ApplicationFirewall/socketfilterfw"


def is_application_firewall_enabled() -> bool:
    res = subprocess.run(
        [SOCKETFILTERFW, "--getglobalstate"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        return False
    return "enabled" in res.stdout.lower()
