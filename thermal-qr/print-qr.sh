#!/usr/bin/env bash
# Print a QR code of the given text/URL to an 80mm ESC/POS thermal printer.
#
# The job is sent as raw bytes (-o raw) so the installed CUPS driver is
# bypassed; we drive the printer directly with ESC/POS, using its native
# QR command (GS ( k) for a single centered QR, then a full paper cut.
#
# With --save <path>, write a PNG to <path> instead of printing. Save mode
# uses qrencode for the QR (and ImageMagick's `magick` to composite a bold
# caption above it when a description is also given); it does not touch lp.
set -euo pipefail

usage() {
    echo "Usage: print-qr.sh [--save <path>] <text-or-url> [description]" >&2
}

save_path=""
if [ "${1:-}" = "--save" ]; then
    if [ "$#" -lt 2 ]; then
        usage
        exit 2
    fi
    save_path="$2"
    shift 2
fi

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ] || [ -z "$1" ]; then
    usage
    exit 2
fi

description="${2:-}"

if [ -n "$save_path" ]; then
    if [ -d "$save_path" ]; then
        echo "Error: --save path is a directory: $save_path" >&2
        exit 1
    fi

    if ! command -v qrencode >/dev/null 2>&1; then
        echo "Error: qrencode not found (brew install qrencode)" >&2
        exit 1
    fi

    if [ -n "$description" ] && ! command -v magick >/dev/null 2>&1; then
        echo "Error: magick (ImageMagick) not found (brew install imagemagick)" >&2
        exit 1
    fi

    # mktemp -d (not -f) because BSD mktemp doesn't substitute XXXXXX in a
    # `-t PREFIX` template — a `mktemp -t print-qr.XXXXXX` produces a path
    # with a literal `XXXXXX` and a random suffix appended, which makes the
    # ".png" trick leak the actual mktemp file. A private directory + a known
    # filename inside it is portable and atomic.
    qr_dir=""
    trap '[ -n "${qr_dir:-}" ] && rm -rf -- "$qr_dir"' EXIT
    qr_dir="$(mktemp -d -t print-qr)"
    qr_tmp="$qr_dir/qr.png"

    qrencode -s 10 -m 2 -o "$qr_tmp" -- "$1"

    if [ -z "$description" ]; then
        mv -- "$qr_tmp" "$save_path"
    else
        # ImageMagick 7 on macOS ships without a font config, so `magick
        # -list font` is empty and a font *name* like "Helvetica-Bold" can't
        # be resolved. Point -font at an actual bold font file instead; try
        # the usual macOS locations and use the first that exists.
        font=""
        for f in \
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" \
            "/System/Library/Fonts/Supplemental/Helvetica.ttc" \
            "/Library/Fonts/Arial Bold.ttf" \
            "/System/Library/Fonts/Helvetica.ttc"; do
            if [ -f "$f" ]; then
                font="$f"
                break
            fi
        done
        if [ -z "$font" ]; then
            echo "Error: no bold font file found for the caption" >&2
            exit 1
        fi

        # `./`-prefix a leading-dash save_path so magick doesn't parse it as
        # an option (ImageMagick has no universal `--` separator).
        out="$save_path"
        case "$out" in -*) out="./$out";; esac

        # label:@- reads caption text from stdin instead of inline, which
        # disables ImageMagick's `%`-escape substitution (so a caption like
        # "50% off" is rendered literally) and avoids @-prefix-means-file.
        # Caption: bold black on white, ~48pt, centered with horizontal padding,
        # vertically appended above the QR (which is already black-on-white).
        printf '%s' "$description" | magick \
            -background white -fill black -font "$font" \
            -pointsize 48 -gravity center \
            label:@- \
            -bordercolor white -border 40x20 \
            "$qr_tmp" \
            -background white -gravity center -append \
            "$out"
    fi

    exit 0
fi

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
