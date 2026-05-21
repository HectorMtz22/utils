#!/usr/bin/env bash
# Print a QR code of the given text/URL to the macOS default printer.
set -euo pipefail

usage() {
    echo "Usage: print-qr.sh <text-or-url>" >&2
}

if [ "$#" -ne 1 ] || [ -z "$1" ]; then
    usage
    exit 2
fi

if ! command -v qrencode >/dev/null 2>&1; then
    echo "Error: qrencode not found. Install with: brew install qrencode" >&2
    exit 1
fi

if ! command -v lp >/dev/null 2>&1; then
    echo "Error: lp (CUPS) not found" >&2
    exit 1
fi

tmp_dir="$(mktemp -d -t print-qr)"
trap 'rm -rf -- "$tmp_dir"' EXIT INT TERM HUP
tmp="$tmp_dir/qr.png"

qrencode -s 8 -m 2 -o "$tmp" -- "$1"
lp -o fit-to-page -- "$tmp"
