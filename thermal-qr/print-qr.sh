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

# Map a friendly EC level (L/M/Q/H) to its ESC/POS numeric code.
ec_to_escpos() {
    case "$1" in
        L|l) echo 48 ;;
        M|m) echo 49 ;;
        Q|q) echo 50 ;;
        H|h) echo 51 ;;
        *) echo "Error: invalid EC_LEVEL '$1' (use L/M/Q/H)" >&2; return 1 ;;
    esac
}

# --- TUI helpers ----------------------------------------------------------
# Read `lpstat -p` output on stdin, emit one printer name per line.
parse_printers() {
    sed -nE 's/^printer ([^ ]+) .*/\1/p'
}

# Render the pre-flight summary. Args: <mode> <dest> <text> <caption> <module> <ec>
format_summary() {
    local mode="$1" dest="$2" text="$3" caption="$4" mod="$5" ec="$6"
    local label="Printer: "
    if [ "$mode" = "Save PNG" ]; then
        label="Path:    "
    fi
    printf 'Mode:     %s\n' "$mode"
    printf '%s%s\n' "$label" "$dest"
    printf 'Text:     %s\n' "$text"
    printf 'Caption:  %s\n' "${caption:-(none)}"
    printf 'Module:   %s\n' "$mod"
    printf 'EC level: %s\n' "$ec"
}

# Ensure `gum` is available, offering a one-time Homebrew install. Returns
# non-zero (with a message) if gum can't be made available.
ensure_gum() {
    if command -v gum >/dev/null 2>&1; then
        return 0
    fi
    if ! command -v brew >/dev/null 2>&1; then
        echo "Error: gum not found and Homebrew unavailable (see https://github.com/charmbracelet/gum)" >&2
        return 1
    fi
    printf 'gum is required for the menu. Install via Homebrew now? [y/N] '
    local ans
    read -r ans || ans=""
    case "$ans" in
        [Yy]*)
            if ! brew install gum; then
                echo "Error: gum install failed" >&2
                return 1
            fi
            ;;
        *)
            echo "Aborted." >&2
            return 1
            ;;
    esac
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
    local mod ec
    mod="${MODULE_SIZE:-8}"
    ec="$(ec_to_escpos "${EC_LEVEL:-M}")" || return 1

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

    # Clean the temp dir via a RETURN trap. Every fallible step below routes
    # failure through an explicit `return 1` instead of letting `set -e` abort
    # mid-function, so the trap always fires — on success and on error — and
    # works whether called from the CLI or the long-lived TUI. (An EXIT trap
    # would not see the function-local qr_dir after the function returns.)
    local qr_dir=""
    trap '[ -n "${qr_dir:-}" ] && rm -rf -- "$qr_dir"' RETURN
    qr_dir="$(mktemp -d -t print-qr)"
    local qr_tmp="$qr_dir/qr.png"

    if ! qrencode -s "${MODULE_SIZE:-10}" -m 2 -l "${EC_LEVEL:-L}" -o "$qr_tmp" -- "$text"; then
        return 1
    fi

    if [ -z "$desc" ]; then
        mv -- "$qr_tmp" "$save_path" || return 1
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
    if ! printf '%s' "$desc" | magick \
        -background white -fill black -font "$font" \
        -pointsize 48 -gravity center \
        label:@- \
        -bordercolor white -border 40x20 \
        "$qr_tmp" \
        -background white -gravity center -append \
        "$out"; then
        return 1
    fi
}

# Interactive front-end: gather inputs via gum, then call the engine.
# A cancelled gum prompt (Esc/Ctrl-C → non-zero) exits cleanly with no job.
run_tui() {
    ensure_gum || return 1

    local mode
    mode="$(gum choose --header 'Mode' 'Print' 'Save PNG')" || return 0
    [ -n "$mode" ] || return 0

    local dest=""
    if [ "$mode" = "Print" ]; then
        require_print_deps || return 1
        local printers default
        printers="$(lpstat -p 2>/dev/null | parse_printers || true)"
        default="$(default_printer)"
        if [ -n "$printers" ]; then
            if [ -n "$default" ]; then
                dest="$(printf '%s\n' "$printers" | gum choose --header 'Printer' --selected "$default")" || return 0
            else
                dest="$(printf '%s\n' "$printers" | gum choose --header 'Printer')" || return 0
            fi
        else
            dest="$default"
        fi
        if [ -z "$dest" ]; then
            echo "Error: no printer available" >&2
            return 1
        fi
    else
        require_qrencode || return 1
        dest="$(gum input --header 'Save path' --value 'qr.png')" || return 0
        [ -n "$dest" ] || return 0
    fi

    local text=""
    while [ -z "$text" ]; do
        text="$(gum input --header 'Text or URL' --placeholder 'https://example.com')" || return 0
    done

    local caption
    caption="$(gum input --header 'Caption (optional)' --placeholder 'Scan to RSVP')" || return 0

    if [ "$mode" = "Save PNG" ] && [ -n "$caption" ]; then
        require_magick || return 1
    fi

    # Advanced tuning (optional; default No). Per-mode defaults shown as the value.
    local mod="" ec=""
    if gum confirm --default=false 'Configure advanced options?'; then
        if [ "$mode" = "Print" ]; then
            mod="$(gum input --header 'Module size (1-16)' --value '8')" || return 0
            ec="$(gum choose --header 'Error correction' --selected 'M' 'L' 'M' 'Q' 'H')" || return 0
        else
            mod="$(gum input --header 'Module size (qrencode -s)' --value '10')" || return 0
            ec="$(gum choose --header 'Error correction' --selected 'L' 'L' 'M' 'Q' 'H')" || return 0
        fi
    fi

    # Summary + confirm.
    echo
    format_summary "$mode" "$dest" "$text" "$caption" "${mod:-default}" "${ec:-default}"
    echo
    gum confirm 'Proceed?' || return 0

    # Apply advanced overrides only when set (keep engine defaults otherwise).
    if [ -n "$mod" ]; then
        export MODULE_SIZE="$mod"
    fi
    if [ -n "$ec" ]; then
        export EC_LEVEL="$ec"
    fi

    if [ "$mode" = "Print" ]; then
        export PRINTER="$dest"
        do_print "$text" "$caption"
    else
        do_save "$dest" "$text" "$caption"
        if gum confirm 'Open preview?'; then
            open "$dest"
        fi
    fi
}

# --- dispatch -------------------------------------------------------------
main() {
    if [ "$#" -eq 0 ]; then
        run_tui
        return
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
