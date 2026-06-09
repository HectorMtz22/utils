from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Static

from pdf_crop.features.crop import command
from pdf_crop.features.redact import service as redact_service
from pdf_crop.features.redact import text_layer
from pdf_crop.shared import output_path, pdf_io, ranges
from pdf_crop.shared.errors import PdfCropError


def _join_lines(*lines):
    return "\n".join(line for line in lines if line)


class CropScreen(Screen):
    """Single-screen page picker."""

    def __init__(self, src: Path, *, strip_metadata: bool = False) -> None:
        super().__init__()
        self.src = src
        self.reader = pdf_io.open_pdf(src)
        self.total = pdf_io.page_count(self.reader)
        self._strip_metadata_default = strip_metadata
        self._findings = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static(f"File: {self.src.name}"),
            Static(f"Total pages: {self.total}"),
            Input(placeholder='e.g. 1-5,8,11-13', id="range_input"),
            Checkbox("Redact: CLABE", id="cat_clabe_chk"),
            Checkbox("Redact: Card numbers", id="cat_card_chk"),
            Checkbox("Redact: RFC/CURP", id="cat_rfccurp_chk"),
            Checkbox("Redact: Names", id="cat_name_chk"),
            Input(placeholder="comma-separated names to redact", id="names_input"),
            Button("Scan", id="scan_btn"),
            Static("", id="preview_msg"),
            Checkbox("Apply redaction", id="apply_redaction_chk", disabled=True),
            Checkbox("Redact QR/barcodes", id="redact_qr_chk"),
            Checkbox("Remove metadata", value=self._strip_metadata_default, id="strip_metadata_chk"),
            Static("", id="error_msg"),
            Static("", id="result_msg"),
            Button("Crop", id="crop_btn", variant="primary"),
            Button("Cancel", id="cancel_btn"),
        )
        yield Footer()

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

    def _qr_preview_line(self, pages):
        """Scan for QR/barcodes (if requested) and return a preview line + findings.

        Returns "" when the QR option is off. Exposes each decoded payload so the
        user can verify it's really their data before exporting.
        """
        if not self.query_one("#redact_qr_chk", Checkbox).value:
            return ""
        from pdf_crop.features.qr_redact import service as qr_service
        findings = qr_service.scan(self.src, pages)
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

    def on_input_changed(self, event: Input.Changed) -> None:
        self._reset_preview()
        if event.input.id != "range_input":
            return
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
            return

        if event.button.id == "scan_btn":
            error_msg = self.query_one("#error_msg", Static)
            preview = self.query_one("#preview_msg", Static)
            try:
                pages = ranges.parse(self.query_one("#range_input", Input).value, self.total)
            except PdfCropError as e:
                error_msg.update(f"[red]{e}[/red]")
                return
            qr_line = self._qr_preview_line(pages)
            cats = self._selected_categories()
            if not cats:
                preview.update(qr_line or "Select at least one category to scan.")
                return
            self._findings = redact_service.scan(
                self.reader, pages, categories=cats, names=self._names()
            )
            summary = self._findings.summary()
            if not summary:
                msg = "Found: nothing to redact."
                if not any(self._page_has_text(p) for p in pages):
                    msg += " (No extractable text — redaction needs a text layer.)"
                preview.update(_join_lines(msg, qr_line))
                return
            parts = ", ".join(f"{v} {k}" for k, v in summary.items())
            total = sum(summary.values())
            note = ""
            if self._findings.skipped_pages:
                note = f" — {len(self._findings.skipped_pages)} page(s) skipped (unreadable)"
            preview.update(_join_lines(f"Found: {parts} ({total} total){note}", qr_line))
            self.query_one("#apply_redaction_chk", Checkbox).disabled = False
            return

        if event.button.id == "crop_btn":
            input_widget = self.query_one("#range_input", Input)
            error_msg = self.query_one("#error_msg", Static)
            result_msg = self.query_one("#result_msg", Static)
            strip = self.query_one("#strip_metadata_chk", Checkbox).value
            apply_redaction = self.query_one("#apply_redaction_chk", Checkbox).value
            try:
                pages = ranges.parse(input_widget.value, self.total)
                dest = output_path.resolve(self.src)
                writer = pdf_io.build_subset(self.reader, pages, strip_metadata=strip)
                redacted = 0
                if apply_redaction and self._findings is not None:
                    redacted = redact_service.redact(
                        writer,
                        categories=self._selected_categories(),
                        names=self._names(),
                    )
                with dest.open("wb") as f:
                    writer.write(f)
                qr_removed = 0
                if self.query_one("#redact_qr_chk", Checkbox).value:
                    qr_removed = command._redact_qr_in_place(dest)
            except PdfCropError as e:
                error_msg.update(f"[red]{e}[/red]")
                return
            notes = []
            if redacted:
                notes.append(f"redacted {redacted} items")
            if qr_removed:
                notes.append(f"{qr_removed} QR/barcodes")
            suffix = f" ({', '.join(notes)})" if notes else ""
            result_msg.update(f"[green]Wrote {dest}{suffix}[/green]")
            self.app.exit(0)
            return
