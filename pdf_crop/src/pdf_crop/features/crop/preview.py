from pathlib import Path

import fitz
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Static
from textual_image.widget import Image

from pdf_crop.shared import imaging

# A page only needs to be legible in the pane, not print-sharp; 150 dpi keeps
# the rasterize fast while staying crisp under the terminal graphics protocols.
PREVIEW_DPI = 150


class PagePreview(Vertical):
    """Right-pane page navigator that renders the current page as an image.

    Owns a 1-based `current` page index and the document `total`. A threaded,
    exclusive worker rasterizes the current page (fitz -> PIL) and hands the
    image to a `textual-image` widget on the main thread, so fast navigation
    cancels stale renders. Render failures show an inline message rather than
    crashing the app.
    """

    current: reactive[int] = reactive(1)

    def __init__(self, *, total: int, src: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.total = max(1, total)
        self.src = src
        self._included_pages: set[int] = set()

    def compose(self) -> ComposeResult:
        with Horizontal(id="preview_nav"):
            yield Button("< prev", id="prev_btn")
            yield Static("", id="preview_status")
            yield Button("next >", id="next_btn")
        yield Image(id="preview_image")
        yield Static("", id="preview_message")

    def on_mount(self) -> None:
        self._refresh_status()
        self._render_worker()

    # --- navigation (all clamp to [1, total]) ---------------------------------

    def goto(self, n: int) -> None:
        self.current = max(1, min(n, self.total))

    def next(self) -> None:
        self.goto(self.current + 1)

    def prev(self) -> None:
        self.goto(self.current - 1)

    # --- inclusion badge ------------------------------------------------------

    def included(self, pages: set[int]) -> bool:
        """Is the current page in the given selected-page set?"""
        return self.current in pages

    def set_selected(self, pages: set[int]) -> None:
        """Record the selected pages so the badge tracks the live range."""
        self._included_pages = pages
        self._refresh_status()

    def watch_current(self) -> None:
        self._refresh_status()
        # `current` can change before mount (e.g. unit tests drive goto/next
        # directly); only render once we're mounted with a worker host.
        if self.is_mounted:
            self._render_worker()

    def _refresh_status(self) -> None:
        try:
            status = self.query_one("#preview_status", Static)
        except Exception:
            return  # not mounted yet
        state = "included" if self.included(self._included_pages) else "excluded"
        colour = "green" if state == "included" else "red"
        status.update(
            f"Page {self.current}/{self.total} — [{colour}]{state}[/{colour}]"
        )

    # --- page image render (threaded, exclusive) ------------------------------

    def _render_page_image(self, page_number: int):
        """Rasterize 1-based `page_number` to a PIL image. The mockable boundary.

        Opens the document per render so the fitz object never crosses threads:
        the exclusive worker calls this, and closing a shared doc on unmount
        while a render reads it would be a use-after-free on a C object (not a
        catchable Python error). The returned PIL image owns its own pixels.
        """
        with fitz.open(str(self.src)) as doc:
            return imaging.render_page(doc[page_number - 1], dpi=PREVIEW_DPI)

    @work(thread=True, exclusive=True, group="preview-render")
    def _render_worker(self) -> None:
        if self.src is None:
            return
        page_number = self.current
        try:
            self._show_loading()
            image = self._render_page_image(page_number)
        except Exception as e:  # never let a render error escape and crash the app
            self.app.call_from_thread(self._render_failed, e)
            return
        self.app.call_from_thread(self._render_done, image)

    def _show_loading(self) -> None:
        try:
            self.app.call_from_thread(
                self.query_one("#preview_message", Static).update,
                "[dim]Rendering…[/dim]",
            )
        except Exception:
            return  # not mounted yet

    def _render_done(self, image) -> None:
        try:
            self.query_one("#preview_image", Image).image = image
            self.query_one("#preview_message", Static).update("")
        except Exception:
            return  # widget gone (e.g. unmounted mid-render)

    def _render_failed(self, error: Exception) -> None:
        try:
            self.query_one("#preview_message", Static).update(
                f"[red]Preview unavailable: {error}[/red]"
            )
        except Exception:
            return  # widget gone (e.g. unmounted mid-render)
