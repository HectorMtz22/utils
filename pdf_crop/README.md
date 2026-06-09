# pdf_crop

CLI + TUI to extract a page range from a PDF.

```bash
uv sync
uv run pdfcrop Document.pdf            # opens TUI for page selection
uv run pdfcrop Document.pdf 1-5,8      # direct mode
```

Output: `Document_cropped.pdf` next to the source. If it exists, suffixed `(1)`, `(2)`, …

## Redaction (TUI)

The TUI can **truly remove** sensitive data from the cropped output — the
matched characters are deleted from the PDF's text layer, so they can't be
copied or extracted (not just covered with a box).

In the TUI, tick the categories you want and press **Scan**:

- **CLABE** — 18-digit Mexican interbank account numbers
- **Card numbers** — 16-digit card numbers (validated with the Luhn checksum)
- **RFC/CURP** — Mexican tax (RFC) and national (CURP) identifiers
- **Names** — each comma-separated name typed in the *names* field, matched
  case- and accent-insensitively (e.g. `José Pérez` also matches `JOSE PEREZ`)

Scan shows a preview of what was found (e.g. `Found: 3 clabe, 2 name (5 total)`).
Nothing is removed until you tick **Apply redaction** and press **Crop** —
the result message then notes how many items were redacted. Changing the page
range or any category clears the preview, so you always confirm a fresh scan.

**Limitation:** redaction works on PDFs with a real text layer (digitally
generated documents, such as bank statements). Scanned or image-only pages have
no extractable text — the preview will report that and remove nothing.

## QR codes / barcodes

Bank statements often embed CLABE / account / payment data in a **QR code or
barcode** that the text-layer detectors above never see. A separate pass
renders each page, decodes every symbol, and applies a **true** PyMuPDF
redaction over each one — the image content is removed from the output, not
just covered.

```bash
uv run pdfcrop Document.pdf 1-5 --redact-qr   # crop, then remove every QR/barcode
```

In the TUI, tick **Redact QR/barcodes** and press **Scan**: the preview lists
each found code with its decoded payload, so you can confirm it's really your
data before cropping. By default **every** detected code is redacted.

This runs as a second pass over the already-cropped output, so the text-layer
crop/redaction pipeline is untouched.

### Native dependency: zbar

Decoding needs the native `zbar` library (via `pyzbar`). On macOS:

```bash
brew install zbar
```

`pyzbar` looks for the dylib on the dynamic-linker path, which doesn't include
Homebrew's prefix by default. If you hit `Unable to find zbar shared library`,
point it at the Homebrew install:

```bash
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/zbar/lib   # Apple silicon
# export DYLD_LIBRARY_PATH=/usr/local/opt/zbar/lib    # Intel
```

The QR tests skip automatically when `zbar` isn't available, so the rest of the
suite still runs on a machine without it.

## Develop

```bash
uv sync
uv run pytest
```
