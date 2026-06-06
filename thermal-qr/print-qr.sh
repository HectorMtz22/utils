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
#
# With no arguments, launch an interactive gum TUI (see run_tui).
set -euo pipefail

usage() {
    echo "Usage: print-qr.sh [--save <path>] <text-or-url> [description]" >&2
    echo "       print-qr.sh                 (no args: interactive TUI)" >&2
}

# --- dependency helpers ---------------------------------------------------
require_print_deps() {
    if ! command -v lp >/dev/null 2>&1; then
        echo "Error: lp (CUPS) not found" >&2
        return 1
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        echo "Error: python3 not found" >&2
        return 1
    fi
}

require_qrencode() {
    if ! command -v qrencode >/dev/null 2>&1; then
        echo "Error: qrencode not found (brew install qrencode)" >&2
        return 1
    fi
}

require_magick() {
    if ! command -v magick >/dev/null 2>&1; then
        echo "Error: magick (ImageMagick) not found (brew install imagemagick)" >&2
        return 1
    fi
}

default_printer() {
    lpstat -d 2>/dev/null | sed -nE 's/^system default destination: //p'
}

# --- ESC/POS generation ---------------------------------------------------
# Write the raw ESC/POS byte stream for a (optionally captioned) QR to stdout.
# Args: <text> <description> <module-size:int> <ec-numeric:48-51>
gen_escpos() {
    python3 - "$1" "$2" "$3" "$4" <<'PY'
import sys

data = sys.argv[1].encode("utf-8")
description = sys.argv[2]
MODULE_SIZE = int(sys.argv[3])
EC_LEVEL = int(sys.argv[4])

ESC = b"\x1b"
GS = b"\x1d"

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
}

# --- engine: print --------------------------------------------------------
# Print a QR of <text> (optional caption). With PRINTQR_DRYRUN set, dump the
# byte stream to stdout instead of sending it to lp (used by the tests).
# Args: <text> <description>
do_print() {
    local text="$1" desc="$2"
    local mod=8 ec=49

    if [ -n "${PRINTQR_DRYRUN:-}" ]; then
        if ! command -v python3 >/dev/null 2>&1; then
            echo "Error: python3 not found" >&2
            return 1
        fi
        gen_escpos "$text" "$desc" "$mod" "$ec"
        return
    fi

    require_print_deps || return 1
    local printer="${PRINTER:-$(default_printer)}"
    if [ -z "$printer" ]; then
        echo "Error: no default printer set (use PRINTER=<name> to override)" >&2
        return 1
    fi
    gen_escpos "$text" "$desc" "$mod" "$ec" | lp -d "$printer" -o raw -t print-qr >/dev/null
}

# --- engine: save ---------------------------------------------------------
# Write a PNG of <text> (optional caption) to <path>.
# Args: <path> <text> <description>
do_save() {
    local save_path="$1" text="$2" desc="$3"

    if [ -d "$save_path" ]; then
        echo "Error: --save path is a directory: $save_path" >&2
        return 1
    fi
    require_qrencode || return 1
    if [ -n "$desc" ]; then
        require_magick || return 1
    fi

    # RETURN trap (not EXIT) so cleanup fires when this function returns, and
    # can still see the function-local qr_dir; works whether called from the
    # CLI or the TUI (which keeps running afterwards).
    local qr_dir=""
    trap '[ -n "${qr_dir:-}" ] && rm -rf -- "$qr_dir"' RETURN
    qr_dir="$(mktemp -d -t print-qr)"
    local qr_tmp="$qr_dir/qr.png"

    qrencode -s 10 -m 2 -o "$qr_tmp" -- "$text"

    if [ -z "$desc" ]; then
        mv -- "$qr_tmp" "$save_path"
        return
    fi

    # ImageMagick 7 on macOS ships without a font config, so a font *name*
    # can't be resolved; point -font at an actual bold font file instead.
    local font="" f
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
        return 1
    fi

    # `./`-prefix a leading-dash path so magick doesn't read it as an option.
    local out="$save_path"
    case "$out" in -*) out="./$out";; esac

    # label:@- reads the caption from stdin, disabling %-escape substitution
    # (so "50% off" renders literally) and avoiding @-means-file.
    printf '%s' "$desc" | magick \
        -background white -fill black -font "$font" \
        -pointsize 48 -gravity center \
        label:@- \
        -bordercolor white -border 40x20 \
        "$qr_tmp" \
        -background white -gravity center -append \
        "$out"
}

# --- dispatch -------------------------------------------------------------
main() {
    if [ "$#" -eq 0 ]; then
        usage
        return 2
    fi

    local save_path=""
    if [ "${1:-}" = "--save" ]; then
        if [ "$#" -lt 2 ]; then
            usage
            return 2
        fi
        save_path="$2"
        shift 2
    fi

    if [ "$#" -lt 1 ] || [ "$#" -gt 2 ] || [ -z "$1" ]; then
        usage
        return 2
    fi

    local description="${2:-}"

    if [ -n "$save_path" ]; then
        do_save "$save_path" "$1" "$description"
    else
        do_print "$1" "$description"
    fi
}

# Only run main when executed directly; when sourced (tests) just define funcs.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
