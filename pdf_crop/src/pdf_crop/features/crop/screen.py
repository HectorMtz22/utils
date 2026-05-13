from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Static

from pdf_crop.shared import output_path, pdf_io, ranges
from pdf_crop.shared.errors import PdfCropError

from .service import crop_pdf


class CropScreen(Screen):
    """Single-screen page picker."""

    def __init__(self, src: Path, *, strip_metadata: bool = False) -> None:
        super().__init__()
        self.src = src
        self.reader = pdf_io.open_pdf(src)
        self.total = pdf_io.page_count(self.reader)
        self._strip_metadata_default = strip_metadata

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static(f"File: {self.src.name}"),
            Static(f"Total pages: {self.total}"),
            Input(placeholder='e.g. 1-5,8,11-13', id="range_input"),
            Checkbox("Remove metadata", value=self._strip_metadata_default, id="strip_metadata_chk"),
            Static("", id="error_msg"),
            Static("", id="result_msg"),
            Button("Crop", id="crop_btn", variant="primary"),
            Button("Cancel", id="cancel_btn"),
        )
        yield Footer()

    def on_input_changed(self, event: Input.Changed) -> None:
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.app.exit(0)
            return
        if event.button.id == "crop_btn":
            input_widget = self.query_one("#range_input", Input)
            error_msg = self.query_one("#error_msg", Static)
            result_msg = self.query_one("#result_msg", Static)
            chk = self.query_one("#strip_metadata_chk", Checkbox)
            try:
                pages = ranges.parse(input_widget.value, self.total)
                dest = output_path.resolve(self.src)
                result = crop_pdf(self.reader, pages, dest, strip_metadata=chk.value)
            except PdfCropError as e:
                error_msg.update(f"[red]{e}[/red]")
                return
            result_msg.update(f"[green]Wrote {result}[/green]")
            self.app.exit(0)
