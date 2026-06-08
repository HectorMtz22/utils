# thermal-qr

Print a QR code of a URL or arbitrary text to an 80mm ESC/POS thermal receipt printer on macOS.

The script sends raw ESC/POS bytes (`-o raw`), bypassing whatever CUPS driver the printer is installed with. The QR is rendered by the printer itself via its native `GS ( k` QR command, centered with `ESC a 1`, and the paper is cut with `GS V`.

## Prerequisites

- macOS (uses the system `python3` and `lp`)
- An ESC/POS thermal printer installed in System Settings → Printers & Scanners
- The printer must support the native QR command (`GS ( k`) and auto-cut (`GS V`). Most POS80 / generic ESC/POS thermals from the last decade do.

For `--save` (writing a PNG instead of printing) you'll additionally need:

- `qrencode` (always, when using `--save`): `brew install qrencode`
- `imagemagick` (only when also passing a description to `--save`): `brew install imagemagick`

`--save` does not invoke `lp` and does not need a printer configured.

## Usage

```bash
./print-qr.sh "https://example.com"
./print-qr.sh "https://example.com" "Scan to RSVP"
```

The optional second argument is a description printed bold and double-size above the QR.

## Interactive TUI

Run with no arguments to open an interactive menu (requires
[`gum`](https://github.com/charmbracelet/gum): `brew install gum` — the script
offers to install it for you on first run):

```bash
./print-qr.sh
```

It walks you through the mode (print vs. save PNG), printer (or save path),
text/URL, optional caption, optional advanced tuning (module size, error
correction), a confirmation summary, and — in save mode — opening the result.
The flag-based CLI below continues to work unchanged.

## Save to PNG

Use `--save <path>` to write the QR (and optional caption) to a PNG file instead of printing. The flag must come before the positional arguments.

```bash
./print-qr.sh --save out.png "https://example.com"
./print-qr.sh --save out.png "https://example.com" "Scan to RSVP"
```

Without a description the file is a plain QR PNG from `qrencode`. With a description, ImageMagick composes a bold black caption above the QR on a white background. An existing file at `<path>` will be overwritten; an existing directory at `<path>` is refused.

## Changing the printer

Defaults to the system default printer. Override with the `PRINTER` env var:

```bash
PRINTER=USBPRINT ./print-qr.sh "hello"
```

## Tuning

Two QR parameters are overridable per-invocation via environment variables
(they also drive the TUI's "advanced options"):

- `MODULE_SIZE`: dots per QR module. Defaults to `8` when printing (≈1mm/module
  at 203 DPI) and `10` when saving a PNG (passed to `qrencode -s`).
- `EC_LEVEL`: error correction, one of `L`/`M`/`Q`/`H`. Defaults to `M` when
  printing and `L` when saving.

For example: `EC_LEVEL=H MODULE_SIZE=10 ./print-qr.sh "hello"`.
