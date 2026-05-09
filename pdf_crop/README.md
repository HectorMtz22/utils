# pdf_crop

CLI + TUI to extract a page range from a PDF.

```bash
uv sync
uv run pdfcrop Document.pdf            # opens TUI for page selection
uv run pdfcrop Document.pdf 1-5,8      # direct mode
```

Output: `Document_cropped.pdf` next to the source. If it exists, suffixed `(1)`, `(2)`, …

## Develop

```bash
uv sync
uv run pytest
```
