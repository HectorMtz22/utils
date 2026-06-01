# pxe-boot

macOS CLI to PXE-boot a PC on the LAN — into either the netboot.xyz menu or a
local ISO of your choice — without a USB drive.

## What it does

- Runs a TFTP server (macOS built-in `tftpd`) for boot files.
- Runs `dnsmasq` from Homebrew in **proxy-DHCP** mode, so your home router
  keeps issuing leases and only PXE traffic is intercepted.
- For local ISOs, runs a small HTTP server for the ISO body.

## Requirements

- macOS (tested on Sonoma+).
- [Homebrew](https://brew.sh).
- A PC on the same LAN with PXE enabled in its BIOS.
- `sudo` (required for TFTP and port 67/UDP).

## Install

```bash
cd pxe-boot
uv sync
```

Then run via `uv run pxe-boot …` or install the entrypoint with:

```bash
uv tool install .
```

## Usage

```bash
sudo pxe-boot                # interactive mode select
sudo pxe-boot --netboot      # netboot.xyz
sudo pxe-boot --iso PATH     # direct ISO (Ubuntu Server first-class)
sudo pxe-boot --cleanup      # stop services, keep installed
sudo pxe-boot --uninstall    # remove everything pxe-boot set up
     pxe-boot --status       # (no sudo) show current state
```

Add `--iface IFACE` (e.g. `--iface en0`) to either mode to force a specific
network interface instead of the default-route autodetect. Useful when the
default route goes over Wi-Fi but PXE has to happen on Ethernet.

### Mode 1 — netboot.xyz

Downloads `netboot.xyz.kpxe` into `/private/tftpboot/` and tells the PC to
chain into it. On boot, the PC will show the netboot.xyz menu and pull
the installer for whatever distro you pick.

### Mode 2 — Direct ISO

Pass a `.iso`. pxe-boot will:

1. Mount the ISO with `hdiutil`.
2. Find the kernel + initrd (Ubuntu's `casper/` layout is first-class;
   `isolinux/` and `boot/` are best-effort fallbacks).
3. Copy them into `/private/tftpboot/pxe-boot/<iso-stem>/`.
4. Serve the ISO itself over HTTP from `/var/db/pxe-boot/http/`.
5. Write an iPXE script that boots the kernel with `url=` pointing
   at the HTTP-served copy.

### `--cleanup` vs `--uninstall`

| Flag           | Stops dnsmasq | Stops TFTP | Stops HTTP | Removes brew dnsmasq | Removes files | Removes state |
|----------------|:-:|:-:|:-:|:-:|:-:|:-:|
| `--cleanup`    | ✓ | ✓ | ✓ |   |   |   |
| `--uninstall`  | ✓ | ✓ | ✓ | ✓ (only if pxe-boot installed it) | ✓ | ✓ |

`--cleanup` leaves everything in place so the next `--netboot` or `--iso`
runs cheaply. `--uninstall` returns the Mac to its pre-`pxe-boot` state.

## Firewall

If the macOS Application Firewall is on, allow inbound traffic for:

- 67/UDP (DHCP proxy)
- 69/UDP (TFTP)
- 8080/TCP (or whichever HTTP port `pxe-boot` picked — see `--status`)

## Architecture

```
src/pxe_boot/
  cli.py                          # argparse + dispatch
  features/<feature>/             # netboot_mode, iso_mode, cleanup, uninstall, status
    service.py                    # orchestration
    command.py                    # CLI adapter
  shared/
    net.py                        # parse default iface + IPv4
    tftp.py                       # launchctl wrapper
    brew.py                       # brew wrapper
    dnsmasq.py + dnsmasq_conf.py  # drop-in conf + service mgmt
    http_server.py                # background HTTP server
    iso_mount.py + iso_inspect.py # hdiutil wrapper + boot-file finder
    state.py + paths.py           # /var/db/pxe-boot/state.json + path constants
    firewall.py                   # Application Firewall check
    privileges.py                 # require_root()
    prompts.py                    # interactive mode select
    errors.py                     # typed exceptions
```

## Tests

```bash
cd pxe-boot && uv run pytest
```

Unit tests cover the pure modules (config rendering, ISO inspection, state
IO, network parsing). Side-effecting wrappers (`brew`, `launchctl`,
`hdiutil`, HTTP spawn) are exercised end-to-end by running the tool on a
real Mac.
