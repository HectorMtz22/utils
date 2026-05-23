# thermal-qr

Print a QR code of a URL or arbitrary text to an 80mm ESC/POS thermal receipt printer on macOS.

The script sends raw ESC/POS bytes (`-o raw`), bypassing whatever CUPS driver the printer is installed with. The QR is rendered by the printer itself via its native `GS ( k` QR command, centered with `ESC a 1`, and the paper is cut with `GS V`.

## Prerequisites

- macOS (uses the system `python3` and `lp`)
- An ESC/POS thermal printer installed in System Settings → Printers & Scanners
- The printer must support the native QR command (`GS ( k`) and auto-cut (`GS V`). Most POS80 / generic ESC/POS thermals from the last decade do.

## Usage

```bash
./print-qr.sh "https://example.com"
./print-qr.sh "https://example.com" "Scan to RSVP"
```

The optional second argument is a description printed bold and double-size above the QR.

## Changing the printer

Defaults to the system default printer. Override with the `PRINTER` env var:

```bash
PRINTER=USBPRINT ./print-qr.sh "hello"
```

## Tuning

Edit the constants near the top of the Python block:

- `MODULE_SIZE` (1–16): dots per QR module. 8 is roughly 1mm/module at 203 DPI.
- `EC_LEVEL`: error correction — `48`=L, `49`=M, `50`=Q, `51`=H.
