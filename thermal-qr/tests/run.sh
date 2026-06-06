#!/usr/bin/env bash
# Plain-shell test runner for print-qr.sh. No bats; just asserts + a counter.
# Pure-function tests source the script in a child shell (the source-guard
# keeps main() from running when sourced). Integration tests exec the script.
set -uo pipefail

SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/print-qr.sh"
fails=0

pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; fails=$((fails + 1)); }

assert_eq() { # <actual> <expected> <name>
    if [ "$1" = "$2" ]; then
        pass "$3"
    else
        fail "$3"
        printf '  expected: %q\n  actual:   %q\n' "$2" "$1" >&2
    fi
}

assert_contains() { # <haystack> <needle> <name>
    case "$1" in
        *"$2"*) pass "$3" ;;
        *) fail "$3"; printf '  missing: %q\n  in:      %q\n' "$2" "$1" >&2 ;;
    esac
}

# Run a snippet with print-qr.sh's functions sourced (isolated child shell).
src() { bash -c "source '$SCRIPT'; $1"; }

# --- print mode (dry-run byte stream) ------------------------------------
# Capture as hex (od) because the ESC/POS stream contains NUL bytes, which
# command substitution would strip from a plain string.
dryrun_hex() { # <args...> -> hex string of the byte stream
    PRINTQR_DRYRUN=1 "$SCRIPT" "$@" | od -An -tx1 | tr -d ' \n'
}

test_print_dryrun_contains_qr_and_payload() {
    local hex
    hex="$(dryrun_hex "hello")"
    assert_contains "$hex" "1b40"             "print: ESC @ init present"
    assert_contains "$hex" "1b6101"           "print: center alignment present"
    assert_contains "$hex" "1d286b"           "print: GS ( k QR command present"
    assert_contains "$hex" "31503068656c6c6f" "print: payload '1P0hello' embedded"
    assert_contains "$hex" "1d5600"           "print: GS V full cut present"
}

test_print_dryrun_contains_qr_and_payload

# --- save mode (characterization) ----------------------------------------
test_save_writes_png() {
    if ! command -v qrencode >/dev/null 2>&1; then
        printf 'SKIP: save PNG test (qrencode not installed)\n'
        return
    fi
    local tmp out ftype
    tmp="$(mktemp -d)"
    out="$tmp/qr.png"
    "$SCRIPT" --save "$out" "https://example.com" >/dev/null 2>&1
    ftype="$(file -b "$out" 2>/dev/null)"
    assert_contains "$ftype" "PNG image" "save mode writes a PNG"
    rm -rf "$tmp"
}

test_save_writes_png

# --- tuning: ec_to_escpos -------------------------------------------------
test_ec_to_escpos() {
    assert_eq "$(src 'ec_to_escpos L')" "48" "ec_to_escpos L -> 48"
    assert_eq "$(src 'ec_to_escpos M')" "49" "ec_to_escpos M -> 49"
    assert_eq "$(src 'ec_to_escpos Q')" "50" "ec_to_escpos Q -> 50"
    assert_eq "$(src 'ec_to_escpos H')" "51" "ec_to_escpos H -> 51"
}

# --- tuning: env vars override the print stream ---------------------------
test_print_honors_env_tuning() {
    local hex
    hex="$(MODULE_SIZE=5 EC_LEVEL=H dryrun_hex "hello")"
    # GS ( k 03 00 '1' 'C' <module> -> module-size command with 0x05
    assert_contains "$hex" "1d286b0300314305" "tuning: MODULE_SIZE=5 in stream"
    # GS ( k 03 00 '1' 'E' <ec> -> EC command with H (0x33)
    assert_contains "$hex" "1d286b0300314533" "tuning: EC_LEVEL=H in stream"
}

# --- tuning: defaults unchanged -------------------------------------------
test_print_default_tuning() {
    local hex
    hex="$(dryrun_hex "hello")"
    assert_contains "$hex" "1d286b0300314308" "tuning: default module size 8"
    assert_contains "$hex" "1d286b0300314531" "tuning: default EC M (0x31=49)"
}

test_ec_to_escpos
test_print_honors_env_tuning
test_print_default_tuning

# --- TUI seam: parse_printers --------------------------------------------
test_parse_printers() {
    local out exp
    out="$(printf 'printer POS80 is idle.  enabled since Mon\nprinter Office_LJ disabled since Tue\n' | src 'parse_printers')"
    exp="$(printf 'POS80\nOffice_LJ')"
    assert_eq "$out" "$exp" "parse_printers extracts printer names"
}

# --- TUI seam: format_summary --------------------------------------------
test_format_summary_print() {
    local out exp
    out="$(src "format_summary 'Print' 'POS80' 'https://x' '' '8' 'M'")"
    exp=$'Mode:     Print\nPrinter: POS80\nText:     https://x\nCaption:  (none)\nModule:   8\nEC level: M'
    assert_eq "$out" "$exp" "format_summary renders print fields"
}

test_format_summary_save() {
    local out exp
    out="$(src "format_summary 'Save PNG' 'qr.png' 'https://x' 'Scan me' '10' 'L'")"
    exp=$'Mode:     Save PNG\nPath:    qr.png\nText:     https://x\nCaption:  Scan me\nModule:   10\nEC level: L'
    assert_eq "$out" "$exp" "format_summary renders save fields"
}

# --- TUI seam: ensure_gum error path -------------------------------------
test_ensure_gum_no_gum_no_brew() {
    local msg
    msg="$(PATH=/usr/bin:/bin bash -c "source '$SCRIPT'; ensure_gum" </dev/null 2>&1)"
    assert_contains "$msg" "gum not found" "ensure_gum errors when gum and brew are absent"
}

test_parse_printers
test_format_summary_print
test_format_summary_save
test_ensure_gum_no_gum_no_brew

if [ "$fails" -gt 0 ]; then
    printf '%d test(s) failed\n' "$fails" >&2
    exit 1
fi
printf 'All tests passed\n'
