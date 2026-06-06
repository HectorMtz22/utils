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

if [ "$fails" -gt 0 ]; then
    printf '%d test(s) failed\n' "$fails" >&2
    exit 1
fi
printf 'All tests passed\n'
