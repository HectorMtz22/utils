from pathlib import Path

from textual.app import App

from pdf_crop.features.crop.screen import CropScreen


class PdfCropApp(App):
    """Textual app shell. v1 mounts the crop screen."""

    def __init__(self, src: Path, *, sanitize: bool = False) -> None:
        super().__init__()
        self._src = src
        self._sanitize = sanitize

    def on_mount(self) -> None:
        self.push_screen(CropScreen(self._src, sanitize=self._sanitize))
