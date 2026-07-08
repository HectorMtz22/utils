# pdf_crop

CLI + TUI to extract a page range from a PDF.

```bash
uv sync
uv run pdfcrop Document.pdf            # opens the two-pane TUI
uv run pdfcrop Document.pdf 1-5,8      # direct mode (no TUI)
```

Output: `Document_cropped.pdf` next to the source. If it exists, suffixed `(1)`, `(2)`, …

## Choosing the output location

By default the cropped PDF is written next to the source, as
`<name>_cropped.pdf`. Use `-o`/`--output` (CLI) or the **Output path** field
(TUI) to send it somewhere else — a folder, an exact filename, or both. A
`.pdf` extension (case-insensitive) is the only signal that decides which:

```bash
uv run pdfcrop Document.pdf 1-5,8 -o ~/out              # folder: ~/out/Document_cropped.pdf
uv run pdfcrop Document.pdf 1-5,8 -o report.pdf          # exact file: ./report.pdf
uv run pdfcrop Document.pdf 1-5,8 -o ~/out/report.pdf    # folder + file: ~/out/report.pdf
```

| `--output` value      | Interpreted as        | Result                                   |
|-----------------------|------------------------|-------------------------------------------|
| *(omitted)*           | —                      | `<src_dir>/<stem>_cropped.pdf`             |
| `~/out` or `~/out/`   | folder                 | `~/out/<stem>_cropped.pdf`                 |
| `reports/2026`        | folder (created)       | `reports/2026/<stem>_cropped.pdf`          |
| `report.pdf`          | exact file             | `./report.pdf` (relative to cwd)           |
| `~/out/report.pdf`    | folder **and** file    | `~/out/report.pdf`                         |

Missing folders are created automatically; `~` is expanded. Just like the
default location, the tool **never overwrites** — a collision auto-suffixes
`(1)`, `(2)`, … even on an explicit filename.

## The TUI

Running `pdfcrop` on a file with no range opens a **two-pane** terminal UI:
grouped controls on the left, a live preview of the current page on the right.

```
┌ Pages ────────┐  ┌ Preview — Document.pdf ──┐
│ Range: 1-5,8  │  │  < prev   3/12   next >  │
├ Redaction ────┤  │                          │
│ [ ] CLABE     │  │   [ rendered page 3 ]    │
│ [ ] Cards     │  │                          │
│ [ ] RFC/CURP  │  │   Page 3/12 — included   │
│ [ ] Names     │  │                          │
│ [Scan]        │  └──────────────────────────┘
├ Output ───────┤
│ [ path input ]│
│ [ ] Rebuild   │
└───────────────┘
        [ Crop ]   [ Cancel ]
```

The left pane groups controls into three sections:

- **Pages** — type a page range (`1-5,8,11-13`), validated as you type.
- **Redaction** — the CLABE / card / RFC-CURP / name detectors, plus the
  *Redact QR/barcodes* and *OCR scan* toggles (see the sections below).
- **Output** — an **Output path** field (folder, exact filename, or both —
  same rules as `-o`/`--output` above; blank writes next to the source),
  *Rebuild clean* (strip non-essential metadata), and *List metadata* (print an
  inventory of what's in the file).

The right **preview** renders the actual page as an image. Step through pages
with `< prev` / `next >` or the arrow keys; the badge reads `Page X/Y` and
whether that page is **included** in or **excluded** from your current range, so
you can confirm the range visually before cropping.

Press **Crop** (or `c`) to write the output. The result stays on screen
(`Wrote …`) so you can tweak the range and crop again — `Cancel` or `q` exits.

### Keybindings

| Key | Action |
|---|---|
| `s` | Scan for sensitive data |
| `c` / `enter` | Crop |
| `←` / `h`,  `→` / `l` | Previous / next page |
| `?` / `F1` | Toggle the help overlay |
| `q` / `esc` | Quit |

These keys act on the screen only when a text field isn't focused — while you're
typing in the **Range** or **names** box they go to the field, so you can enter
a range freely. Use the buttons or click away from the field to invoke them.

### Page preview rendering

The preview uses [`textual-image`](https://pypi.org/project/textual-image/),
which auto-detects your terminal's graphics protocol (Kitty / iTerm2 / sixel)
and falls back to unicode half-blocks elsewhere — so the preview works in any
terminal, just at lower fidelity without graphics support. Rendering runs off
the UI thread; if a page can't be rendered the pane shows `Preview unavailable`
instead of crashing.

## Redaction (TUI)

The TUI can **truly remove** sensitive data from the cropped output — the
matched characters are deleted from the PDF's text layer, so they can't be
copied or extracted (not just covered with a box).

In the **Redaction** section, tick the categories you want and press **Scan**:

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

## OCR (scanned / image-only pages)

Scanned statements have **no text layer**, so the text-layer detectors above
find nothing. A separate OCR pass renders each page, reads it with `tesseract`
(via `pytesseract`), reconstructs the page text while tracking every word's
bounding box, runs the same CLABE / card / RFC / CURP detectors over that text,
and applies a **true** PyMuPDF redaction over each matched word — the text is
removed from the image, not just covered.

```bash
uv run pdfcrop Document.pdf 1-5 --ocr   # crop, then OCR-redact scanned pages
```

`--ocr` scans the automatic categories (CLABE, card, RFC, CURP). In the TUI,
tick **OCR scan (for scanned pages)**: the second pass uses the category
checkboxes you've selected plus the *names* field, so it can also redact names
on scanned pages. Like the QR pass, this runs over the already-cropped output.

### Native dependency: tesseract

OCR needs the native `tesseract` engine (via `pytesseract`). On macOS:

```bash
brew install tesseract
```

The OCR tests skip automatically when the `tesseract` binary isn't on `PATH`,
so the rest of the suite still runs on a machine without it.

## Develop

```bash
uv sync
uv run pytest
```
