#!/usr/bin/env bash
# Print a QR code of the given text/URL to an 80mm ESC/POS thermal printer.
#
# The job is sent as raw bytes (-o raw) so the installed CUPS driver is
# bypassed; we drive the printer directly with ESC/POS, using its native
# QR command (GS ( k) for a single centered QR, then a full paper cut.
set -euo pipefail

usage() {
    echo "Usage: print-qr.sh <text-or-url> [description]" >&2
}

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ] || [ -z "$1" ]; then
    usage
    exit 2
fi

description="${2:-}"

if ! command -v lp >/dev/null 2>&1; then
    echo "Error: lp (CUPS) not found" >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 not found" >&2
    exit 1
fi

printer="${PRINTER:-$(lpstat -d | sed -nE 's/^system default destination: //p')}"
if [ -z "$printer" ]; then
    echo "Error: no default printer set (use PRINTER=<name> to override)" >&2
    exit 1
fi

python3 - "$1" "$description" <<'PY' | lp -d "$printer" -o raw -t print-qr >/dev/null
import sys

data = sys.argv[1].encode("utf-8")
description = sys.argv[2]

ESC = b"\x1b"
GS = b"\x1d"

# Module size at 203 DPI: 8 dots ≈ 1mm per QR module — a ~30-module URL
# QR (+ quiet zone) lands around 40mm wide, comfortably centered on 80mm.
MODULE_SIZE = 8
EC_LEVEL = 49  # 48=L, 49=M, 50=Q, 51=H

out = bytearray()
out += ESC + b"@"                                   # initialize
out += ESC + b"a\x01"                               # center alignment

if description:
    out += GS + b"!\x11"                            # double-width + double-height
    out += ESC + b"E\x01"                           # bold on
    out += description.encode("utf-8") + b"\n"
    out += ESC + b"E\x00"                           # bold off
    out += GS + b"!\x00"                            # reset character size
    out += b"\n"                                    # gap before the QR

out += GS + b"(k\x04\x001A2\x00"                    # QR: select model 2
out += GS + b"(k\x03\x001C" + bytes([MODULE_SIZE])  # QR: module size
out += GS + b"(k\x03\x001E" + bytes([EC_LEVEL])     # QR: error correction
n = len(data) + 3
out += GS + b"(k" + bytes([n & 0xff, n >> 8]) + b"1P0" + data  # store data
out += GS + b"(k\x03\x001Q0"                        # print stored QR
out += b"\n\n\n"                                    # feed past the cutter
out += GS + b"V\x00"                                # full cut

sys.stdout.buffer.write(bytes(out))
PY
