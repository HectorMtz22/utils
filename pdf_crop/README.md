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

## Develop

```bash
uv sync
uv run pytest
```
