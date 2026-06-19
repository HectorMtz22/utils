from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Static

from pdf_crop.features.crop import command
from pdf_crop.features.crop.preview import PagePreview
from pdf_crop.features.redact import service as redact_service
from pdf_crop.features.redact import text_layer
from pdf_crop.features.sanitize import service as sanitize_service
from pdf_crop.shared import output_path, pdf_io, ranges
from pdf_crop.shared.errors import PdfCropError, QrRedactionFailed


def _join_lines(*lines):
    return "\n".join(line for line in lines if line)


class HelpScreen(ModalScreen):
    """Keybinding cheat sheet shown over the crop screen."""

    BINDINGS = [("escape,question_mark,f1", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        panel = Static(
            _join_lines(
                "s            Scan for sensitive data",
                "c / enter    Crop",
                "← / h        Previous page",
                "→ / l        Next page",
                "z            Toggle zoom (Fit / 100%)",
                "? / f1       Toggle this help",
                "q / esc      Quit",
            ),
            id="help_panel",
        )
        panel.border_title = "Keybindings"
        yield panel


class CropScreen(Screen):
    """Two-pane page picker: controls on the left, page preview on the right."""

    CSS_PATH = "screen.tcss"

    BINDINGS = [
        Binding("s", "scan", "Scan", show=False),
        Binding("c", "crop", "Crop", show=False),
        Binding("enter", "crop", "Crop", show=False),
        Binding("left,h", "prev_page", "Prev page", show=False),
        Binding("right,l", "next_page", "Next page", show=False),
        Binding("z", "toggle_zoom", "Zoom", show=False),
        Binding("question_mark,f1", "help", "Help"),
        Binding("q,escape", "quit", "Quit"),
    ]

    def __init__(self, src: Path, *, sanitize: bool = False) -> None:
        super().__init__()
        self.src = src
        self.reader = pdf_io.open_pdf(src)
        self.total = pdf_io.page_count(self.reader)
        self._sanitize_default = sanitize
        self._findings = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="crop_body"):
            with VerticalScroll(id="controls"):
                yield self._pages_section()
                yield self._redaction_section()
                yield self._output_section()
            preview = PagePreview(total=self.total, src=self.src, id="preview")
            preview.border_title = f"Preview — {self.src.name}"
            yield preview
        with Vertical(id="action_bar"):
            yield Static("", id="error_msg")
            yield Static("", id="result_msg")
            with Horizontal(id="action_buttons"):
                yield Button("Crop", id="crop_btn", variant="primary")
                yield Button("Cancel", id="cancel_btn")
        yield Footer()

    def _pages_section(self) -> Vertical:
        section = Vertical(
            Static(f"File: {self.src.name}"),
            Static(f"Total pages: {self.total}"),
            Input(placeholder="e.g. 1-5,8,11-13", id="range_input"),
            Static("Enter a page range to begin.", id="pages_hint"),
            classes="section",
            id="pages_section",
        )
        section.border_title = "Pages"
        return section

    def _redaction_section(self) -> Vertical:
        section = Vertical(
            Checkbox("Redact: CLABE", id="cat_clabe_chk"),
            Checkbox("Redact: Card numbers", id="cat_card_chk"),
            Checkbox("Redact: RFC/CURP", id="cat_rfccurp_chk"),
            Checkbox("Redact: Names", id="cat_name_chk"),
            Input(placeholder="comma-separated names to redact", id="names_input"),
            Button("Scan", id="scan_btn"),
            Static("", id="preview_msg", classes="found-summary"),
            Checkbox("Apply redaction", id="apply_redaction_chk", disabled=True),
            Checkbox("Redact QR/barcodes", id="redact_qr_chk"),
            Checkbox("OCR scan (for scanned pages)", id="ocr_chk"),
            classes="section",
            id="redaction_section",
        )
        section.border_title = "Redaction"
        return section

    def _output_section(self) -> Vertical:
        section = Vertical(
            Checkbox(
                "Rebuild clean (strip all non-essential)",
                value=self._sanitize_default,
                id="sanitize_chk",
            ),
            Button("List metadata", id="list_metadata_btn"),
            Static("", id="metadata_msg", classes="found-summary"),
            classes="section",
            id="output_section",
        )
        section.border_title = "Output"
        return section

    # --- helpers --------------------------------------------------------------

    def _selected_categories(self):
        cats = set()
        if self.query_one("#cat_clabe_chk", Checkbox).value:
            cats.add("clabe")
        if self.query_one("#cat_card_chk", Checkbox).value:
            cats.add("card")
        if self.query_one("#cat_rfccurp_chk", Checkbox).value:
            cats.update({"rfc", "curp"})
        if self.query_one("#cat_name_chk", Checkbox).value:
            cats.add("name")
        return cats

    def _names(self):
        raw = self.query_one("#names_input", Input).value
        return [n.strip() for n in raw.split(",") if n.strip()]

    def _qr_preview_line(self, pages, redact_qr):
        """Scan for QR/barcodes (if requested) and return a preview line (a str).

        Returns "" when the QR option is off. Exposes each decoded payload so the
        user can verify it's really their data before exporting. A render/decode
        failure is translated to a PdfCropError so the caller can show it.

        `redact_qr` is read on the main thread by the caller — this runs in a
        worker thread, which must not touch the DOM.
        """
        if not redact_qr:
            return ""
        try:
            from pdf_crop.features.qr_redact import service as qr_service
            findings = qr_service.scan(self.src, pages)
        except PdfCropError:
            raise
        except Exception as e:  # zbar missing / fitz render / decode failure
            raise QrRedactionFailed(f"QR/barcode scan failed: {e}") from e
        if not findings.codes:
            return "QR/barcodes: none found."
        items = ", ".join(f"{c.symbology} {c.payload!r}" for c in findings.codes)
        return f"QR/barcodes ({len(findings.codes)}): {items}"

    def _page_has_text(self, page_number):
        try:
            text, _ = text_layer.page_text(self.reader.pages[page_number - 1])
        except Exception:
            return False
        return bool(text.strip())

    def _reset_preview(self):
        self.query_one("#preview_msg", Static).update("")
        chk = self.query_one("#apply_redaction_chk", Checkbox)
        chk.value = False
        chk.disabled = True
        self._findings = None

    def _update_badge(self, value: str) -> None:
        """Update the preview included/excluded badge from the current range."""
        preview = self.query_one(PagePreview)
        try:
            pages = set(ranges.parse(value, self.total))
        except PdfCropError:
            pages = set()
        preview.set_selected(pages)

    def _input_focused(self) -> bool:
        return isinstance(self.focused, Input)

    # --- events ---------------------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        self._reset_preview()
        if event.input.id != "range_input":
            return
        self._update_badge(event.value)
        error_msg = self.query_one("#error_msg", Static)
        value = event.value.strip()
        if not value:
            error_msg.update("")
            return
        try:
            ranges.parse(value, self.total)
            error_msg.update("")
        except PdfCropError as e:
            error_msg.update(f"[red]{e}[/red]")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id != "apply_redaction_chk":
            self._reset_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.app.exit(0)
        elif event.button.id == "list_metadata_btn":
            self._list_metadata()
        elif event.button.id == "scan_btn":
            self._start_scan()
        elif event.button.id == "crop_btn":
            self._start_crop()
        elif event.button.id == "prev_btn":
            self.query_one(PagePreview).prev()
        elif event.button.id == "next_btn":
            self.query_one(PagePreview).next()
        elif event.button.id == "zoom_btn":
            self.query_one(PagePreview).toggle_zoom()

    # --- actions (keybindings) ------------------------------------------------

    def action_scan(self) -> None:
        if not self._input_focused():
            self._start_scan()

    def action_crop(self) -> None:
        if not self._input_focused():
            self._start_crop()

    def action_prev_page(self) -> None:
        if not self._input_focused():
            self.query_one(PagePreview).prev()

    def action_next_page(self) -> None:
        if not self._input_focused():
            self.query_one(PagePreview).next()

    def action_toggle_zoom(self) -> None:
        if not self._input_focused():
            self.query_one(PagePreview).toggle_zoom()

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen())

    def action_quit(self) -> None:
        self.app.exit(0)

    # --- metadata -------------------------------------------------------------

    def _list_metadata(self) -> None:
        inv = sanitize_service.inventory(self.reader)
        summary = inv.summary()
        metadata_msg = self.query_one("#metadata_msg", Static)
        if not summary:
            metadata_msg.update("Metadata: nothing found.")
            return
        parts = ", ".join(f"{v} {k}" for k, v in summary.items())
        metadata_msg.update(f"Metadata: {parts} ({inv.total()} total)")

    # --- scan (threaded) ------------------------------------------------------

    def _start_scan(self) -> None:
        error_msg = self.query_one("#error_msg", Static)
        try:
            pages = ranges.parse(self.query_one("#range_input", Input).value, self.total)
        except PdfCropError as e:
            error_msg.update(f"[red]{e}[/red]")
            return
        error_msg.update("")
        self.query_one("#preview_msg", Static).update("Scanning…")
        self._scan_worker(
            pages,
            self._selected_categories(),
            self._names(),
            self.query_one("#redact_qr_chk", Checkbox).value,
        )

    @work(thread=True, exit_on_error=False, group="pdf", exclusive=True)
    def _scan_worker(self, pages, cats, names, redact_qr) -> None:
        try:
            qr_line = self._qr_preview_line(pages, redact_qr)
            if not cats:
                self.app.call_from_thread(
                    self._scan_done, qr_line or "Select at least one category to scan.", False
                )
                return
            self._findings = redact_service.scan(
                self.reader, pages, categories=cats, names=names
            )
            summary = self._findings.summary()
            if not summary:
                msg = "Found: nothing to redact."
                if not any(self._page_has_text(p) for p in pages):
                    msg += " (No extractable text — redaction needs a text layer.)"
                self.app.call_from_thread(self._scan_done, _join_lines(msg, qr_line), False)
                return
            parts = ", ".join(f"{v} {k}" for k, v in summary.items())
            total = sum(summary.values())
            note = ""
            if self._findings.skipped_pages:
                note = f" — {len(self._findings.skipped_pages)} page(s) skipped (unreadable)"
            line = _join_lines(f"Found: {parts} ({total} total){note}", qr_line)
            self.app.call_from_thread(self._scan_done, line, True)
        except PdfCropError as e:
            self.app.call_from_thread(self._scan_error, str(e))

    def _scan_done(self, message: str, enable_apply: bool) -> None:
        self.query_one("#preview_msg", Static).update(message)
        self.query_one("#apply_redaction_chk", Checkbox).disabled = not enable_apply

    def _scan_error(self, message: str) -> None:
        self.query_one("#preview_msg", Static).update("")
        self.query_one("#error_msg", Static).update(f"[red]{message}[/red]")

    # --- crop (threaded) ------------------------------------------------------

    def _start_crop(self) -> None:
        error_msg = self.query_one("#error_msg", Static)
        try:
            pages = ranges.parse(self.query_one("#range_input", Input).value, self.total)
        except PdfCropError as e:
            error_msg.update(f"[red]{e}[/red]")
            return
        error_msg.update("")
        self.query_one("#result_msg", Static).update("Cropping…")
        self._crop_worker(
            pages,
            sanitize=self.query_one("#sanitize_chk", Checkbox).value,
            apply_redaction=self.query_one("#apply_redaction_chk", Checkbox).value,
            redact_qr=self.query_one("#redact_qr_chk", Checkbox).value,
            ocr=self.query_one("#ocr_chk", Checkbox).value,
            categories=self._selected_categories(),
            names=self._names(),
        )

    @work(thread=True, exit_on_error=False, group="pdf", exclusive=True)
    def _crop_worker(
        self, pages, *, sanitize, apply_redaction, redact_qr, ocr, categories, names
    ) -> None:
        try:
            dest = output_path.resolve(self.src)
            writer = pdf_io.build_subset(self.reader, pages, sanitize=sanitize)
            redacted = 0
            if apply_redaction and self._findings is not None:
                redacted = redact_service.redact(
                    writer, categories=categories, names=names
                )
            with dest.open("wb") as f:
                writer.write(f)
            qr_removed = command._redact_qr_in_place(dest) if redact_qr else 0
            ocr_removed = (
                command._redact_ocr_in_place(dest, categories=categories, names=names)
                if ocr
                else 0
            )
        except PdfCropError as e:
            self.app.call_from_thread(self._crop_error, str(e))
            return
        notes = []
        if redacted:
            notes.append(f"redacted {redacted} items")
        if qr_removed:
            notes.append(f"{qr_removed} QR/barcodes")
        if ocr_removed:
            notes.append(f"{ocr_removed} OCR items")
        suffix = f" ({', '.join(notes)})" if notes else ""
        self.app.call_from_thread(self._crop_done, f"Wrote {dest}{suffix}")

    def _crop_done(self, message: str) -> None:
        self.query_one("#result_msg", Static).update(f"[green]{message}[/green]")

    def _crop_error(self, message: str) -> None:
        self.query_one("#result_msg", Static).update("")
        self.query_one("#error_msg", Static).update(f"[red]{message}[/red]")
