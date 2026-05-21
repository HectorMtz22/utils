# thermal-qr

Print a QR code of a URL or arbitrary text to the macOS default printer (intended for a USB/network thermal receipt printer).

## Prerequisites

- macOS
- A printer set as default in System Settings → Printers & Scanners
- `qrencode` (`brew install qrencode`)

## Usage

```bash
./print-qr.sh "https://example.com"
```

## Changing the printer

The script uses whatever printer is currently set as the system default. To print to a different printer, change the default in System Settings → Printers & Scanners.
